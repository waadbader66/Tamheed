"""Critical-path tests. Video rendering is replaced by a stub here (it's verified separately by test_video_render)."""
import os, tempfile, importlib
from pathlib import Path

TMP = Path(tempfile.mkdtemp())
os.environ.update(DATABASE_URL=f"sqlite:///{TMP/'t.db'}", TAMHEED_STORAGE=str(TMP / "storage"), DISABLE_WORKER="1",
                  ANTHROPIC_API_KEY="", SMTP_USER="", SMTP_PASSWORD="", EMAIL_ALLOWLIST="waadbader@gmail.com")

import pytest
from fastapi.testclient import TestClient
from app import pipeline, video
from app.main import app
from app.db import SessionLocal
from app.models import JobStage, Invitation, User

SAMPLES = Path(__file__).resolve().parents[2] / "data" / "samples"


@pytest.fixture(scope="module")
def client():
    def fake_render(script, out):
        out.parent.mkdir(parents=True, exist_ok=True); out.write_bytes(b"\x00\x00\x00\x18ftypmp42fake")
        assert len(script["scenes"]) >= 8
        return {"duration": 1.0, "frames": 1, "fps": 1, "size": "1x1", "scenes": len(script["scenes"])}
    real = video.render
    video.render = fake_render
    with TestClient(app) as c:
        yield c
    video.render = real


def login(c, u, p):
    c.cookies.clear()
    return c.post("/api/auth/login", json={"username": u, "password": p})


def opts(c):
    return c.get("/api/hr/options").json()


def create(c, code, name, email, cv, exp=""):
    o = opts(c)
    role = next(r for r in o["roles"] if r["title"] == "Electrical Project Engineer")
    mgr = next(m for m in o["managers"] if m["name"] == "Khalid Al-Mutairi")
    proj = next(p for p in o["projects"] if p["code"] == "NSU")
    files = {"cv": (cv, (SAMPLES / cv).read_bytes(), "text/plain")} if cv else None
    data = dict(employee_code=code, full_name=name, email=email, role_id=role["id"], department_id=role["department_id"], manager_id=mgr["id"],
                project_id=proj["id"], start_date="2026-11-02", experience_text=exp)
    return c.post("/api/hr/employees", data=data, files=files)


def drain():
    db = SessionLocal()
    while pipeline.run_next(db):
        pass
    db.close()


def test_login_errors_and_role_separation(client):
    assert login(client, "hr@rimal.example", "wrong").status_code == 401
    assert login(client, "hr@rimal.example", "Rimal-HR-2026!").status_code == 200
    assert client.get("/api/me/workspace").status_code == 403  # HR has no employee workspace
    client.cookies.clear()
    assert client.get("/api/hr/overview").status_code == 401


