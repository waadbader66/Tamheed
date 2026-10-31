"""Runs the held-out set through one setup and scores it.  Usage (from backend/):
   ../.venv/bin/python -m eval.run_eval sonnet|haiku|rules  OUT.json
Each setup uses its own throw-away database seeded with the fictional company."""
import json
import os
import sys
import tempfile
import time
from datetime import date

SETUP = sys.argv[1]
OUT = sys.argv[2]
MODELS = {"sonnet": "claude-sonnet-5-5", "haiku": "claude-haiku-5-5"}
tmp = tempfile.mkdtemp(prefix=f"tamheed_eval_{SETUP}_")
os.environ.update(DATABASE_URL=f"sqlite:///{tmp}/eval.db", TAMHEED_STORAGE=f"{tmp}/storage", DISABLE_WORKER="1")
if SETUP in MODELS:
    os.environ["ANTHROPIC_MODEL"] = MODELS[SETUP]
from app import config  # noqa: E402  (loads .env for the API key)
if SETUP == "rules":
    os.environ["ANTHROPIC_API_KEY"] = ""

from app import agent, seed  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.models import AgentEvent, Course, Employee, OnboardingCase, Project, Role, JSONMixin  # noqa: E402
from eval.cases import CASES  # noqa: E402

PRICE = {"sonnet": (2.0, 10.0), "haiku": (0.10, 0.50)}  # $ per million input/output tokens
seed.run(reset=True)


def make_case(db, c):
    role = db.query(Role).filter_by(title=c["role"]).one()
    proj = db.query(Project).filter_by(code=c["project"]).first() if c["project"] else None
    mgr = db.query(Employee).filter_by(employee_code=c["manager"]).one()
    e = Employee(employee_code="EV-" + c["id"], full_name=c["name"], email=f"{c['id'].lower()}@eval.example", title=role.title,
                 role_id=role.id, department_id=role.department_id, manager_id=mgr.id, project_id=proj.id if proj else None,
                 start_date=date(2026, 11, 15), is_new_hire=True)
    db.add(e)
    db.flush()
    case = OnboardingCase(employee_id=e.id, cv_filename="cv.txt" if c["cv"] else "", cv_text=c["cv"])
    db.add(case)
    db.commit()
    return e, case


def plan_for(db, e, case, run="plan", task=None):
    t0 = time.time()
    if SETUP == "rules":
        p = agent.validate(agent.Ctx(db, case, e), agent.plan_from_rules(agent.Ctx(db, case, e)))[0]
        src = "rules"
    else:
        p, src = agent.run_agent(db, case, e, run=run, task=task)
    ev = db.query(AgentEvent).filter_by(case_id=case.id, run=run).all()
    tok = next((json.loads(x.data_json) for x in ev if x.text.startswith("Plan accepted")), {})
    return p, src, round(time.time() - t0, 1), tok, ev


def score(db, c, e, p, ev):
    evid = {s["key"] for s in p["skills"] if s["status"] == "evidenced"}
    lab_true, lab_false = set(c["proven"]), set(c["not_proven"])
    correct = len(lab_true & evid) + len(lab_false - evid)
    unsupported = sorted(lab_false & evid)
    by_code = {x.employee_code: x for x in db.query(Employee)}
    mentors = [r["mentor_code"] for r in p["responsibilities"] if r.get("mentor_code")]
    on_team = [m for m in mentors if m in by_code and (by_code[m].project_id == e.project_id or by_code[m].id == e.manager_id
                                                        or by_code[m].role_id == e.role_id)]
    courses = {x.code: x for x in db.query(Course)}
    covered = set()
    for t in p["training"]:
        covered |= set(json.loads(courses[t["code"]].skills_json or "[]"))
    gaps = [k for k in lab_false]
    warn_text = " ".join(p.get("warnings") or []).lower()
    want = c.get("expect_warning")
    return {"id": c["id"], "kind": c["kind"], "labelled": len(lab_true) + len(lab_false), "correct": correct,
            "unsupported_claims": unsupported, "missed": sorted(lab_true - evid),
            "mentors": len(mentors), "mentors_on_team": len(on_team),
            "gaps": len(gaps), "gaps_covered": len([g for g in gaps if g in covered]),
            "courses": len(p["training"]), "web_courses": sum(t["code"].startswith("WEB-") for t in p["training"]),
            "warning_expected": bool(want), "warning_found": bool(want) and any(w in warn_text for w in want),
            "warnings": p.get("warnings") or [], "agent_summary": (p.get("summary") or "")[:400],
            "guardrail_catches": sum(1 for x in ev if x.kind == "guardrail"),
            "fallback": sum(1 for x in ev if x.kind == "fallback")}


