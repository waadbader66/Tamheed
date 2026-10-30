"""Durable onboarding pipeline. Stages are persisted in SQLite, idempotent, retryable and resumed after restart."""
import json
import os
import secrets
import threading
import time
import traceback
from datetime import datetime, timedelta
from pathlib import Path

from . import agent, analysis as A, config, exercise as X, llm, mailer, scriptgen, video
from .auth import hash_password, temp_password
from .db import SessionLocal
from .models import (Artifact, Course, Employee, Invitation, JobStage, OnboardingCase, OnboardingTask, ResponsibilityPlan,
                     TrainingAssignment, User, AgentEvent, Exercise, audit, JSONMixin)

J, L = JSONMixin.dump, JSONMixin.load

STAGES = [
    ("record", "Employee record saved & onboarding detected"),
    ("cv", "CV, experience, role, team & project retrieved"),
    ("analysis", "Onboarding agent reads the CV and plans (Claude)"),
    ("tasks", "Onboarding tasks, equipment & first-week actions"),
    ("responsibilities", "Responsibilities & mentoring decided"),
    ("training", "Training & courses chosen"),
    ("exercise", "Agent designs a practical exercise"),
    ("video", "Personalised animated video rendered"),
    ("workspace", "Employee workspace ready"),
    ("invitation", "Invitation email delivered"),
]


def create_stages(db, case: OnboardingCase) -> None:
    for i, (k, label) in enumerate(STAGES):
        db.add(JobStage(case_id=case.id, key=k, label=label, position=i))


# ---------------------------------------------------------------- stage handlers (each idempotent)
def st_record(db, case, emp):
    return f"{emp.full_name} ({emp.employee_code}) — {emp.title}, start {emp.start_date}"


def st_cv(db, case, emp):
    bits = [f"CV: {case.cv_filename or 'not provided'} ({len(case.cv_text)} chars)" ,
            f"manager: {emp.manager.full_name if emp.manager else 'unassigned'}", f"project: {emp.project.name if emp.project else 'none'}"]
    return "; ".join(bits)


def st_analysis(db, case, emp):
    plan, source = agent.run_agent(db, case, emp, run="plan")
    if not plan.get("background") and source.startswith("Rules"):  # the agent may deliberately leave it empty (e.g. CV of someone else)
        plan["background"] = A.background_rules(case.cv_text, emp)
    case.plan_json, case.plan_source = J(plan), source
    case.analysis_json = J(agent.analysis_from_plan(plan, bool(case.cv_text)))
    case.analysis_source = source
    agent.log_decisions(db, case, plan, "plan")
    ev = sum(s["status"] == "evidenced" for s in plan["skills"])
    return f"{source}: {ev} of {len(plan['skills'])} skills evidenced with quotes, {len(plan['training'])} courses, {len(plan.get('first_week_actions') or [])} first-week actions"


def _tasks_for(emp, plan) -> list[dict]:
    tasks = A.build_tasks(emp)
    for a in plan.get("first_week_actions") or []:
        tasks.append(dict(category="orientation", title=a["title"], detail=a["detail"], owner="employee", due=tasks[0]["due"] + timedelta(days=4),
                          reason=f"Suggested by the onboarding agent from company records {', '.join(a['source_ids'])}."))
    return tasks


def st_tasks(db, case, emp):
    db.query(OnboardingTask).filter_by(case_id=case.id).delete()
    tasks = _tasks_for(emp, L(case.plan_json) or {})
    for i, t in enumerate(tasks):
        db.add(OnboardingTask(case_id=case.id, category=t["category"], title=t["title"], detail=t["detail"], owner=t["owner"],
                              due_date=t["due"], reason=t["reason"], position=i))
    return f"{len(tasks)} tasks created"


def st_resp(db, case, emp):
    db.query(ResponsibilityPlan).filter_by(case_id=case.id).delete()
    db.query(TrainingAssignment).filter_by(case_id=case.id).delete()
    plan = L(case.plan_json)
    agent.apply_plan(db, case, emp, plan, keep_progress=False)
    lv = [r["support_level"] for r in plan["responsibilities"]]
    return f"{lv.count('independent')} independent, {lv.count('light-guidance')} light guidance, {lv.count('mentoring')} with mentor"


def st_training(db, case, emp):
    plan = L(case.plan_json)
    return "; ".join(f"{t['code']} ({t['priority']})" for t in plan["training"])


