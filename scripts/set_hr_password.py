"""Change the HR account's password (do this before putting the site online — the demo password is public).
Usage: .venv/bin/python scripts/set_hr_password.py   (you'll be prompted; nothing is printed or stored in plain text)"""
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.auth import hash_password  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.models import AuthSession, User  # noqa: E402

pw = getpass.getpass("New HR password (min 12 characters): ")
if len(pw) < 12 or pw != getpass.getpass("Repeat it: "):
    sys.exit("Passwords don't match or are too short.")
db = SessionLocal()
u = db.query(User).filter_by(kind="hr").first()
u.password_hash = hash_password(pw)
db.query(AuthSession).filter_by(user_id=u.id).delete()  # sign out existing HR sessions
db.commit()
print(f"Updated the password for {u.username}.")
