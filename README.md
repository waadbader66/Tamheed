# Tamheed — AI onboarding agent

**Rimal Engineering & Technology** (a fictional company with synthetic data) · HUMAIN AI Hackathon, Challenge 3.

Live demo: **https://tamheed.onrender.com**. Judges can leave the username and password empty and click **Sign in**.

---

## What it does

```
HR adds a new hire ──► Claude agent plans ──► Welcome video ──► Invitation email ──► New hire's workspace
 (details + CV)        (reads CV, role,       (Sara & Ahmed,     (username +          dashboard · tasks ·
                        team, courses, web;    personalised)      temporary password)  responsibilities ·
                        validator checks it)                                           training · exercise ·
                                                                                       AI assistant
```

1. **HR** signs in and adds an employee: name, ID, role, department, manager, responsibilities and CV.
2. **One Claude agent** works through tools:
   - Inputs: the CV, the role requirements, the team, the course catalog, the company emails and documents, and web search.
   - Output: a plan covering skills already proven (each quoted from the CV), mentoring for each responsibility,
     internal and external courses, a short practical exercise, and warnings for HR.
   - HR sees the agent's reasoning live.
   - A **validator** rejects anything not backed by the data before the plan is saved.
3. **The pipeline** renders a personalised animated welcome video (hosts Sara and Ahmed) and emails the invitation.
4. **The new hire** signs in with their email and the temporary password, sets their own password, and finds everything
   ready. The assistant answers questions from company records and cites its sources.
5. **The agent keeps working after day one**:
   - It re-plans when HR edits the employee.
   - It reviews progress as items are completed.
   - It grades the practical exercise and adapts the plan.
   - It tells HR when onboarding is complete. After `GRADUATE_DAYS` the person moves to existing employees.

Without a Claude key, every step falls back to a clearly labelled rule-based version, so the app still runs end to end.

---

## Run it on your computer

### 1. Requirements

| Tool | Version | Install (macOS) | Why |
|---|---|---|---|
| Git | any | `xcode-select --install` | download the code |
| Python | 3.11+ (3.12 recommended) | https://www.python.org/downloads/ | backend |
| Node.js | 20+ | https://nodejs.org | website |
| FFmpeg | any | `brew install ffmpeg` | welcome videos (optional) |

On Linux, install `ffmpeg espeak-ng` with your package manager for videos. macOS already has a voice engine (`say`).
On Windows, use **WSL** (Ubuntu) and follow the Linux steps, or use Docker (option B below).

### 2A. Quick start (macOS / Linux)

```bash
git clone https://github.com/waadbader66/Tamheed.git
cd Tamheed
./scripts/setup.sh      # once: Python env, packages, website packages, .env file, demo database
./scripts/dev.sh        # starts everything; Ctrl+C to stop
```

Open **http://localhost:5710**.