def test_full_flow_personalisation_and_isolation(client):
    login(client, "hr@rimal.example", "Rimal-HR-2026!")
    a = create(client, "T-1", "Sami Test", "waadbader+sami@gmail.com", "CV_Sami_Al-Rashid_embedded.txt")
    b = create(client, "T-2", "Hana Test", "hana.test@rimal.example", "CV_Hana_Al-Fahad_projects.txt")
    assert a.status_code == 200 and b.status_code == 200
    assert create(client, "T-1", "Dup", "dup@x.com", None).status_code == 409  # duplicate prevention
    drain()
    ea, eb = client.get(f"/api/hr/employees/{a.json()['employee_id']}").json(), client.get(f"/api/hr/employees/{b.json()['employee_id']}").json()
    assert all(s["status"] == "done" for s in ea["stages"]), ea["stages"]
    assert ea["status"] == "ready" and ea["video"]
    # same role, different backgrounds -> different plans
    assert ea["analysis"]["evidenced"] != eb["analysis"]["evidenced"], (ea["plan_source"], [x["text"] for x in ea["agent"][:5]])
    assert [r["support_level"] for r in ea["responsibilities"]] != [r["support_level"] for r in eb["responsibilities"]]
    # training = exactly 1 mandatory + 1 internal + 1 external (with a real link), chosen per person
    for e in (ea, eb):
        assert [t["priority"] for t in e["training"]] == ["mandatory", "optional", "optional"]
        assert [t["external"] for t in e["training"]] == [False, False, True]
        assert e["training"][2]["url"].startswith("https://")
    assert [t["title"] for t in ea["training"]] != [t["title"] for t in eb["training"]]
    # skills not in CV are 'unverified', never 'missing'
    assert all(s["status"] in ("evidenced", "unverified") for s in ea["analysis"]["skills"])
    # invitation honesty: no sender configured -> not 'sent'; non-allowlisted -> blocked
    assert ea["invitation"]["status"] == "waiting-sender-config"
    assert eb["invitation"]["status"] == "blocked-not-allowlisted"
    # employee B tries to read A's data -> blocked; employee cannot reach HR
    db = SessionLocal()
    ub = db.query(User).filter_by(username="hana.test@rimal.example").first()
    from app.auth import hash_password
    ub.password_hash = hash_password("TempPass-123"); db.commit(); db.close()
    assert login(client, "hana.test@rimal.example", "TempPass-123").status_code == 200
    assert client.get("/api/me/workspace").status_code == 428  # must change password first
    r = client.post("/api/auth/change-password", json={"current": "TempPass-123", "new": "MyNewPassword-1"})
    assert r.status_code == 200
    w = client.get("/api/me/workspace").json()
    assert w["employee"]["name"] == "Hana Test"
    assert client.get("/api/hr/overview").status_code == 403
    assert client.get(f"/api/hr/employees/{a.json()['employee_id']}/video").status_code == 403
    other_task = ea["tasks"][0]["id"]
    assert client.post(f"/api/me/tasks/{other_task}/submit").status_code == 404
    # own task: submit -> 'submitted' (not verified until HR verifies)
    own = w["tasks"][0]["id"]
    assert client.post(f"/api/me/tasks/{own}/submit").json()["status"] == "submitted"
    # chat works offline, is labelled, and cites only accessible records
    m = client.post("/api/me/chat", json={"message": "Why did we switch the 33 kV cable supplier?"}).json()
    assert "Claude not connected" in m["engine"] and any(s["id"].startswith("E") for s in m["sources"])
    m2 = client.post("/api/me/chat", json={"message": "TimescaleDB telemetry decision"}).json()
    assert not any("TimescaleDB" in s["label"] for s in m2["sources"])  # KFT emails are out of scope for an NSU hire
    # invitation view tracking
    login(client, "hr@rimal.example", "Rimal-HR-2026!")
    inv = client.get("/api/hr/invitations").json()
    assert any(i["password_changed_at"] for i in inv)


def test_failed_stage_is_visible_and_retryable(client):
    login(client, "hr@rimal.example", "Rimal-HR-2026!")
    orig = video.render
    video.render = lambda s, o: (_ for _ in ()).throw(RuntimeError("ffmpeg crashed"))
    r = create(client, "T-3", "Retry Person", "retry@rimal.example", None)
    drain()
    case = client.get(f"/api/hr/cases/{r.json()['case_id']}").json()
    vid = next(s for s in case["stages"] if s["key"] == "video")
    assert vid["status"] == "failed" and "ffmpeg crashed" in vid["detail"]
    assert next(s for s in case["stages"] if s["key"] == "workspace")["status"] == "pending"
    video.render = orig
    client.post(f"/api/hr/cases/{r.json()['case_id']}/retry")
    drain()
    case = client.get(f"/api/hr/cases/{r.json()['case_id']}").json()
    assert all(s["status"] == "done" for s in case["stages"])
    db = SessionLocal()
    assert db.query(Invitation).filter(Invitation.employee_id == case["employee"]["id"]).count() == 1  # no duplicate invitation
    db.close()


def test_claude_failure_falls_back(client, monkeypatch):
    from app import chat, config, llm
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-invalid")
    def boom(*a, **k): raise RuntimeError("API down")
    monkeypatch.setattr(chat, "_claude", boom)
    db = SessionLocal()
    from app.models import Employee
    emp = db.query(Employee).filter_by(employee_code="R-0022").first()
    res = chat.answer(db, emp, [], "inspection failed")
    assert "Claude error" in res["engine"]
    db.close()


def test_claude_script_path_keeps_visuals(monkeypatch):
    """Recorded-style fake model response: Claude rewrites narration, visuals must still come from the DB facts."""
    from app import scriptgen, llm
    f = {"first": "T", "x": 1}
    base = {"scenes": [{"key": k, "lines": [{"speaker": "A", "text": "draft"}], "visual": f} for k in ("welcome", "next")]}
    monkeypatch.setattr(llm, "complete_json", lambda *a, **k: {"scenes": [{"key": "welcome", "lines": [{"speaker": "A", "text": "Hi T"}]},
                                                                         {"key": "next", "lines": [{"speaker": "B", "text": "Bye"}]}]})
    out = scriptgen.claude_script(f, base)
    assert all(s["visual"] is f for s in out["scenes"])
    monkeypatch.setattr(llm, "complete_json", lambda *a, **k: {"scenes": [{"key": "welcome", "lines": [{"speaker": "A", "text": "word " * 200}]},
                                                                         {"key": "next", "lines": [{"speaker": "B", "text": "word " * 200}]}]})
    with pytest.raises(ValueError):
        scriptgen.claude_script(f, base)


