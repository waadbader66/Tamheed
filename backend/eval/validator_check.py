"""Does the validator matter?  Plants known errors in plans for the 12 held-out hires and checks that validate()
catches every one, without throwing away the valid parts.  Free and deterministic (no Claude calls, no network).
Usage (from backend/):  ../.venv/bin/python -m eval.validator_check eval/results/validator.json"""
import copy
import json
import os
import sys
import tempfile
import time
from datetime import date

OUT = sys.argv[1] if len(sys.argv) > 1 else "eval/results/validator.json"
tmp = tempfile.mkdtemp(prefix="tamheed_validator_")
os.environ.update(DATABASE_URL=f"sqlite:///{tmp}/eval.db", TAMHEED_STORAGE=f"{tmp}/storage", DISABLE_WORKER="1", ANTHROPIC_API_KEY="")

from app import agent, seed  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.models import Employee, OnboardingCase, Project, Role  # noqa: E402
from eval.cases import CASES  # noqa: E402

FAKE_URL = "https://made-up.example/course"
# each planted error: (key, label shown to judges, how to plant it, how to check it was caught)
PLANTS = [
    ("invented_quote", "Skill claimed with a quote that is not in the CV",
     lambda p, ctx: _plant_quote(p),
     lambda out, p: "NASA" not in json.dumps([s for s in out["skills"] if s["status"] == "evidenced"])),
    ("fake_mentor", "Mentor who is not on the hire's team",
     lambda p, ctx: p["responsibilities"][0].update(support_level="mentoring", mentor_code="EMP-FAKE-999"),
     lambda out, p: all(r["mentor_code"] != "EMP-FAKE-999" for r in out["responsibilities"])),
    ("invented_course", "Course that doesn't exist in the catalog",
     lambda p, ctx: p["training"].insert(0, {"code": "FAKE-101", "priority": "optional", "rationale": "x"}),
     lambda out, p: all(t["code"] != "FAKE-101" for t in out["training"])),
    ("unverified_link", "External course link not found by web search",
     lambda p, ctx: p["training"].insert(0, {"code": "", "url": FAKE_URL, "title": "Made-up course", "rationale": "x"}),
     lambda out, p: FAKE_URL not in json.dumps(out["training"])),
    ("out_of_scope_record", "First-week action citing a record the hire can't see",
     lambda p, ctx: p["first_week_actions"].append({"title": "Read the secret board memo", "detail": "x", "source_ids": ["E99999"]}),
     lambda out, p: all("secret board memo" not in a["title"] for a in out["first_week_actions"])),
    ("ungrounded_background", "Background fact that is not in the CV",
     lambda p, ctx: p["background"].update(achievement="Won the Nobel Prize in Physics"),
     lambda out, p: "Nobel" not in json.dumps(out["background"])),
    ("missing_responsibility", "A responsibility left out of the plan",
     lambda p, ctx: p["responsibilities"].pop(),
     lambda out, p: len(out["responsibilities"]) == len(p["_all_resp"])),
]


def _plant_quote(p):
    s = next((s for s in p["skills"] if s["status"] != "evidenced"), p["skills"][0])
    s.update(status="evidenced", quote="Led a team of 40 engineers at NASA for 12 years.")
    p["_planted_skill"] = s["key"]


def make_case(db, c):
    role = db.query(Role).filter_by(title=c["role"]).one()
    proj = db.query(Project).filter_by(code=c["project"]).first() if c["project"] else None
    mgr = db.query(Employee).filter_by(employee_code=c["manager"]).one()
    e = Employee(employee_code="VC-" + c["id"], full_name=c["name"], email=f"vc-{c['id'].lower()}@eval.example", title=role.title,
                 role_id=role.id, department_id=role.department_id, manager_id=mgr.id, project_id=proj.id if proj else None,
                 start_date=date(2026, 11, 15), is_new_hire=True)
    db.add(e)
    db.flush()
    case = OnboardingCase(employee_id=e.id, cv_filename="cv.txt" if c["cv"] else "", cv_text=c["cv"])
    db.add(case)
    db.commit()
    return e, case


def main():
    seed.run(reset=True)
    db = SessionLocal()
    by_type = {k: {"label": label, "planted": 0, "caught": 0, "caught_without_validator": 0} for k, label, *_ in PLANTS}
    kept = kept_total = 0
    for c in CASES:
        e, case = make_case(db, c)
        ctx = agent.Ctx(db, case, e)
        clean = agent.plan_from_rules(ctx)
        base, _ = agent.validate(agent.Ctx(db, case, e), copy.deepcopy(clean))   # the valid plan, for comparison
        good_skills = {s["key"] for s in base["skills"] if s["status"] == "evidenced"}
        for key, _label, plant, caught in PLANTS:
            p = copy.deepcopy(clean)
            p["_all_resp"] = list(clean["responsibilities"])
            plant(p, ctx)
            raw = {k: v for k, v in p.items() if not k.startswith("_")}
            out, _issues = agent.validate(agent.Ctx(db, case, e), copy.deepcopy(raw))
            by_type[key]["planted"] += 1
            by_type[key]["caught"] += bool(caught(out, p))
            by_type[key]["caught_without_validator"] += bool(caught(raw, p))   # control: the plan as submitted
            good = good_skills - {p.get("_planted_skill")}
            still = {s["key"] for s in out["skills"] if s["status"] == "evidenced"}
            kept += len(good & still)                                      # valid evidence must survive
            kept_total += len(good)
    planted = sum(v["planted"] for v in by_type.values())
    caught = sum(v["caught"] for v in by_type.values())
    summary = {"cases": len(CASES), "error_types": len(PLANTS), "planted": planted, "caught": caught,
               "caught_without_validator": sum(v["caught_without_validator"] for v in by_type.values()),
               "catch_rate": round(100 * caught / planted, 1), "valid_evidence_kept": round(100 * kept / max(1, kept_total), 1)}
    json.dump({"summary": summary, "by_type": by_type, "ran_at": time.strftime("%Y-%m-%d %H:%M")}, open(OUT, "w"), indent=2)
    print(json.dumps(summary, indent=1))
    for v in by_type.values():
        print(f"  {v['caught']}/{v['planted']} (without validator {v['caught_without_validator']})  {v['label']}")


if __name__ == "__main__":
    main()
