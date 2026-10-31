# Tamheed — AI onboarding agent

**Rimal Engineering & Technology** (fictional company, synthetic data) · HUMAIN AI Hackathon, Challenge 3.

HR adds a new hire (details + CV). One **Claude agent** with tools reads the CV, checks the role, team, course catalog,
company records and the web, then plans: which skills are proven (quoted from the CV), mentoring per responsibility,
courses (internal + found on the web), first-week actions and warnings for HR. A validator checks every plan before it is
saved. The pipeline then renders a personalised animated welcome video and emails the invitation.

The employee signs in, sets a password and finds everything ready: dashboard + video, tasks, responsibilities, training,
a practical exercise (designed and assessed by the agent) and an AI assistant that answers from company emails and
documents with sources. The agent re-plans when HR edits an employee, reviews progress when items are completed,
and marks onboarding complete (HR is notified; the person moves to existing employees after `GRADUATE_DAYS`).

## Run locally (Mac)

```bash
./scripts/setup.sh        # once: venv, Python + npm deps, .env, database
./scripts/dev.sh          # backend :8710 + frontend :5710  →  http://localhost:5710
```

| Account | Username | Password |
|---|---|---|
| HR (local demo only) | `hr@rimal.example` | `Rimal-HR-2026!` |
| New hire | the email HR enters | from the invitation email (temporary; must be changed) |

Other commands: `./scripts/test.sh` (tests) · `./scripts/reset_demo.sh` (wipe demo data; stop dev.sh first) ·
`scripts/issue_temp_password.py <email>` (temporary password without email) ·
`scripts/set_hr_password.py` (change the HR password) ·
`scripts/claude_smoke.py` (check the Claude key and tool calling).

## Configuration (`.env` locally, Railway variables in production — never commit)

| Variable | What |
|---|---|
| `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` | Claude (API usage is billed separately from a Claude.ai plan). Without a key everything falls back to labelled rule-based behaviour. |
| `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | Gmail with an **App Password** for invitation emails. |
| `EMAIL_ALLOWLIST` | `*` = any address, or a comma-separated list. |
| `APP_BASE_URL` | Link in invitation emails (on Railway it defaults to the public domain). |
| `HR_PASSWORD` | HR password for a **new** database (set this in production). |
| `GRADUATE_DAYS` | Days after completion before a hire becomes an existing employee (default 21). |
| `JUDGE_ACCESS_KEY` | Enables the one-click judge link `/#/judge?key=…` (separate HR account, can't delete). Remove to switch it off. |
| `COOKIE_SECURE` | `1` when served over HTTPS (set in the Dockerfile). |

## Deploy on Render

`render.yaml` describes the service (Docker, 1 instance, 1 GB disk at `/data`, health check). Push this folder to a
private GitHub repo → Render → **New → Blueprint** → pick the repo → fill in the secret variables
(`ANTHROPIC_API_KEY`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `HR_PASSWORD`) → **Apply**.
Invitation links use the `https://….onrender.com` address automatically.

## Evaluation (proof for the judges — HR → Evaluation tab)

```bash
cd backend
../.venv/bin/python -m eval.run_eval sonnet eval/results/sonnet.json   # Claude Sonnet 5.5 (used in production)
../.venv/bin/python -m eval.run_eval haiku  eval/results/haiku.json    # Claude Haiku 5.5 (cheaper alternative)
../.venv/bin/python -m eval.run_eval rules  eval/results/rules.json    # rule-based baseline, no AI
cd .. && .venv/bin/python scripts/test_report.py                        # automated tests → eval/results/tests.json
```

- `backend/eval/cases.py`: 12 held-out fictional hires (8 roles + missing CV, someone else's CV, hidden prompt-injection,
  minimal CV), each with an answer sheet of the skills the text really proves.
- Scored: skill accuracy, unsupported (wrongly credited) skills, mentors on the right team, gaps covered by a course,
  problems flagged to HR, injection resistance, safety-check catches, time and cost per hire; plus an adaptation test
  (project change) and a fallback test (Claude unavailable).
- `iterations.json` (what testing found and what changed) and `decisions.json` (trade-offs) are shown alongside.
- GitHub Actions runs the tests and the website build on every push (`.github/workflows/tests.yml`).

## Architecture

- `backend/app/main.py` — FastAPI: auth (bcrypt, httpOnly cookie), HR and employee APIs, ownership checks; serves the
  built website in production.
- `pipeline.py` — durable job pipeline in SQLite (record → CV → **agent plan** → tasks → mentoring → training →
  **exercise** → video → workspace → invitation, plus adapt / review / grade steps). Survives restarts, retryable.
- `agent.py` — the onboarding agent: Claude tool loop (profile & CV, role, team, course catalog, company records,
  web search) → `validate()` guardrails (quotes must appear in the CV, real courses/links/mentors/records) → plan.
  Re-planning and progress reviews. Falls back to the rule-based planner (`analysis.py`).
- `exercise.py` — practical exercises from company records; AI-assessed; adapts mentoring. Answer key never sent to the browser.
- `completion.py` — completion detection, HR notification, move to existing employees.
- `chat.py` — the employee assistant (Claude + scoped read-only tools, citations, where-to-find paths).
- `video.py` + `scriptgen.py` — animated two-host welcome video (Pillow + TTS + FFmpeg).
- `seed.py` / `seed_extra.py` — the fictional company: 6 departments, 10 roles, 5 projects, 21 staff, 34 emails,
  22 documents, courses.
- `frontend/` — React + TypeScript (HR and employee workspaces).
- `scripts/explainer/` — the 1-minute "behind the scenes" video (motion graphics + generated music).