def test_allowlist_star_allows_any_address(monkeypatch):
    from app import mailer
    monkeypatch.setenv("EMAIL_ALLOWLIST", "*")
    assert mailer.allowed("someone@company.com") and mailer.allowed("x@y.org")
    monkeypatch.setenv("EMAIL_ALLOWLIST", "waadbader66@gmail.com")
    assert mailer.allowed("waadbader66+a@gmail.com") and not mailer.allowed("someone@company.com")


def test_hr_can_delete_new_hire_and_everything_goes(client):
    login(client, "hr@rimal.example", "Rimal-HR-2026!")
    r = create(client, "T-DEL", "Delete Me", "delete.me@rimal.example", "CV_Hana_Al-Fahad_projects.txt")
    drain()
    emp_id = r.json()["employee_id"]
    assert client.delete("/api/hr/employees/1").status_code == 409  # seeded staff are protected
    assert client.delete(f"/api/hr/employees/{emp_id}").json()["deleted"] is True
    assert client.get(f"/api/hr/employees/{emp_id}").status_code == 404
    assert login(client, "delete.me@rimal.example", "anything").status_code == 401
    from app import config
    assert not (config.STORAGE_DIR / "employees" / str(emp_id)).exists()
    # the same ID/email can be used again afterwards
    login(client, "hr@rimal.example", "Rimal-HR-2026!")
    assert create(client, "T-DEL", "Delete Me", "delete.me@rimal.example", None).status_code == 200


def test_every_emailed_password_works_until_changed(client, monkeypatch):
    import re
    from app import mailer
    sent = []
    monkeypatch.setattr(mailer, "sender_configured", lambda: True)
    monkeypatch.setattr(mailer, "send", lambda msg: sent.append(msg.get_body(("plain",)).get_content()) if msg["To"] == "pw.test@example.org" else None)
    monkeypatch.setenv("EMAIL_ALLOWLIST", "*")
    login(client, "hr@rimal.example", "Rimal-HR-2026!")
    r = create(client, "T-PW", "Pass Word", "pw.test@example.org", None)
    drain()
    inv = next(i for i in client.get("/api/hr/invitations").json() if i["to"] == "pw.test@example.org")
    assert inv["status"] == "sent"
    client.post(f"/api/hr/invitations/{inv['id']}/resend")  # HR clicks resend: a second email
    pws = [re.search(r"Temporary password: (\S+)", body).group(1) for body in sent]
    assert len(pws) == 2 and pws[0] != pws[1]
    assert "invite=" in sent[0] and "u=pw.test%40example.org" in sent[0]
    # the OLDER email's password still works, even with pasted spaces around it
    assert login(client, " pw.test@example.org ", f"  {pws[0]} ").status_code == 200
    assert client.post("/api/auth/change-password", json={"current": pws[1], "new": "BrandNewPass-1"}).status_code == 200
    # after choosing their own password, emailed temporary passwords stop working
    assert login(client, "pw.test@example.org", pws[0]).status_code == 401
    assert login(client, "pw.test@example.org", "BrandNewPass-1").status_code == 200


# ---------------------------------------------------------------- onboarding agent (recorded-style fake Claude)
import json as _json
from types import SimpleNamespace as NS


