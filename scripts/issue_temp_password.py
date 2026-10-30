"""LOCAL DEV ONLY: issue a temporary password for a new hire when email sending isn't configured yet.
Prints it to this terminal only (never stored in plaintext). Usage: .venv/bin/python scripts/issue_temp_password.py name@example.com"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.auth import hash_password, temp_password  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.models import User  # noqa: E402

db = SessionLocal()
u = db.query(User).filter_by(username=sys.argv[1].strip().lower(), kind="employee").first()
if not u:
    sys.exit("No employee account with that username.")
pw = temp_password()
import json
h = hash_password(pw)
u.password_hash, u.must_change_password, u.temp_password_expires = h, True, datetime.utcnow() + timedelta(days=7)
u.temp_hashes_json = json.dumps(json.loads(u.temp_hashes_json or "[]") + [h])
db.commit()
print(f"Username: {u.username}\nTemporary password: {pw}\n(You'll be asked to set a new password on first sign-in.)")
