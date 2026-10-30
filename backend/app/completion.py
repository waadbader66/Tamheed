"""Onboarding completion and graduation to 'existing employee'."""
from datetime import datetime, timedelta

from . import agent, config
from .models import Exercise, OnboardingCase, OnboardingTask, ResponsibilityPlan, TrainingAssignment, audit


def requirements(db, case: OnboardingCase) -> dict:
    tasks = db.query(OnboardingTask).filter_by(case_id=case.id).all()
    resp = db.query(ResponsibilityPlan).filter_by(case_id=case.id).all()
    mand = [t for t in db.query(TrainingAssignment).filter_by(case_id=case.id) if t.priority == "mandatory"]
    ex = db.query(Exercise).filter_by(case_id=case.id).order_by(Exercise.id.desc()).first()
    return {"tasks": bool(tasks) and all(t.status in ("submitted", "verified") for t in tasks),
            "responsibilities": bool(resp) and all(r.status == "done" for r in resp),
            "mandatory_training": all(t.status == "completed" for t in mand),
            "exercise": ex is None or ex.status == "assessed"}


def check(db, case: OnboardingCase) -> bool:
    """Marks the case complete when every requirement is met (or reopens it if something was undone before graduation).
    Returns True when it just became complete."""
    if case.graduated_at or case.status != "ready" and case.status != "completed":
        return False
    done = all(requirements(db, case).values())
    if done and not case.completed_at:
        case.completed_at, case.status, case.completion_seen = datetime.utcnow(), "completed", False
        first = case.employee.full_name.split()[0]
        agent.log(db, case.id, "complete", "next-step",
                  f"Congratulations, {first}! You've completed your onboarding — every task, responsibility, mandatory course and your "
                  "practical exercise. Your manager and HR have been notified.", {"trigger": "Onboarding complete"}, employee=True)
        audit(db, "system", "onboarding-complete", case.employee.employee_code)
        return True
    if not done and case.completed_at:
        case.completed_at, case.status = None, "ready"
    return False


def graduate(db, case: OnboardingCase, actor: str = "system") -> None:
    e = case.employee
    e.is_new_hire = False
    case.graduated_at = datetime.utcnow()
    audit(db, actor, "moved-to-existing", e.employee_code, e.full_name)


def graduate_due(db) -> int:
    cutoff = datetime.utcnow() - timedelta(days=config.GRADUATE_DAYS)
    due = db.query(OnboardingCase).filter(OnboardingCase.completed_at.isnot(None), OnboardingCase.graduated_at.is_(None),
                                          OnboardingCase.completed_at <= cutoff).all()
    for c in due:
        graduate(db, c)
    if due:
        db.commit()
    return len(due)


def graduates_on(case: OnboardingCase):
    return (case.completed_at + timedelta(days=config.GRADUATE_DAYS)) if case.completed_at and not case.graduated_at else None