class FakeClaude:
    """Scripted stand-in for the Anthropic client: gathers context with tools, then submits a plan that contains
    deliberate mistakes (invented quote, unknown mentor, invented course, unsupported source) to exercise the guardrails."""
    def __init__(self):
        self.messages = self
        self.calls = 0

    def create(self, **kw):
        self.calls += 1
        u = NS(input_tokens=100, output_tokens=50)
        if any(t["name"] == "submit_progress_review" for t in kw.get("tools", [])):
            return NS(content=[NS(type="tool_use", id="r1", name="submit_progress_review",
                                  input={"message": "Great job finishing that course! Next, shadow your mentor on the ITP.", "extra_course_code": "DIG-101", "extra_course_reason": "Builds on it."})],
                      stop_reason="tool_use", usage=u)
        results = {}
        for m in kw["messages"]:
            if m["role"] == "user" and isinstance(m["content"], list):
                for r in m["content"]:
                    results[r["tool_use_id"]] = _json.loads(r["content"]) if not r.get("is_error") else r["content"]
        if not results:
            return NS(content=[NS(type="text", text="Reading the profile, role, team and catalog first."),
                               NS(type="server_tool_use", id="ws1", name="web_search", input={"query": "IEC 61850 course"}),
                               NS(type="web_search_tool_result", tool_use_id="ws1",
                                  content=[NS(type="web_search_result", url="https://www.coursera.org/learn/real-course", title="Real Course")]),
                               *[NS(type="tool_use", id=n, name=n, input={}) for n in ("get_new_hire_profile", "get_role_requirements", "get_team")],
                               NS(type="tool_use", id="search_course_catalog", name="search_course_catalog", input={})],
                      stop_reason="tool_use", usage=u)
        role, team = results["get_role_requirements"], results["get_team"]
        plan = {"summary": "Automation engineer; strong software, coordination not yet shown.",
                "change_summary": "Your project changed, so your plan now follows the new team.",
                "skills": [{"key": "software", "status": "evidenced", "quote": "Strong programmer (Python, C++)", "reasoning": "CV says so"},
                           {"key": "power", "status": "evidenced", "quote": "Led the design of a 400kV national grid substation", "reasoning": "invented"}],
                "responsibilities": [{"title": r["title"], "support_level": "mentoring", "mentor_code": "R-9999" if i == 0 else team["mentor_candidates"][0]["code"],
                                      "rationale": "Needs practice."} for i, r in enumerate(role["responsibilities_to_plan"])],
                "training": [{"code": "ACAD-001", "rationale": "Mandatory"}, {"code": "ENG-120", "rationale": "Testing"},
                             {"code": "EXT-INVENTED", "rationale": "Made up"},
                             {"title": "Real Course", "provider": "Coursera", "url": "https://www.coursera.org/learn/real-course", "rationale": "From search"},
                             {"title": "Imaginary", "provider": "Nowhere", "url": "https://made-up.example/course", "rationale": "Invented link"}],
                "first_week_actions": [{"title": "Read the supplier decision", "detail": "", "source_ids": ["E2"]},
                                       {"title": "Attend a fake meeting", "detail": "", "source_ids": ["E9999"]}],
                "background": {"recent_org": "Gulf Controls Co.", "achievement": "Nobel Prize in Physics"}}
        return NS(content=[NS(type="text", text="Submitting the plan."), NS(type="tool_use", id=f"s{self.calls}", name="submit_onboarding_plan", input=plan)],
                  stop_reason="tool_use", usage=u)