def st_video(db, case, emp):
    analysis = L(case.analysis_json)
    db.flush()
    resp = [dict(title=r.title, support_level=r.support_level) for r in db.query(ResponsibilityPlan).filter_by(case_id=case.id).order_by(ResponsibilityPlan.position)]
    training = [dict(course=t.course, priority=t.priority) for t in db.query(TrainingAssignment).filter_by(case_id=case.id).order_by(TrainingAssignment.position)]
    mentor = A.pick_mentor(db, emp)
    f = scriptgen.facts(db, emp, analysis, resp, training, mentor)
    script = scriptgen.baseline_script(f)
    source = "Template narration (Claude not connected)"
    if config.claude_enabled():
        try:
            script = scriptgen.claude_script(f, script)
            source = f"Claude ({llm.model()})"
        except Exception as e:  # fall back but say so
            source = f"Template narration (Claude call failed: {type(e).__name__})"
    prev = db.query(Artifact).filter_by(case_id=case.id, kind="video").count()
    rel = f"employees/{emp.id}/video_v{prev + 1}.mp4"
    out = config.STORAGE_DIR / rel
    t0 = time.time()
    info = video.render(script, out)
    info.update(render_seconds=round(time.time() - t0, 1), narration=source)
    db.query(Artifact).filter_by(case_id=case.id, kind="video").update({"is_current": False})
    db.add(Artifact(case_id=case.id, kind="video", title=f"Welcome to Rimal, {emp.full_name.split()[0]}", rel_path=rel, mime="video/mp4",
                    version=prev + 1, meta_json=J({**info, "script": [{"key": s["key"], "lines": s["lines"]} for s in script["scenes"]]})))
    return f"{info['duration']}s MP4, {info['scenes']} scenes, rendered in {info['render_seconds']}s — narration: {source}"


def st_workspace(db, case, emp):
    case.status = "ready"
    case.ready_at = datetime.utcnow()
    return "Dashboard, tasks, responsibilities, training and video published"


def send_invitation(db, emp: Employee) -> Invitation:
    """Creates (once) and delivers the invitation. A fresh temporary password is issued per delivery attempt,
    so the plaintext never needs to be stored."""
    inv = db.query(Invitation).filter_by(employee_id=emp.id).first()
    user = db.query(User).filter_by(employee_id=emp.id).first()
    if not inv:
        inv = Invitation(employee_id=emp.id, username=user.username, to_email=emp.email, view_token=secrets.token_urlsafe(24))
        db.add(inv)
        db.flush()
    if inv.status == "sent":
        return inv  # never duplicate a delivered invitation
    if not mailer.allowed(emp.email):
        inv.status, inv.detail = "blocked-not-allowlisted", "Recipient not in EMAIL_ALLOWLIST (demo safety)."
        return inv
    if not mailer.sender_configured():
        inv.status, inv.detail = "waiting-sender-config", "SMTP_USER / SMTP_PASSWORD not set in .env"
        return inv
    pw = temp_password()
    h = hash_password(pw)
    earlier = L(user.temp_hashes_json) or ([user.password_hash] if user.must_change_password and inv.sent_at else [])
    user.password_hash = h
    user.temp_hashes_json = J(earlier + [h])  # earlier emails keep working
    user.must_change_password = True
    user.temp_password_expires = datetime.utcnow() + timedelta(days=7)
    case = db.query(OnboardingCase).filter_by(employee_id=emp.id).first()
    ready = dict(tasks=db.query(OnboardingTask).filter_by(case_id=case.id).count(),
                 resp=db.query(ResponsibilityPlan).filter_by(case_id=case.id).count(),
                 courses=db.query(TrainingAssignment).filter_by(case_id=case.id).count())
    from urllib.parse import quote
    link = f"{config.APP_BASE_URL}/#/login?invite={inv.view_token}&u={quote(user.username, safe='')}"
    inv.attempts += 1
    try:
        mailer.send(mailer.build(emp.email, emp.full_name, user.username, pw, link, ready))
        inv.status, inv.sent_at, inv.detail = "sent", datetime.utcnow(), "Accepted by SMTP server (inbox delivery not guaranteed)."
    except Exception as e:
        inv.status, inv.detail = "failed", f"{type(e).__name__}: {str(e)[:200]}"
    db.commit()
    return inv


