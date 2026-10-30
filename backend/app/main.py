from datetime import date, datetime
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from . import chat, completion, config, pipeline, seed
from .auth import (COOKIE, create_session, current_user, drop_session, hash_password, require_employee, require_hr, verify_password)
from .cvtext import extract_text
from .db import get_db
from .models import (AgentEvent, Artifact, ChatMessage, CompanyDocument, CompanyEmail, Exercise, Course, Department, Employee, Invitation, JobStage, OnboardingCase, OnboardingTask,
                     Project, ResponsibilityPlan, Role, TrainingAssignment, User, audit, JSONMixin)

J, L = JSONMixin.dump, JSONMixin.load
app = FastAPI(title=f"{config.PRODUCT_NAME} API")


@app.on_event("startup")
def _startup():
    seed.run()
    pipeline.start_worker()


@app.get("/api/health")
def health():
    return {"ok": True, "product": config.PRODUCT_NAME, "claude": config.claude_enabled(), "model": config.ANTHROPIC_MODEL if config.claude_enabled() else None,
            "email_sender": __import__("app.mailer", fromlist=["x"]).sender_configured()}


# ---------------------------------------------------------------- auth
class LoginIn(BaseModel):
    username: str
    password: str


def user_out(u: User):
    e = u.employee
    return {"id": u.id, "username": u.username, "kind": u.kind, "must_change_password": u.must_change_password,
            "name": e.full_name if e else u.username, "title": e.title if e else ""}


@app.post("/api/auth/login")
def login(body: LoginIn, response: Response, db: Session = Depends(get_db)):
    u = db.query(User).filter(User.username == body.username.strip().lower()).first()
    pw = body.password.strip()  # copy-paste from email often adds spaces
    ok = bool(u and u.is_active) and (verify_password(pw, u.password_hash) or verify_password(body.password, u.password_hash)
                                      or (u.must_change_password and any(verify_password(pw, h) for h in (L(u.temp_hashes_json) or []))))
    if not ok:
        # Tell the person which kind of account this is, so they know which password to use.
        if not u or not u.is_active:
            msg = "We couldn't find an account with this email. New employees: use the email address your invitation was sent to."
        elif u.kind == "hr":
            msg = "Incorrect password for this HR account. Check capital letters and symbols."
        elif u.must_change_password:
            msg = ("That's not the temporary password from your invitation email. Copy it exactly as shown "
                   "(letters, numbers and dashes) — or ask HR to resend your invitation.")
        else:
            msg = "Incorrect password. Use the password you chose when you first signed in."
        raise HTTPException(401, msg)
    if u.must_change_password and u.temp_password_expires and u.temp_password_expires < datetime.utcnow():
        raise HTTPException(401, "Your temporary password has expired. Ask HR to resend your invitation.")
    u.last_login_at = datetime.utcnow()
    if u.kind == "employee":
        inv = db.query(Invitation).filter_by(employee_id=u.employee_id).first()
        if inv and not inv.first_login_at:
            inv.first_login_at = datetime.utcnow()
    audit(db, u.username, "login")
    token = create_session(db, u)
    response.set_cookie(COOKIE, token, httponly=True, samesite="lax", max_age=12 * 3600, secure=config.COOKIE_SECURE)
    return user_out(u)