def test_agent_plan_guardrails_adaptation_and_review(client, monkeypatch):
    from app import agent, llm, config as cfg
    fake = FakeClaude()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(agent, "_fake_or_real_client", lambda: fake)
    monkeypatch.setattr(agent, "link_ok", lambda url: True)  # no network in tests
    monkeypatch.setattr(llm, "complete_json", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no network in tests")))
    login(client, "hr@rimal.example", "Rimal-HR-2026!")
    r = create(client, "T-AG", "Agent Test", "agent.test@rimal.example", "CV_Sami_Al-Rashid_embedded.txt")
    drain()
    rec = client.get(f"/api/hr/employees/{r.json()['employee_id']}").json()
    assert rec["plan_source"].startswith("Claude agent")
    skills = {s["key"]: s for s in rec["analysis"]["skills"]}
    assert skills["software"]["status"] == "evidenced"                       # real quote accepted
    assert skills["power"]["status"] == "unverified"                         # invented quote rejected
    assert "Nobel" not in _json.dumps(rec["analysis"]["background"])         # ungrounded background dropped
    codes = [t["code"] for t in rec["training"]]
    assert "EXT-INVENTED" not in codes and sum(t["priority"] == "mandatory" for t in rec["training"]) == 1
    urls = [t["url"] for t in rec["training"]]
    assert "https://www.coursera.org/learn/real-course" in urls           # web result accepted (was in search results)
    assert "https://made-up.example/course" not in urls                   # link not from search results rejected
    assert len(codes) == 3 and any(t["web_found"] for t in rec["training"])
    assert all(r_["mentor"] for r_ in rec["responsibilities"])               # unknown mentor replaced by a real one
    titles = [t["title"] for t in rec["tasks"]]
    assert "Read the supplier decision" in titles and "Attend a fake meeting" not in titles
    kinds = {e["kind"] for e in rec["agent"]}
    assert {"thinking", "tool", "guardrail", "decision"} <= kinds            # visible agent trace
    # adaptation: complete a course, then HR moves the hire to another project
    from app.auth import hash_password
    db = SessionLocal()
    u = db.query(User).filter_by(username="agent.test@rimal.example").first()
    u.password_hash, u.must_change_password = hash_password("AgentPass-123"), False
    db.commit(); db.close()
    login(client, "agent.test@rimal.example", "AgentPass-123")
    ws = client.get("/api/me/workspace").json()
    eng = next(t for t in ws["training"] if t["code"] == "ENG-120")
    assert client.post(f"/api/me/training/{eng['id']}", json={"status": "completed"}).status_code == 200
    drain()                                                                  # runs the agent's progress review
    ws = client.get("/api/me/workspace").json()
    assert any(u_["kind"] == "next-step" and "Great job" in u_["text"] for u_ in ws["updates"])
    assert any(t["code"] == "DIG-101" for t in ws["training"])               # agent added a valid optional course
    login(client, "hr@rimal.example", "Rimal-HR-2026!")
    kft = next(p for p in client.get("/api/hr/options").json()["projects"] if p["code"] == "KFT")
    up = client.post(f"/api/hr/employees/{rec['profile']['id']}/update", data={"project_id": str(kft["id"])}).json()
    assert up["replanning"] and "project changed" in up["changes"][0]
    drain()
    rec2 = client.get(f"/api/hr/employees/{rec['profile']['id']}").json()
    assert rec2["profile"]["project"]["code"] == "KFT"
    assert any(t["code"] == "ENG-120" and t["status"] == "completed" for t in rec2["training"])  # progress preserved
    assert any(e["kind"] == "plan-update" for e in rec2["agent"])
    assert sum(1 for s in rec2["stages"] if s["key"].startswith("video")) == 2 and all(s["status"] == "done" for s in rec2["stages"])


def test_practical_exercise_flow(client):
    login(client, "hr@rimal.example", "Rimal-HR-2026!")
    r = create(client, "T-EX", "Ex Ercise", "ex.test@rimal.example", "CV_Hana_Al-Fahad_projects.txt")
    drain()
    from app.auth import hash_password
    db = SessionLocal()
    u = db.query(User).filter_by(username="ex.test@rimal.example").first()
    u.password_hash, u.must_change_password = hash_password("ExPass-12345"), False
    db.commit(); db.close()
    login(client, "ex.test@rimal.example", "ExPass-12345")
    d = client.get("/api/me/exercise").json()
    ex = d["exercise"]
    assert ex and ex["status"] == "open" and ex["rubric"]
    assert "answer_key" not in _json.dumps(d)                                   # key never sent to the employee
    assert isinstance(ex["materials"], list)
    assert client.post("/api/me/exercise/submit", json={"answer": "too short"}).status_code == 422
    answer = " ".join(row[1] for row in ex["worksheet"]["rows"])                  # covers every step of the standard exercise
    assert client.post("/api/me/exercise/submit", json={"answer": answer}).status_code == 200
    drain()
    ex2 = client.get("/api/me/exercise").json()["exercise"]
    assert ex2["status"] == "assessed" and ex2["score"] == 100
    ws = client.get("/api/me/workspace").json()
    assert any(u_["kind"] == "plan-update" and "Practical exercise" in u_["data"].get("trigger", "") for u_ in ws["updates"])
    assert client.post("/api/me/exercise/review-request").status_code == 200
    assert any("practical exercise with" in t["title"] for t in client.get("/api/me/workspace").json()["tasks"])
    assert client.post("/api/me/exercise/retry").status_code == 200
    drain()
    assert client.get("/api/me/exercise").json()["exercise"]["attempt"] == 2


def test_exercise_design_is_validated(monkeypatch):
    from app import exercise as X
    good = {"title": "T", "scenario": "Inspection on Thursday [E3] and [E999].", "worksheet": {"columns": ["Doc", "Rev"], "rows": [["SLD", "B"], ["ITP", "A"]]},
            "task": "Find issues", "deliverable": "Note", "minutes": 40, "rubric": [{"criterion": "a", "points": 50}, {"criterion": "b", "points": 30}, {"criterion": "c", "points": 20}],
            "answer_key": ["SLD outdated"], "sources": ["E3", "E999"]}
    out = X._check_design(good, {"E3"})
    assert out["sources"] == ["E3"] and "[E999]" not in out["scenario"]       # unknown records stripped
    bad = dict(good, rubric=[{"criterion": "a", "points": 50}, {"criterion": "b", "points": 10}, {"criterion": "c", "points": 10}])
    with pytest.raises(ValueError):
        X._check_design(bad, {"E3"})                                             # rubric must sum to 100


def test_completion_notifies_hr_and_graduates(client):
    login(client, "hr@rimal.example", "Rimal-HR-2026!")
    r = create(client, "T-DONE", "Done Person", "done.person@rimal.example", None)
    drain()
    emp_id = r.json()["employee_id"]
    assert client.post(f"/api/hr/employees/{emp_id}/graduate").status_code == 409   # not complete yet
    from app.auth import hash_password
    db = SessionLocal()
    u = db.query(User).filter_by(username="done.person@rimal.example").first()
    u.password_hash, u.must_change_password = hash_password("DonePass-123"), False
    db.commit(); db.close()
    login(client, "done.person@rimal.example", "DonePass-123")
    ws = client.get("/api/me/workspace").json()
    for t in ws["tasks"]:
        client.post(f"/api/me/tasks/{t['id']}/submit")
    for r_ in ws["responsibilities"]:
        client.post(f"/api/me/responsibilities/{r_['id']}", json={"status": "done"})
    ex = client.get("/api/me/exercise").json()["exercise"]
    assert client.get("/api/me/workspace").json()["completed_at"] is None        # mandatory course + exercise still open
    client.post("/api/me/exercise/submit", json={"answer": " ".join(row[1] for row in ex["worksheet"]["rows"])})
    drain()
    mand = next(t for t in client.get("/api/me/workspace").json()["training"] if t["priority"] == "mandatory")
    client.post(f"/api/me/training/{mand['id']}", json={"status": "completed"})
    drain()
    ws = client.get("/api/me/workspace").json()
    assert ws["completed_at"] and any("completed your onboarding" in u_["text"] for u_ in ws["updates"])
    login(client, "hr@rimal.example", "Rimal-HR-2026!")
    ov = client.get("/api/hr/overview").json()
    assert any(n["employee_id"] == emp_id for n in ov["notices"])
    assert next(h for h in ov["hires"] if h["id"] == emp_id)["case_status"] == "completed"
    assert client.post(f"/api/hr/employees/{emp_id}/graduate").status_code == 200
    ov = client.get("/api/hr/overview").json()
    assert all(h["id"] != emp_id for h in ov["hires"]) and any(e["id"] == emp_id for e in ov["existing_employees"])


def test_completed_hires_move_to_existing_after_grace_period(client):
    from datetime import datetime, timedelta
    from app import completion
    from app.models import OnboardingCase
    login(client, "hr@rimal.example", "Rimal-HR-2026!")
    r = create(client, "T-OLD", "Old Hire", "old.hire@rimal.example", None)
    drain()
    db = SessionLocal()
    case = db.get(OnboardingCase, r.json()["case_id"])
    case.completed_at, case.status = datetime.utcnow() - timedelta(days=5), "completed"
    db.commit()
    assert completion.graduate_due(db) == 0                                         # not yet 3 weeks
    case.completed_at = datetime.utcnow() - timedelta(days=22)
    db.commit()
    assert completion.graduate_due(db) == 1 and db.get(OnboardingCase, case.id).employee.is_new_hire is False
    db.close()


def test_judge_link_signs_in_to_separate_hr_account(client, monkeypatch):
    client.cookies.clear()
    assert client.post("/api/auth/judge", json={"key": "anything"}).status_code == 403          # off by default
    monkeypatch.setenv("JUDGE_ACCESS_KEY", "judge-key-1234567890")
    assert client.post("/api/auth/judge", json={"key": "wrong-key-1234567890"}).status_code == 403
    r = client.post("/api/auth/judge", json={"key": "judge-key-1234567890"})
    assert r.status_code == 200 and r.json()["judge"] and r.json()["kind"] == "hr"
    assert client.get("/api/hr/overview").status_code == 200 and client.get("/api/hr/evaluation").status_code == 200
    any_hire = client.get("/api/hr/overview").json()["hires"][0]["id"]
    assert client.delete(f"/api/hr/employees/{any_hire}").status_code == 403                    # judges can't delete
    monkeypatch.delenv("JUDGE_ACCESS_KEY")
    client.cookies.clear()
    assert client.post("/api/auth/judge", json={"key": "judge-key-1234567890"}).status_code == 403  # switched off