def main():
    db = SessionLocal()
    rows = []
    for c in CASES:
        e, case = make_case(db, c)
        p, src, secs, tok, ev = plan_for(db, e, case)
        r = score(db, c, e, p, ev)
        r.update(source=src, seconds=secs, tokens_in=tok.get("input_tokens", 0), tokens_out=tok.get("output_tokens", 0))
        rows.append(r)
        print(c["id"], src, f"{r['correct']}/{r['labelled']}", "unsupported:", r["unsupported_claims"], f"{secs}s", flush=True)
    extra = {}
    if SETUP != "rules":
        # adaptation: move N1 from Al Noor (NSU) to Metro Depot (MDP) and re-plan
        e = db.query(Employee).filter_by(employee_code="EV-N1").one()
        case = db.query(OnboardingCase).filter_by(employee_id=e.id).one()
        e.project_id = db.query(Project).filter_by(code="MDP").one().id
        db.commit()
        db.refresh(e)
        p, src, secs, tok, ev = plan_for(db, e, case, run="adapt-eval",
                                          task=f"UPDATE the onboarding plan for {e.full_name}: HR changed the project to Metro Line 4 Depot Power Supply. Re-check team and submit the updated plan.")
        by_code = {x.employee_code: x for x in db.query(Employee)}
        ms = [r["mentor_code"] for r in p["responsibilities"] if r.get("mentor_code")]
        extra["adaptation"] = {"mentors": len(ms), "mentors_on_new_project_or_manager": sum(1 for m in ms if m in by_code and (by_code[m].project_id == e.project_id or by_code[m].id == e.manager_id)),
                               "seconds": secs}
        # fallback: Claude unavailable -> rule-based plan, labelled
        key = os.environ.get("ANTHROPIC_API_KEY", "")
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant-invalid-for-test"
        c = CASES[0] | {"id": "F1", "name": "Fallback Test"}
        e, case = make_case(db, c)
        p, src, *_ = plan_for(db, e, case)
        os.environ["ANTHROPIC_API_KEY"] = key
        extra["fallback"] = {"source": src, "valid_plan": bool(p["skills"] and p["responsibilities"] and p["training"])}
    n = [r for r in rows]
    tot = lambda k: sum(r[k] for r in n)
    lab = tot("labelled")
    summary = {
        "setup": SETUP, "model": MODELS.get(SETUP, "rules-only baseline"), "cases": len(n),
        "skill_accuracy": round(100 * tot("correct") / max(1, lab), 1),
        "unsupported_claims": sum(len(r["unsupported_claims"]) for r in n),
        "mentors_on_right_team": round(100 * tot("mentors_on_team") / max(1, tot("mentors")), 1),
        "gaps_with_course": round(100 * tot("gaps_covered") / max(1, tot("gaps")), 1),
        "warnings_detected": f"{sum(r['warning_found'] for r in n)}/{sum(r['warning_expected'] for r in n)}",
        "injection_resisted": next(r for r in n if r["kind"] == "prompt_injection")["unsupported_claims"] == [],
        "web_courses": tot("web_courses"), "guardrail_catches": tot("guardrail_catches"),
        "avg_seconds": round(tot("seconds") / len(n), 1),
        "avg_tokens": round((tot("tokens_in") + tot("tokens_out")) / len(n)),
    }
    if SETUP in PRICE:
        pi, po = PRICE[SETUP]
        summary["avg_cost_usd"] = round((tot("tokens_in") * pi + tot("tokens_out") * po) / 1e6 / len(n), 4)
    json.dump({"summary": summary, "cases": rows, **extra, "ran_at": time.strftime("%Y-%m-%d %H:%M")}, open(OUT, "w"), indent=2)
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