def st_invitation(db, case, emp):
    inv = send_invitation(db, emp)
    audit(db, "system", "invitation", emp.email, inv.status)
    if inv.status == "failed":
        raise RuntimeError(inv.detail)
    return {"sent": f"Sent to {inv.to_email}", "waiting-sender-config": "Prepared — waiting for email sender configuration",
            "blocked-not-allowlisted": "Prepared — recipient not allowlisted for the demo"}.get(inv.status, inv.status)


def add_stage(db, case, prefix: str, label: str, trigger: str = "") -> JobStage:
    """Queues an extra pipeline step (plan update / progress review / video refresh) after everything that exists."""
    n = db.query(JobStage).filter(JobStage.case_id == case.id, JobStage.key.like(f"{prefix}-%")).count() + 1
    pos = (db.query(JobStage.position).filter_by(case_id=case.id).order_by(JobStage.position.desc()).first() or (0,))[0] + 1
    st = JobStage(case_id=case.id, key=f"{prefix}-{n}", label=label, position=pos)
    db.add(st)
    db.flush()
    if trigger:
        db.add(AgentEvent(case_id=case.id, run=st.key, kind="trigger", text=trigger))
    return st


def _trigger(db, case, stage) -> str:
    ev = db.query(AgentEvent).filter_by(case_id=case.id, run=stage.key, kind="trigger").first()
    return ev.text if ev else ""


def st_adapt(db, case, emp, stage):
    change = _trigger(db, case, stage)
    prev = L(case.plan_json) or {}
    progress = {"responsibilities": [{"title": r.title, "status": r.status} for r in db.query(ResponsibilityPlan).filter_by(case_id=case.id)],
                "training": [{"code": t.course.code, "status": t.status} for t in db.query(TrainingAssignment).filter_by(case_id=case.id)]}
    task = (f"UPDATE the onboarding plan for {emp.full_name} ({emp.title}). What changed (entered by HR): {change}\n"
            f"Previous plan summary: {prev.get('summary', '')}\nProgress so far: {json.dumps(progress)}\n"
            "Re-check the profile, role, team and catalog as needed, then submit the complete updated plan. Keep courses the employee "
            "already started or completed where still relevant, and fill change_summary for the employee.")
    plan, source = agent.run_agent(db, case, emp, run=stage.key, task=task)
    if not plan.get("background") and source.startswith("Rules"):
        plan["background"] = prev.get("background") or A.background_rules(case.cv_text, emp)
    changes = agent.apply_plan(db, case, emp, plan, keep_progress=True)
    # tasks: rebuild for the (possibly new) role/project, keeping anything already done
    old = {t.title: t for t in db.query(OnboardingTask).filter_by(case_id=case.id)}
    keep = {k: v for k, v in old.items() if v.status != "pending"}
    db.query(OnboardingTask).filter_by(case_id=case.id, status="pending").delete()
    for i, t in enumerate(_tasks_for(emp, plan)):
        if t["title"] in keep:
            keep[t["title"]].position = i
            continue
        if t["title"] not in old:
            changes.append(f"New task: {t['title']}")
        db.add(OnboardingTask(case_id=case.id, category=t["category"], title=t["title"], detail=t["detail"], owner=t["owner"],
                              due_date=t["due"], reason=t["reason"], position=i))
    case.plan_json, case.plan_source = J(plan), source
    case.analysis_json = J(agent.analysis_from_plan(plan, bool(case.cv_text)))
    case.analysis_source = source
    agent.log_decisions(db, case, plan, stage.key)
    msg = plan.get("change_summary") or f"Your onboarding plan was updated because {change[0].lower() + change[1:] if change else 'your details changed'}."
    agent.log(db, case.id, stage.key, "plan-update", msg, {"changes": changes, "trigger": change}, employee=True)
    return f"{source}: {len(changes)} changes — " + "; ".join(changes[:4])


def st_review(db, case, emp, stage):
    trigger = _trigger(db, case, stage)
    out = agent.review_progress(db, case, emp, stage.key, trigger)
    if out.get("extra_course"):
        c = db.query(Course).filter_by(code=out["extra_course"]["code"]).first()
        if c and not db.query(TrainingAssignment).filter_by(case_id=case.id, course_id=c.id).first():
            db.add(TrainingAssignment(case_id=case.id, course_id=c.id, priority="optional", position=60,
                                      rationale=out["extra_course"]["reason"] or "Suggested by the onboarding agent after your progress."))
            out["message"] += f" I've added “{c.title}” to your training as an optional next course."
    agent.log(db, case.id, stage.key, "next-step", out["message"], {"source": out["source"], "trigger": trigger}, employee=True)
    return f"{out['source']}: {out['message'][:120]}"