| Who | Username | Password |
|---|---|---|
| HR | `hr@rimal.example` | `Rimal-HR-2026!` |
| Judge (HR view, can't delete) | leave empty | leave empty, then click **Sign in** |
| New hire | the email HR entered | the temporary password from the invitation email (you set your own next) |

### 2B. Docker (any OS)

```bash
git clone https://github.com/waadbader66/Tamheed.git
cd Tamheed
cp .env.example .env    # optional: add keys (step 3)
docker build -t tamheed .
docker run --rm -p 8000:8000 --env-file .env -e COOKIE_SECURE=0 -e APP_BASE_URL=http://localhost:8000 -v tamheed-data:/data tamheed
```

Open **http://localhost:8000**. The accounts are the same as above.

### 3. Turn on Claude and email (optional)

Edit the `.env` file in the project folder, then restart `./scripts/dev.sh`.

```ini
ANTHROPIC_API_KEY=...         # https://console.anthropic.com → API Keys (needs API credits)
SMTP_USER=you@gmail.com       # Gmail address that sends invitations
SMTP_PASSWORD=...             # a Gmail *App Password*, not your normal password
SMTP_FROM=you@gmail.com
```

- Check the Claude key with `.venv/bin/python scripts/claude_smoke.py`.
- Without email set up, the invitation is still prepared. To create a sign-in for the new hire yourself, run
  `.venv/bin/python scripts/issue_temp_password.py their@email.com`. It prints a temporary password in the terminal.
- **Never commit `.env`.** It is already listed in `.gitignore`.

### 4. Try the full flow (about 3 minutes)

1. Sign in as **HR** and open **Add employee**.
2. Fill in the details and upload a CV. Samples are in `data/samples/`.
3. Watch the agent's reasoning in the **Onboarding progress** tab.
4. When the invitation is sent, sign out and sign in as the new hire using the email and temporary password.
5. Set a password, then explore: the dashboard and video, Tasks, Responsibilities, Training, Practical exercise and the AI assistant.
6. Back in HR, check **Evaluation** for the test results and measurements.

### Useful commands

| Command | What it does |
|---|---|
| `./scripts/test.sh` | run the automated tests (14) |
| `./scripts/reset_demo.sh` | wipe demo data and re-create the fictional company (stop `dev.sh` first) |
| `.venv/bin/python scripts/set_hr_password.py` | change the HR password |
| `.venv/bin/python scripts/issue_temp_password.py <email>` | temporary password for a new hire, without email |
| `.venv/bin/python scripts/claude_smoke.py` | check the Claude key and tool calling |
| `./scripts/start_prod.sh` | build the website and serve everything from one port (8000) |

### Troubleshooting

| Problem | Fix |
|---|---|
| `permission denied: ./scripts/setup.sh` | `chmod +x scripts/*.sh` |
| Port 5710 or 8710 already in use | stop the other program, or `lsof -i :5710` to find it |
| Video step fails | install FFmpeg (and `espeak-ng` on Linux), then click **Retry failed step** on the hire in HR |
| Plans say "Rules" instead of "Claude" | `ANTHROPIC_API_KEY` is missing, wrong or out of credits; run `claude_smoke.py` |
| Gmail error 535 | use an App Password, and make sure `SMTP_USER` is the same Gmail account |
| Signed out unexpectedly | the database was reset; sign in again |

---

## Configuration (`.env` locally, host variables in production)

| Variable | What |
|---|---|
| `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` | Claude (default `claude-sonnet-5-5`). Without a key, everything uses the labelled rule-based fallback. |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | Sending invitation emails (Gmail with an App Password). |
| `EMAIL_ALLOWLIST` | `*` = any address, or a comma-separated list. |
| `APP_BASE_URL` | Link inside invitation emails (on Render it uses the public address automatically). |
| `HR_PASSWORD` | HR password for a **new** database. Set this in production. |
| `GRADUATE_DAYS` | Days after completion before a hire becomes an existing employee (default 21). |
| `JUDGE_ACCESS` | Judge sign-in (empty username and password) is **on** by default. Set `off` to disable. |
| `COOKIE_SECURE` | `1` when served over HTTPS (set in the Dockerfile). |

## Deploy on Render

`render.yaml` describes the service: Docker, 1 instance, a 1 GB disk at `/data`, and a health check.

1. Push to GitHub.
2. In Render, choose **New → Blueprint** and pick the repo.
3. Fill in the secrets: `ANTHROPIC_API_KEY`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` and `HR_PASSWORD`.
4. Click **Apply**.

Every push to `main` redeploys automatically.

---

## Evaluation (HR → Evaluation tab)

```bash
cd backend
../.venv/bin/python -m eval.run_eval sonnet eval/results/sonnet.json   # Claude Sonnet 5.5 (used in production)
../.venv/bin/python -m eval.run_eval haiku  eval/results/haiku.json    # Claude Haiku 5.5 (cheaper alternative)
../.venv/bin/python -m eval.run_eval rules  eval/results/rules.json    # rule-based baseline, no AI
../.venv/bin/python -m eval.validator_check eval/results/validator.json  # planted-error test of the validator (free, no AI)
cd .. && .venv/bin/python scripts/test_report.py                        # automated tests → eval/results/tests.json
```

- `backend/eval/cases.py` holds 12 held-out fictional hires. They cover 8 roles plus four hard cases: a missing CV,
  someone else's CV, a hidden prompt injection and a minimal CV. Each case has an answer sheet listing the skills its
  text really proves.
- Scores cover:
  - skill accuracy and unsupported (wrongly credited) skills;
  - mentors on the right team, and skill gaps covered by a course;
  - problems flagged to HR, injection resistance and validator catches;
  - time and cost per hire;
  - an adaptation test (project change) and a fallback test (Claude unavailable).
- **Does the validator matter?** `validator_check.py` plants 7 kinds of mistakes (invented CV quote, fake mentor,
  made-up course, unverified link, out-of-scope record, ungrounded background, missing responsibility) into plans for the
  same 12 hires. Result: **84/84 caught with the validator, 0/84 without it**, and 100% of valid evidence kept.
- `iterations.json` records what testing found and what changed. `decisions.json` records the trade-offs.
- GitHub Actions runs the tests and the website build on every push (`.github/workflows/tests.yml`).

## Architecture

```
frontend/ (React + TypeScript, Vite)                       backend/ (FastAPI + SQLite)
  Login · HR workspace · Employee workspace    ──/api──►     main.py        auth, HR & employee APIs, serves built site
                                                             pipeline.py    durable job pipeline (survives restarts)
                                                             agent.py       Claude tool loop + validate() guardrails
                                                             exercise.py    practical exercise: design, grade, adapt
                                                             completion.py  completion → HR notice → existing staff
                                                             chat.py        employee assistant with citations
                                                             video.py       Pillow frames + TTS + FFmpeg
                                                             seed*.py       the fictional company data
```

- **Pipeline steps:** record → CV → **agent plan** → tasks → mentoring → training → **exercise** → video → workspace →
  invitation. Adapt, review and grade steps are added later as needed. Each step is retryable.
- **Agent tools:** `get_new_hire_profile`, `get_role_requirements`, `get_team`, `search_course_catalog`,
  `search_company_records`, web search and `submit_onboarding_plan`.
- **Guardrails:**
  - CV quotes must appear in the CV.
  - Courses must exist in the catalog or come from verified web results.
  - Mentors must be on the hire's team.
  - Record IDs must be in scope.
  - Exercise answer keys never reach the browser.
- **Fictional company:** 6 departments, 10 roles, 5 projects, 21 staff, 34 emails, 22 documents and a course catalog.
- **`scripts/explainer/`:** the 1-minute "behind the scenes" video (motion graphics and generated music).

## Project layout

```
Tamheed/
├── backend/        app/ (API + agent), eval/ (evaluation), tests/, requirements.txt
├── frontend/       src/ (React pages), package.json
├── data/samples/   sample CVs for the demo
├── scripts/        setup, dev, test, reset, admin helpers, explainer video
├── Dockerfile      production image (website + API + ffmpeg)
├── render.yaml     Render deployment
└── .env.example    configuration template → copy to .env
```