@app.post("/api/auth/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    drop_session(db, request.cookies.get(COOKIE))
    response.delete_cookie(COOKIE)
    return {"ok": True}


@app.get("/api/auth/me")
def me(user: User = Depends(current_user)):
    return user_out(user)


class PwIn(BaseModel):
    current: str
    new: str


@app.post("/api/auth/change-password")
def change_password(body: PwIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    cur = body.current.strip()
    if not (verify_password(cur, user.password_hash) or verify_password(body.current, user.password_hash)
            or (user.must_change_password and any(verify_password(cur, h) for h in (L(user.temp_hashes_json) or [])))):
        raise HTTPException(400, "Current password is incorrect")
    if len(body.new) < 10 or body.new == body.current:
        raise HTTPException(400, "New password must be at least 10 characters and different from the current one")
    user = db.get(User, user.id)
    user.password_hash = hash_password(body.new)
    user.must_change_password = False
    user.temp_password_expires = None
    user.temp_hashes_json = "[]"  # emailed temporary passwords stop working once the employee sets their own
    if user.employee_id:
        inv = db.query(Invitation).filter_by(employee_id=user.employee_id).first()
        if inv:
            inv.password_changed_at = datetime.utcnow()
    audit(db, user.username, "password-changed")
    db.commit()
    return user_out(user)


class ViewIn(BaseModel):
    token: str


@app.post("/api/invitations/viewed")
def invitation_viewed(body: ViewIn, db: Session = Depends(get_db)):
    inv = db.query(Invitation).filter_by(view_token=body.token).first()
    if inv and not inv.viewed_at:
        inv.viewed_at = datetime.utcnow()
        db.commit()
    return {"ok": True}  # reveals nothing either way


# ---------------------------------------------------------------- HR
@app.get("/api/hr/options")
def hr_options(_: User = Depends(require_hr), db: Session = Depends(get_db)):
    return {
        "departments": [{"id": d.id, "name": d.name} for d in db.query(Department).order_by(Department.name)],
        "roles": [{"id": r.id, "title": r.title, "department_id": r.department_id} for r in db.query(Role)],
        "managers": [{"id": e.id, "name": e.full_name, "title": e.title, "department_id": e.department_id}
                     for e in db.query(Employee).filter(Employee.is_new_hire == False).order_by(Employee.full_name)],  # noqa: E712
        "projects": [{"id": p.id, "name": p.name, "code": p.code} for p in db.query(Project)],
    }


@app.post("/api/hr/employees")
async def hr_create_employee(
    employee_code: str = Form(...), full_name: str = Form(...), email: str = Form(...), role_id: int = Form(...),
    department_id: int = Form(...), manager_id: int = Form(...), start_date: date = Form(...), project_id: int | None = Form(None),
    experience_years: int | None = Form(None), experience_text: str = Form(""), qualifications: str = Form(""), extra_context: str = Form(""), responsibilities_text: str = Form(""),
    cv: UploadFile | None = File(None), hr: User = Depends(require_hr), db: Session = Depends(get_db),
):
    email = email.strip().lower()
    if "@" not in email:
        raise HTTPException(422, "Enter a valid email address")
    if db.query(Employee).filter((Employee.employee_code == employee_code.strip()) | (Employee.email == email)).first():
        raise HTTPException(409, "An employee with this ID or email already exists")
    role = db.get(Role, role_id)
    if not role or not db.get(Department, department_id) or not db.get(Employee, manager_id):
        raise HTTPException(422, "Unknown role, department or manager")
    cv_name, cv_text, cv_bytes = "", "", b""
    if cv and cv.filename:
        if not cv.filename.lower().endswith((".pdf", ".docx", ".txt", ".md")):
            raise HTTPException(422, "CV must be PDF, DOCX or TXT")
        cv_bytes = await cv.read()
        if len(cv_bytes) > 5 * 1024 * 1024:
            raise HTTPException(422, "CV must be under 5 MB")
        cv_name = Path(cv.filename).name
        cv_text = extract_text(cv_name, cv_bytes)
    emp = Employee(employee_code=employee_code.strip(), full_name=full_name.strip(), email=email, title=role.title, role_id=role.id,
                   department_id=department_id, manager_id=manager_id, project_id=project_id or None, start_date=start_date, is_new_hire=True,
                   experience_years=experience_years, experience_text=experience_text, qualifications=qualifications, extra_context=extra_context,
                   responsibilities_text=responsibilities_text)
    db.add(emp)
    db.flush()
    import secrets
    db.add(User(username=email, password_hash=hash_password(secrets.token_urlsafe(24)), kind="employee", employee_id=emp.id, must_change_password=True))
    case = OnboardingCase(employee_id=emp.id, cv_filename=cv_name, cv_text=cv_text)
    db.add(case)
    db.flush()
    if cv_bytes:
        rel = f"employees/{emp.id}/cv_{cv_name}"
        p = config.STORAGE_DIR / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(cv_bytes)
        db.add(Artifact(case_id=case.id, kind="cv", title=cv_name, rel_path=rel, mime=cv.content_type or "application/octet-stream"))
    pipeline.create_stages(db, case)
    audit(db, hr.username, "employee-created", emp.employee_code, emp.full_name)
    db.commit()
    return {"employee_id": emp.id, "case_id": case.id}


def progress(db, case: OnboardingCase | None) -> dict:
    if not case:
        return {}
    tasks = db.query(OnboardingTask).filter_by(case_id=case.id).all()
    tr = db.query(TrainingAssignment).filter_by(case_id=case.id).all()
    rs = db.query(ResponsibilityPlan).filter_by(case_id=case.id).all()
    # percent = what's REQUIRED to complete onboarding: tasks, responsibilities, mandatory course(s), practical exercise.
    # Optional courses are shown in the training bar but don't hold anyone back.
    mand = [t for t in tr if t.priority == "mandatory"]
    ex = db.query(Exercise).filter_by(case_id=case.id).order_by(Exercise.id.desc()).first()
    total = len(tasks) + len(rs) + len(mand) + (1 if ex else 0)
    done = (sum(t.status in ("submitted", "verified") for t in tasks) + sum(r.status == "done" for r in rs)
            + sum(t.status == "completed" for t in mand) + (1 if ex and ex.status == "assessed" else 0))
    overdue = sum(t.status == "pending" and t.due_date and t.due_date < date.today() for t in tasks)
    return {"tasks_total": len(tasks), "tasks_done": sum(t.status in ("submitted", "verified") for t in tasks), "tasks_verified": sum(t.status == "verified" for t in tasks),
            "tasks_awaiting_verification": sum(t.status == "submitted" for t in tasks), "overdue": overdue,
            "training_total": len(tr), "training_done": sum(t.status == "completed" for t in tr), "mandatory_open": sum(t.priority == "mandatory" and t.status != "completed" for t in tr),
            "resp_total": len(rs), "resp_done": sum(r.status == "done" for r in rs), "percent": round(100 * done / total) if total else 0}


def events_out(db, case_id, limit=200, employee_only=False):
    q = db.query(AgentEvent).filter(AgentEvent.case_id == case_id, AgentEvent.kind != "trigger")
    if employee_only:
        q = q.filter(AgentEvent.visible_to_employee == True)  # noqa: E712
    rows = q.order_by(AgentEvent.id.desc()).limit(limit).all()[::-1]
    return [{"id": e.id, "run": e.run, "kind": e.kind, "text": e.text, "data": L(e.data_json), "at": e.at} for e in rows]


def stages_out(db, case_id):
    return [{"key": s.key, "label": s.label, "status": s.status, "detail": s.detail, "attempts": s.attempts,
             "started_at": s.started_at, "finished_at": s.finished_at}
            for s in db.query(JobStage).filter_by(case_id=case_id).order_by(JobStage.position)]


@app.get("/api/hr/overview")
def hr_overview(_: User = Depends(require_hr), db: Session = Depends(get_db)):
    emps = db.query(Employee).all()
    hires = []
    for e in [x for x in emps if x.is_new_hire]:
        case = db.query(OnboardingCase).filter_by(employee_id=e.id).first()
        inv = db.query(Invitation).filter_by(employee_id=e.id).first()
        st = db.query(JobStage).filter_by(case_id=case.id).all() if case else []
        hires.append({"id": e.id, "code": e.employee_code, "name": e.full_name, "title": e.title, "department": e.department.name,
                      "manager": e.manager.full_name if e.manager else None, "start_date": e.start_date, "case_id": case.id if case else None,
                      "case_status": "failed" if any(s.status == "failed" for s in st) else (case.status if case else None),
                      "completed_at": case.completed_at if case else None,
                      "graduates_on": completion.graduates_on(case) if case else None,
                      "stages_done": sum(s.status == "done" for s in st), "stages_total": len(st),
                      "invitation": inv.status if inv else None, "first_login": inv.first_login_at if inv else None, "progress": progress(db, case)})
    hires.sort(key=lambda h: h["id"], reverse=True)
    notices = [{"case_id": c.id, "employee_id": c.employee_id, "name": c.employee.full_name, "completed_at": c.completed_at,
                "graduates_on": completion.graduates_on(c)}
               for c in db.query(OnboardingCase).filter(OnboardingCase.completed_at.isnot(None), OnboardingCase.completion_seen == False,  # noqa: E712
                                                        OnboardingCase.graduated_at.is_(None))]
    return {"total_employees": len(emps), "new_hires": len(hires), "existing": len(emps) - len(hires),
            "ready": sum(h["case_status"] == "ready" for h in hires), "completed": sum(h["case_status"] == "completed" for h in hires),
            "notices": notices, "graduate_days": config.GRADUATE_DAYS, "preparing": sum(h["case_status"] == "preparing" for h in hires),
            "failed": sum(h["case_status"] == "failed" for h in hires),
            "awaiting_verification": sum(h["progress"].get("tasks_awaiting_verification", 0) for h in hires), "hires": hires,
            "existing_employees": [{"id": e.id, "code": e.employee_code, "name": e.full_name, "title": e.title, "department": e.department.name}
                                   for e in emps if not e.is_new_hire]}


@app.get("/api/hr/cases/{case_id}")
def hr_case(case_id: int, _: User = Depends(require_hr), db: Session = Depends(get_db)):
    case = db.get(OnboardingCase, case_id) or _404()
    inv = db.query(Invitation).filter_by(employee_id=case.employee_id).first()
    return {"case_id": case.id, "status": case.status, "employee": {"id": case.employee.id, "name": case.employee.full_name, "title": case.employee.title, "email": case.employee.email},
            "stages": stages_out(db, case.id), "invitation": inv_out(inv) if inv else None,
            "agent": events_out(db, case.id, limit=80), "plan_source": case.plan_source}


@app.post("/api/hr/cases/{case_id}/retry")
def hr_retry(case_id: int, hr: User = Depends(require_hr), db: Session = Depends(get_db)):
    n = db.query(JobStage).filter_by(case_id=case_id, status="failed").update({"status": "pending", "detail": "Retry requested"})
    audit(db, hr.username, "retry", str(case_id))
    db.commit()
    return {"retried": n}


def _404():
    raise HTTPException(404, "Not found")


@app.get("/api/hr/employees/{emp_id}")
def hr_employee(emp_id: int, _: User = Depends(require_hr), db: Session = Depends(get_db)):
    e = db.get(Employee, emp_id) or _404()
    case = db.query(OnboardingCase).filter_by(employee_id=e.id).first()
    out = {"profile": emp_out(e) | {"role_id": e.role_id, "department_id": e.department_id, "manager_id": e.manager_id,
                                    "project_id": e.project_id, "experience_years": e.experience_years, "experience_text": e.experience_text, "qualifications": e.qualifications,
                                    "extra_context": e.extra_context, "responsibilities_text": e.responsibilities_text, "is_new_hire": e.is_new_hire}}
    if case:
        out |= {"case_id": case.id, "status": case.status, "cv_filename": case.cv_filename, "analysis": L(case.analysis_json), "analysis_source": case.analysis_source,
                "plan_source": case.plan_source, "agent": events_out(db, case.id), "exercise": exercise_out(db, case, for_employee=False),
                "completed_at": case.completed_at, "graduated_at": case.graduated_at, "graduates_on": completion.graduates_on(case),
                "requirements": completion.requirements(db, case),
                "stages": stages_out(db, case.id), "progress": progress(db, case), **workspace(db, case)}
        inv = db.query(Invitation).filter_by(employee_id=e.id).first()
        out["invitation"] = inv_out(inv) if inv else None
    return out


@app.post("/api/hr/employees/{emp_id}/update")
async def hr_update_employee(
    emp_id: int, role_id: int | None = Form(None), department_id: int | None = Form(None), manager_id: int | None = Form(None),
    project_id: str | None = Form(None), start_date: date | None = Form(None), experience_years: str | None = Form(None),
    experience_text: str | None = Form(None), qualifications: str | None = Form(None), responsibilities_text: str | None = Form(None),
    extra_context: str | None = Form(None), cv: UploadFile | None = File(None), hr: User = Depends(require_hr), db: Session = Depends(get_db),
):
    """HR changes a new hire's details. Plan-relevant changes make the onboarding agent re-plan (keeping progress)
    and refresh the welcome video."""
    e = db.get(Employee, emp_id) or _404()
    case = db.query(OnboardingCase).filter_by(employee_id=e.id).first() or _404()
    changes, plan_relevant = [], False

    def name_of(model, id_, attr):
        obj = db.get(model, id_) if id_ else None
        return getattr(obj, attr) if obj else "none"

    if role_id and role_id != e.role_id:
        r = db.get(Role, role_id) or _404()
        changes.append(f"role changed from {e.title} to {r.title}")
        e.role_id, e.title, plan_relevant = r.id, r.title, True
    if department_id and department_id != e.department_id:
        changes.append(f"department changed to {name_of(Department, department_id, 'name')}")
        e.department_id = department_id
    if manager_id and manager_id != e.manager_id:
        changes.append(f"manager changed from {name_of(Employee, e.manager_id, 'full_name')} to {name_of(Employee, manager_id, 'full_name')}")
        e.manager_id, plan_relevant = manager_id, True
    if project_id is not None:
        pid = int(project_id) if project_id.strip() else None
        if pid != e.project_id:
            changes.append(f"project changed from {name_of(Project, e.project_id, 'name')} to {name_of(Project, pid, 'name')}")
            e.project_id, plan_relevant = pid, True
    if start_date and start_date != e.start_date:
        changes.append(f"start date changed to {start_date}")
        e.start_date = start_date
    if experience_years is not None:
        y = int(experience_years) if experience_years.strip().isdigit() else None
        if y != e.experience_years:
            changes.append("years of experience updated")
            e.experience_years = y
    for field, label in (("experience_text", "previous experience"), ("qualifications", "qualifications & skills"),
                         ("responsibilities_text", "key responsibilities"), ("extra_context", "additional context")):
        val = locals()[field]
        norm = lambda x: "\n".join(l.rstrip() for l in (x or "").replace("\r\n", "\n").strip().split("\n"))  # browsers send \r\n
        if val is not None and norm(val) != norm(getattr(e, field)):
            val = norm(val)
            changes.append(f"{label} updated")
            setattr(e, field, val)
            plan_relevant = True
    if cv and cv.filename:
        if not cv.filename.lower().endswith((".pdf", ".docx", ".txt", ".md")):
            raise HTTPException(422, "CV must be PDF, DOCX or TXT")
        data = await cv.read()
        if len(data) > 5 * 1024 * 1024:
            raise HTTPException(422, "CV must be under 5 MB")
        name = Path(cv.filename).name
        case.cv_filename, case.cv_text = name, extract_text(name, data)
        rel = f"employees/{e.id}/cv_{name}"
        (config.STORAGE_DIR / rel).parent.mkdir(parents=True, exist_ok=True)
        (config.STORAGE_DIR / rel).write_bytes(data)
        db.add(Artifact(case_id=case.id, kind="cv", title=name, rel_path=rel, mime=cv.content_type or "application/octet-stream"))
        changes.append("a new CV was uploaded")
        plan_relevant = True
    if not changes:
        return {"changed": False, "case_id": case.id}
    audit(db, hr.username, "employee-updated", e.employee_code, "; ".join(changes))
    trigger = "; ".join(changes)
    if plan_relevant:
        pipeline.add_stage(db, case, "adapt", f"Agent re-plans: {trigger[:120]}", trigger=trigger[0].upper() + trigger[1:])
        pipeline.add_stage(db, case, "video", "Welcome video refreshed for the changes")
    db.commit()
    return {"changed": True, "replanning": plan_relevant, "changes": changes, "case_id": case.id}


@app.delete("/api/hr/employees/{emp_id}")
def hr_delete_employee(emp_id: int, hr: User = Depends(require_hr), db: Session = Depends(get_db)):
    """Removes a new hire and everything generated for them (records, files, login, invitation, chat)."""
    import shutil
    from .models import AuthSession
    e = db.get(Employee, emp_id) or _404()
    if not e.is_new_hire:
        raise HTTPException(409, "Only new hires added through onboarding can be deleted here")
    case = db.query(OnboardingCase).filter_by(employee_id=e.id).first()
    if case and db.query(JobStage).filter_by(case_id=case.id, status="running").count():
        raise HTTPException(409, "A preparation step is running right now — try again in a minute")
    users = db.query(User).filter_by(employee_id=e.id).all()
    for u in users:
        db.query(AuthSession).filter_by(user_id=u.id).delete()
        db.query(ChatMessage).filter_by(user_id=u.id).delete()
        db.delete(u)
    if case:
        for model in (Exercise, AgentEvent, JobStage, OnboardingTask, ResponsibilityPlan, TrainingAssignment, Artifact):
            db.query(model).filter_by(case_id=case.id).delete()
        db.delete(case)
    db.query(Invitation).filter_by(employee_id=e.id).delete()
    db.query(Employee).filter_by(manager_id=e.id).update({"manager_id": None})
    name, code = e.full_name, e.employee_code
    db.delete(e)
    audit(db, hr.username, "employee-deleted", code, name)
    db.commit()
    folder = (config.STORAGE_DIR / "employees" / str(emp_id)).resolve()
    if str(folder).startswith(str(config.STORAGE_DIR.resolve())) and folder.exists():
        shutil.rmtree(folder)
    return {"deleted": True, "name": name}


@app.post("/api/hr/cases/{case_id}/ack")
def hr_ack_completion(case_id: int, _: User = Depends(require_hr), db: Session = Depends(get_db)):
    case = db.get(OnboardingCase, case_id) or _404()
    case.completion_seen = True
    db.commit()
    return {"ok": True}


@app.post("/api/hr/employees/{emp_id}/graduate")
def hr_graduate(emp_id: int, hr: User = Depends(require_hr), db: Session = Depends(get_db)):
    case = db.query(OnboardingCase).filter_by(employee_id=emp_id).first() or _404()
    if not case.completed_at:
        raise HTTPException(409, "Onboarding isn't complete yet")
    if not case.graduated_at:
        completion.graduate(db, case, hr.username)
        case.completion_seen = True
    db.commit()
    return {"ok": True}


@app.post("/api/hr/tasks/{task_id}/verify")
def hr_verify(task_id: int, hr: User = Depends(require_hr), db: Session = Depends(get_db)):
    t = db.get(OnboardingTask, task_id) or _404()
    t.status, t.verified_at = "verified", datetime.utcnow()
    audit(db, hr.username, "task-verified", str(task_id), t.title)
    completion.check(db, db.get(OnboardingCase, t.case_id))
    db.commit()
    return {"ok": True}


def inv_out(i: Invitation):
    return {"id": i.id, "employee_id": i.employee_id, "name": i.employee.full_name, "title": i.employee.title, "to": i.to_email, "username": i.username,
            "status": i.status, "detail": i.detail, "attempts": i.attempts, "created_at": i.created_at, "sent_at": i.sent_at, "viewed_at": i.viewed_at,
            "first_login_at": i.first_login_at, "password_changed_at": i.password_changed_at}


@app.get("/api/hr/invitations")
def hr_invitations(_: User = Depends(require_hr), db: Session = Depends(get_db)):
    return [inv_out(i) for i in db.query(Invitation).order_by(Invitation.id.desc())]


@app.get("/api/hr/email-check")
def hr_email_check(_: User = Depends(require_hr)):
    """Diagnoses the sender settings and tries a Gmail sign-in WITHOUT sending anything. Never returns the password."""
    import os
    import re as _re
    import smtplib
    user = os.environ.get("SMTP_USER", config.SMTP_USER) or ""
    raw = os.environ.get("SMTP_PASSWORD", config.SMTP_PASSWORD) or ""
    pw = raw.replace(" ", "")
    out = {"smtp_user": user, "user_has_spaces_or_quotes": user != user.strip().strip('"').strip("'"),
           "password_set": bool(pw), "password_length_without_spaces": len(pw),
           "password_looks_like_app_password": bool(_re.fullmatch(r"[a-z]{16}", pw)),
           "password_has_quotes": raw.strip()[:1] in "\"'" if raw.strip() else False,
           "smtp_host": os.environ.get("SMTP_HOST", config.SMTP_HOST), "smtp_port": int(os.environ.get("SMTP_PORT", config.SMTP_PORT))}
    try:
        with smtplib.SMTP(out["smtp_host"], out["smtp_port"], timeout=20) as s:
            s.ehlo(); s.starttls(); s.ehlo()
            s.user, s.password = user, pw
            s.auth("PLAIN", s.auth_plain, initial_response_ok=True)
        out["gmail_login"] = "OK — Gmail accepted the sign-in"
    except smtplib.SMTPAuthenticationError as e:
        out["gmail_login"] = f"REJECTED ({e.smtp_code}): {e.smtp_error.decode(errors='ignore')[:160]}"
    except Exception as e:
        out["gmail_login"] = f"ERROR: {type(e).__name__}: {str(e)[:160]}"
    return out


@app.post("/api/hr/invitations/{inv_id}/resend")
def hr_resend(inv_id: int, hr: User = Depends(require_hr), db: Session = Depends(get_db)):
    inv = db.get(Invitation, inv_id) or _404()
    if inv.first_login_at and inv.password_changed_at:
        raise HTTPException(409, "Employee has already activated their account")
    inv.status = "prepared"
    db.commit()
    inv = pipeline.send_invitation(db, inv.employee)
    audit(db, hr.username, "invitation-resend", inv.to_email, inv.status)
    db.commit()
    return inv_out(inv)


@app.get("/api/hr/employees/{emp_id}/video")
def hr_video(emp_id: int, _: User = Depends(require_hr), db: Session = Depends(get_db)):
    case = db.query(OnboardingCase).filter_by(employee_id=emp_id).first() or _404()
    return _video_file(db, case)


# ---------------------------------------------------------------- employee workspace
def emp_out(e: Employee):
    return {"id": e.id, "code": e.employee_code, "name": e.full_name, "first_name": e.full_name.split()[0], "email": e.email, "title": e.title,
            "department": e.department.name, "start_date": e.start_date,
            "manager": {"name": e.manager.full_name, "title": e.manager.title, "email": e.manager.email} if e.manager else None,
            "project": {"code": e.project.code, "name": e.project.name, "client": e.project.client, "phase": e.project.phase, "background": e.project.background,
                        "objectives": L(e.project.objectives_json)} if e.project else None}


def workspace(db, case):
    v = db.query(Artifact).filter_by(case_id=case.id, kind="video", is_current=True).first()
    return {
        "video": {"id": v.id, "title": v.title, "version": v.version, "created_at": v.created_at, "meta": {k: x for k, x in L(v.meta_json).items() if k != "script"},
                  "script": L(v.meta_json).get("script")} if v else None,
        "tasks": [{"id": t.id, "category": t.category, "title": t.title, "detail": t.detail, "owner": t.owner, "due_date": t.due_date, "status": t.status,
                   "reason": t.reason, "submitted_at": t.submitted_at, "verified_at": t.verified_at}
                  for t in db.query(OnboardingTask).filter_by(case_id=case.id).order_by(OnboardingTask.position)],
        "responsibilities": [{"id": r.id, "title": r.title, "detail": r.detail, "support_level": r.support_level, "rationale": r.rationale, "status": r.status,
                              "evidence": L(r.evidence_json), "mentor": {"name": r.mentor.full_name, "title": r.mentor.title, "email": r.mentor.email} if r.mentor else None}
                             for r in db.query(ResponsibilityPlan).filter_by(case_id=case.id).order_by(ResponsibilityPlan.position)],
        "training": [{"id": t.id, "code": t.course.code, "title": t.course.title, "provider": t.course.provider, "description": t.course.description,
                      "level": t.course.level, "hours": t.course.hours, "external": t.course.external, "url": t.course.url, "web_found": t.course.code.startswith("WEB-"), "priority": t.priority, "rationale": t.rationale, "status": t.status, "completed_at": t.completed_at}
                     for t in db.query(TrainingAssignment).filter_by(case_id=case.id).order_by(TrainingAssignment.position)],
    }


def exercise_out(db, case, for_employee: bool = True):
    ex = db.query(Exercise).filter_by(case_id=case.id).order_by(Exercise.id.desc()).first()
    if not ex:
        return None
    r = db.query(ResponsibilityPlan).filter_by(case_id=case.id, title=ex.responsibility).first()
    out = {"id": ex.id, "attempt": ex.attempt, "responsibility": ex.responsibility, "title": ex.title, "scenario": ex.scenario,
           "worksheet": L(ex.worksheet_json), "task": ex.task, "deliverable": ex.deliverable, "minutes": ex.minutes,
           "rubric": L(ex.rubric_json), "sources": L(ex.sources_json), "source": ex.source, "status": ex.status, "answer": ex.answer,
           "score": ex.final_score, "feedback": ex.ai_feedback, "breakdown": L(ex.ai_breakdown_json) if ex.status == "assessed" else None,
           "grade_source": ex.grade_source, "submitted_at": ex.submitted_at, "mentor_review_requested": ex.mentor_review_requested,
           "mentor": r.mentor.full_name if r and r.mentor else (case.employee.manager.full_name if case.employee.manager else None)}
    out["materials"] = exercise_materials(db, case.employee, ex)
    return out  # the answer key is never included


def exercise_materials(db, emp, ex) -> list[dict]:
    """The emails/documents the exercise cites, so a new hire doesn't have to search for them.
    Only records the employee is allowed to see (company-wide + their project)."""
    import re as _re
    ids = list(dict.fromkeys(L(ex.sources_json) + _re.findall(r"\b([ED]\d+)\b", f"{ex.scenario} {ex.task} {ex.worksheet_json}")))
    proj = emp.project_id
    out = []
    for rid in ids:
        kind, num = rid[0], int(rid[1:])
        if kind == "E":
            e = db.get(CompanyEmail, num)
            if e and (e.project_id is None or e.project_id == proj):
                out.append({"id": rid, "type": "email", "title": e.subject, "from": chat._first_name(db, e.sender), "to": e.recipients,
                            "date": e.sent_at.strftime("%d %b %Y"), "body": e.body, "location": chat.record_location("email", e.project, when=e.sent_at)})
        else:
            d = db.get(CompanyDocument, num)
            if d and (d.project_id is None or d.project_id == proj):
                out.append({"id": rid, "type": d.kind, "title": d.title, "from": None, "to": None, "date": None, "body": d.body,
                            "location": chat.record_location("document", d.project, d.kind)})
    return out


def my_case(db, user: User) -> OnboardingCase:
    case = db.query(OnboardingCase).filter_by(employee_id=user.employee_id).first()
    if not case:
        raise HTTPException(404, "No onboarding case")
    return case


@app.get("/api/me/workspace")
def my_workspace(user: User = Depends(require_employee), db: Session = Depends(get_db)):
    case = my_case(db, user)
    a = L(case.analysis_json) or {}
    return {"employee": emp_out(user.employee), "status": case.status, "progress": progress(db, case),
            "skills": {"evidenced": a.get("evidenced", []), "unverified": a.get("unverified", []), "note": a.get("note")},
            "updates": events_out(db, case.id, limit=6, employee_only=True)[::-1],
            "exercise": exercise_out(db, case),
            "completed_at": case.completed_at,
            "agent_working": db.query(JobStage).filter(JobStage.case_id == case.id, JobStage.status.in_(["pending", "running"]),
                                                       JobStage.key.like("review-%") | JobStage.key.like("adapt-%") | JobStage.key.like("grade-%")
                                                       | JobStage.key.like("exercise%")).count() > 0,
            **workspace(db, case)}


@app.post("/api/me/tasks/{task_id}/{action}")
def my_task(task_id: int, action: str, user: User = Depends(require_employee), db: Session = Depends(get_db)):
    case = my_case(db, user)
    t = db.get(OnboardingTask, task_id)
    if not t or t.case_id != case.id:
        raise HTTPException(404, "Not found")
    if t.status == "verified":
        raise HTTPException(409, "Already verified by HR")
    if action == "submit":
        t.status, t.submitted_at = "submitted", datetime.utcnow()
    elif action == "undo":
        t.status, t.submitted_at = "pending", None
    else:
        raise HTTPException(400, "Unknown action")
    completion.check(db, case)
    db.commit()
    return {"ok": True, "status": t.status}


class StatusIn(BaseModel):
    status: str


@app.post("/api/me/training/{tid}")
def my_training(tid: int, body: StatusIn, user: User = Depends(require_employee), db: Session = Depends(get_db)):
    case = my_case(db, user)
    t = db.get(TrainingAssignment, tid)
    if not t or t.case_id != case.id or body.status not in ("not-started", "in-progress", "completed"):
        raise HTTPException(404, "Not found")
    was = t.status
    t.status = body.status
    t.completed_at = datetime.utcnow() if body.status == "completed" else None
    if body.status == "completed" and was != "completed":
        _queue_review(db, case, f"Completed the course “{t.course.title}”")
    completion.check(db, case)
    db.commit()
    return {"ok": True}


def _queue_review(db, case, trigger: str) -> None:
    """The agent reviews progress after something is completed (one review queued at a time)."""
    busy = db.query(JobStage).filter(JobStage.case_id == case.id, JobStage.key.like("review-%"), JobStage.status.in_(["pending", "running"])).count()
    if not busy:
        pipeline.add_stage(db, case, "review", f"Agent reviews progress: {trigger[:100]}", trigger=trigger)


@app.post("/api/me/responsibilities/{rid}")
def my_resp(rid: int, body: StatusIn, user: User = Depends(require_employee), db: Session = Depends(get_db)):
    case = my_case(db, user)
    r = db.get(ResponsibilityPlan, rid)
    if not r or r.case_id != case.id or body.status not in ("not-started", "in-progress", "done"):
        raise HTTPException(404, "Not found")
    was = r.status
    r.status = body.status
    if body.status == "done" and was != "done":
        _queue_review(db, case, f"Finished the responsibility “{r.title}”")
    completion.check(db, case)
    db.commit()
    return {"ok": True}


class AnswerIn(BaseModel):
    answer: str


def _ensure_exercise(db, case):
    """Hires prepared before exercises existed get one queued the first time they open the tab."""
    if case.status == "ready" and not db.query(Exercise).filter_by(case_id=case.id).first() and not db.query(JobStage).filter(
            JobStage.case_id == case.id, JobStage.key.like("exercise%"), JobStage.status.in_(["pending", "running"])).count():
        pipeline.add_stage(db, case, "exercise", "Agent designs a practical exercise")
        db.commit()


@app.get("/api/me/exercise")
def my_exercise(user: User = Depends(require_employee), db: Session = Depends(get_db)):
    case = my_case(db, user)
    _ensure_exercise(db, case)
    busy = db.query(JobStage).filter(JobStage.case_id == case.id, JobStage.status.in_(["pending", "running"]),
                                     JobStage.key.like("exercise%") | JobStage.key.like("grade-%")).count() > 0
    return {"exercise": exercise_out(db, case), "working": busy}


@app.post("/api/me/exercise/submit")
def my_exercise_submit(body: AnswerIn, user: User = Depends(require_employee), db: Session = Depends(get_db)):
    case = my_case(db, user)
    ex = db.query(Exercise).filter_by(case_id=case.id, status="open").order_by(Exercise.id.desc()).first() or _404()
    text = body.answer.strip()
    if len(text) < 20:
        raise HTTPException(422, "Please write a little more before submitting.")
    ex.answer, ex.status, ex.submitted_at = text[:8000], "submitted", datetime.utcnow()
    pipeline.add_stage(db, case, "grade", f"Agent assesses the practical exercise (attempt {ex.attempt})")
    db.commit()
    return {"ok": True}


@app.post("/api/me/exercise/retry")
def my_exercise_retry(user: User = Depends(require_employee), db: Session = Depends(get_db)):
    case = my_case(db, user)
    last = db.query(Exercise).filter_by(case_id=case.id).order_by(Exercise.id.desc()).first() or _404()
    if last.status != "assessed":
        raise HTTPException(409, "Finish the current exercise first.")
    pipeline.add_stage(db, case, "exercise", f"Agent designs a new practical exercise (attempt {last.attempt + 1})")
    db.commit()
    return {"ok": True}


@app.post("/api/me/exercise/review-request")
def my_exercise_review(user: User = Depends(require_employee), db: Session = Depends(get_db)):
    case = my_case(db, user)
    ex = db.query(Exercise).filter_by(case_id=case.id, status="assessed").order_by(Exercise.id.desc()).first() or _404()
    if not ex.mentor_review_requested:
        ex.mentor_review_requested = True
        who = exercise_out(db, case)["mentor"] or "your mentor"
        n = db.query(OnboardingTask).filter_by(case_id=case.id).count()
        db.add(OnboardingTask(case_id=case.id, category="orientation", title=f"Go through your practical exercise with {who}",
                              detail=f"You asked for a review of “{ex.title}” ({ex.final_score}%).", owner="employee",
                              due_date=date.today(), reason="Requested by you after the AI assessment.", position=n))
    db.commit()
    return {"ok": True}


@app.get("/api/me/courses/{code}")
def my_course(code: str, user: User = Depends(require_employee), db: Session = Depends(get_db)):
    case = my_case(db, user)
    c = db.query(Course).filter_by(code=code).first()
    if not c or not db.query(TrainingAssignment).filter_by(case_id=case.id, course_id=c.id).first():
        raise HTTPException(404, "Not found")
    return {"code": c.code, "title": c.title, "content_md": c.content_md}


def _video_file(db, case):
    v = db.query(Artifact).filter_by(case_id=case.id, kind="video", is_current=True).first() or _404()
    path = (config.STORAGE_DIR / v.rel_path).resolve()
    if not str(path).startswith(str(config.STORAGE_DIR.resolve())) or not path.exists():
        _404()
    return FileResponse(path, media_type="video/mp4", filename=f"welcome-video-v{v.version}.mp4", content_disposition_type="inline")


@app.get("/api/me/video")
def my_video(user: User = Depends(require_employee), db: Session = Depends(get_db)):
    return _video_file(db, my_case(db, user))


class ChatIn(BaseModel):
    message: str


def msg_out(m: ChatMessage):
    return {"id": m.id, "role": m.role, "content": m.content, "created_at": m.created_at, **(L(m.meta_json) or {})}


@app.get("/api/me/chat")
def chat_history(user: User = Depends(require_employee), db: Session = Depends(get_db)):
    return [msg_out(m) for m in db.query(ChatMessage).filter_by(user_id=user.id).order_by(ChatMessage.id)]


@app.post("/api/me/chat")
def chat_send(body: ChatIn, user: User = Depends(require_employee), db: Session = Depends(get_db)):
    text = body.message.strip()[:2000]
    if not text:
        raise HTTPException(422, "Empty message")
    history = [{"role": m.role, "content": m.content} for m in db.query(ChatMessage).filter_by(user_id=user.id).order_by(ChatMessage.id)]
    db.add(ChatMessage(user_id=user.id, role="user", content=text))
    db.commit()
    res = chat.answer(db, user.employee, history, text)
    m = ChatMessage(user_id=user.id, role="assistant", content=res["content"], meta_json=J({k: v for k, v in res.items() if k != "content"}))
    db.add(m)
    db.commit()
    return msg_out(m)


# Production: the built website is served by the same server (one port). In development Vite serves it instead.
if config.FRONTEND_DIST.exists():
    from fastapi.staticfiles import StaticFiles
    app.mount("/", StaticFiles(directory=config.FRONTEND_DIST, html=True), name="site")