def st_exercise(db, case, emp):
    existing = db.query(Exercise).filter_by(case_id=case.id).order_by(Exercise.attempt.desc()).first()
    if existing and existing.status == "open":
        return f"Exercise ready: {existing.title}"
    ex = X.design(db, case, emp, attempt=(existing.attempt + 1) if existing else 1)
    db.flush()
    agent.log(db, case.id, f"exercise-{ex.attempt}", "decision", f"Practical exercise designed for “{ex.responsibility}”: {ex.title} ({ex.source})")
    return f"{ex.title} — for “{ex.responsibility}” · {ex.source}"


def st_grade(db, case, emp, stage):
    ex = db.query(Exercise).filter_by(case_id=case.id, status="submitted").order_by(Exercise.id.desc()).first()
    if not ex:
        return "Nothing to grade"
    X.grade(db, ex)
    ex.final_score = ex.ai_score
    msg, changes = X.adapt_after(db, case, ex)
    from . import completion
    completion.check(db, case)
    agent.log(db, case.id, stage.key, "decision", f"Exercise assessed: {ex.ai_score}% ({ex.grade_source})")
    agent.log(db, case.id, stage.key, "plan-update", msg, {"changes": changes, "trigger": f"Practical exercise scored {ex.ai_score}%"}, employee=True)
    return f"{ex.ai_score}% · {ex.grade_source}" + (f" — {'; '.join(changes)}" if changes else "")


STAGE_AWARE = {"adapt": st_adapt, "review": st_review, "grade": st_grade}

HANDLERS = {"exercise": st_exercise, "record": st_record, "cv": st_cv, "analysis": st_analysis, "tasks": st_tasks, "responsibilities": st_resp,
            "training": st_training, "video": st_video, "workspace": st_workspace, "invitation": st_invitation}


# ---------------------------------------------------------------- worker
def run_next(db) -> bool:
    """Runs one pending stage of the oldest preparing case. Returns True if work was done."""
    stage = None
    for cand in (db.query(JobStage).join(OnboardingCase, OnboardingCase.id == JobStage.case_id)
                 .filter(JobStage.status == "pending").order_by(JobStage.case_id, JobStage.position)):
        blocked = db.query(JobStage).filter(JobStage.case_id == cand.case_id, JobStage.position < cand.position, JobStage.status != "done").count()
        if not blocked:  # a case waiting on a failed step (needs Retry) must not hold up other employees
            stage = cand
            break
    if not stage:
        return False
    case = db.get(OnboardingCase, stage.case_id)
    emp = db.get(Employee, case.employee_id)
    stage.status, stage.started_at, stage.attempts = "running", datetime.utcnow(), stage.attempts + 1
    db.commit()
    try:
        base = stage.key.split("-")[0]
        detail = STAGE_AWARE[base](db, case, emp, stage) if base in STAGE_AWARE else HANDLERS[base](db, case, emp)
        stage.status, stage.detail, stage.finished_at = "done", detail or "", datetime.utcnow()
        audit(db, "agent", f"stage:{stage.key}", emp.employee_code, stage.detail)
        db.commit()
    except Exception as e:
        db.rollback()
        stage = db.get(JobStage, stage.id)
        stage.status, stage.detail, stage.finished_at = "failed", f"{type(e).__name__}: {str(e)[:300]}", datetime.utcnow()
        audit(db, "agent", f"stage-failed:{stage.key}", emp.employee_code, traceback.format_exc()[-500:])
        db.commit()
    return True


def recover(db) -> None:
    db.query(JobStage).filter_by(status="running").update({"status": "pending"})
    db.commit()


_started = False


def start_worker() -> None:
    global _started
    if _started or config.DISABLE_WORKER:
        return
    _started = True

    def loop():
        db = SessionLocal()
        recover(db)
        db.close()
        last_grad = 0.0
        while True:
            db = SessionLocal()
            try:
                worked = run_next(db)
            except Exception:
                traceback.print_exc()
                worked = False
            finally:
                db.close()
            if not worked:
                time.sleep(1.0)
                if time.time() - last_grad > 60:  # move completed hires to existing employees when their time is up
                    last_grad = time.time()
                    gdb = SessionLocal()
                    try:
                        from . import completion
                        completion.graduate_due(gdb)
                    except Exception:
                        traceback.print_exc()
                    finally:
                        gdb.close()

    threading.Thread(target=loop, daemon=True, name="onboarding-worker").start()
