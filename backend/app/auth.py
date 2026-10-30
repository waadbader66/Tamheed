import hashlib
import secrets
from datetime import datetime, timedelta

import bcrypt
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .db import get_db
from .models import AuthSession, User

COOKIE = "tamheed_session"


def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def verify_password(pw: str, h: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode(), h.encode())
    except ValueError:
        return False


def temp_password() -> str:
    # readable but strong: e.g. Kq7m-Xp2R-v9Tz
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789"
    return "-".join("".join(secrets.choice(alphabet) for _ in range(4)) for _ in range(3))


def _h(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(db: Session, user: User) -> str:
    token = secrets.token_urlsafe(32)
    db.add(AuthSession(token_hash=_h(token), user_id=user.id, expires_at=datetime.utcnow() + timedelta(hours=12)))
    db.commit()
    return token


def drop_session(db: Session, token: str | None) -> None:
    if token:
        db.query(AuthSession).filter_by(token_hash=_h(token)).delete()
        db.commit()


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(COOKIE)
    if not token:
        raise HTTPException(401, "Not signed in")
    s = db.get(AuthSession, _h(token))
    if not s or s.expires_at < datetime.utcnow():
        raise HTTPException(401, "Session expired")
    user = db.get(User, s.user_id)
    if not user or not user.is_active:
        raise HTTPException(401, "Account disabled")
    return user


def require_hr(user: User = Depends(current_user)) -> User:
    if user.kind != "hr":
        raise HTTPException(403, "HR access only")
    return user


def require_employee(user: User = Depends(current_user)) -> User:
    if user.kind != "employee" or not user.employee_id:
        raise HTTPException(403, "Employee workspace only")
    if user.must_change_password:
        raise HTTPException(428, "Password change required")
    return user
