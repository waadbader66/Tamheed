"""Runs the automated tests and saves a summary for the Evaluation tab (backend/eval/results/tests.json)."""
import json
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LABELS = {
    "test_login_errors_and_role_separation": "Sign-in errors and HR/employee separation",
    "test_full_flow_personalisation_and_isolation": "Full flow: two CVs → different plans; employees can't see each other's data",
    "test_failed_stage_is_visible_and_retryable": "A failed step is visible, retryable and never duplicates invitations",
    "test_claude_failure_falls_back": "Claude errors fall back to labelled rule-based answers",
    "test_claude_script_path_keeps_visuals": "Video narration from Claude keeps facts from the database; too-long scripts rejected",
    "test_allowlist_star_allows_any_address": "Invitations can go to any email address",
    "test_hr_can_delete_new_hire_and_everything_goes": "Deleting a hire removes all their data and files",
    "test_every_emailed_password_works_until_changed": "Every emailed temporary password works until the hire sets their own",
    "test_agent_plan_guardrails_adaptation_and_review": "Agent guardrails: invented quotes, courses, links and mentors rejected; re-plan keeps progress",
    "test_practical_exercise_flow": "Practical exercise: answer key hidden, graded, plan adapts, retry works",
    "test_exercise_design_is_validated": "Exercise design validated (rubric sums to 100, unknown records stripped)",
    "test_completion_notifies_hr_and_graduates": "Completion detected, HR notified, hire moves to existing employees",
    "test_completed_hires_move_to_existing_after_grace_period": "Hires move to existing employees after the grace period",
    "test_render_real_mp4": "Real video render: MP4 with video and audio streams",
}
xml = ROOT / "backend" / "eval" / "results" / "pytest.xml"
t0 = time.time()
subprocess.run([str(ROOT / ".venv" / "bin" / "python"), "-m", "pytest", "-q", f"--junitxml={xml}"], cwd=ROOT / "backend")
cases = []
for tc in ET.parse(xml).getroot().iter("testcase"):
    ok = not any(ch.tag in ("failure", "error") for ch in tc)
    cases.append({"name": tc.get("name"), "label": LABELS.get(tc.get("name"), tc.get("name")), "ok": ok, "seconds": float(tc.get("time", 0))})
out = {"total": len(cases), "passed": sum(c["ok"] for c in cases), "failed": sum(not c["ok"] for c in cases),
       "seconds": round(time.time() - t0, 1), "ran_at": time.strftime("%Y-%m-%d %H:%M"), "tests": cases}
(ROOT / "backend" / "eval" / "results" / "tests.json").write_text(json.dumps(out, indent=2))
print(f"{out['passed']}/{out['total']} passed")
sys.exit(1 if out["failed"] else 0)
