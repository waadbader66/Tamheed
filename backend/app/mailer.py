"""Invitation email delivery over SMTP. Status is reported honestly: 'sent' = SMTP server accepted the message."""
import os
import smtplib
from email.message import EmailMessage

from . import config


def normalise(addr: str) -> str:
    addr = addr.strip().lower()
    local, _, domain = addr.partition("@")
    if domain in ("gmail.com", "googlemail.com"):
        local = local.split("+")[0].replace(".", "")
    return f"{local}@{domain}"


def allowed(addr: str) -> bool:
    """EMAIL_ALLOWLIST='*' (or empty) sends to any address; otherwise only to the listed ones."""
    raw = {a.strip().lower() for a in os.environ.get("EMAIL_ALLOWLIST", ",".join(config.EMAIL_ALLOWLIST)).split(",") if a.strip()}
    if not raw or "*" in raw:
        return True
    return normalise(addr) in {normalise(a) for a in raw}


def sender_configured() -> bool:
    return bool(os.environ.get("SMTP_USER", config.SMTP_USER) and os.environ.get("SMTP_PASSWORD", config.SMTP_PASSWORD))


def build(to: str, name: str, username: str, password: str, link: str, ready: dict) -> EmailMessage:
    m = EmailMessage()
    m["Subject"] = f"Welcome to {config.COMPANY_NAME}, {name.split()[0]} — your sign-in details"
    m["From"] = f"{config.COMPANY_NAME} HR via {config.PRODUCT_NAME} <{os.environ.get('SMTP_FROM') or os.environ.get('SMTP_USER', config.SMTP_USER)}>"
    m["To"] = to
    first = name.split()[0]
    text = (f"Hi {first},\n\nWelcome to {config.COMPANY_NAME}! Your personalised onboarding space is ready.\n\n"
            f"Sign in: {link}\nUsername: {username}\nTemporary password: {password}\n\n"
            f"You will be asked to choose your own password when you first sign in. The temporary password expires in 7 days.\n\n"
            f"Waiting for you: a personalised welcome video, {ready['tasks']} onboarding tasks, {ready['resp']} first responsibilities and {ready['courses']} recommended courses.\n\n"
            f"— {config.COMPANY_NAME} HR")
    html = f"""<div style="font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;max-width:560px;margin:auto;color:#0f2a2e">
<div style="background:#0d5c63;color:#fff;padding:28px;border-radius:14px 14px 0 0">
<div style="font-size:13px;opacity:.8;letter-spacing:.08em;text-transform:uppercase">{config.COMPANY_NAME}</div>
<div style="font-size:26px;font-weight:700;margin-top:6px">Welcome, {first}!</div>
<div style="opacity:.9;margin-top:6px">Your personalised onboarding space is ready.</div></div>
<div style="border:1px solid #d9e6e6;border-top:0;padding:28px;border-radius:0 0 14px 14px">
<p>We've prepared everything for your first days:</p>
<ul><li>A personalised welcome video about your role, team and project</li>
<li>{ready['tasks']} onboarding tasks (paperwork, equipment, access)</li>
<li>{ready['resp']} first responsibilities with mentoring support</li>
<li>{ready['courses']} recommended training courses</li></ul>
<table style="background:#f2f8f8;border-radius:10px;padding:14px;width:100%;margin:18px 0"><tr><td style="padding:6px 10px;color:#4c6a6d">Username</td><td style="padding:6px 10px;font-weight:600">{username}</td></tr>
<tr><td style="padding:6px 10px;color:#4c6a6d">Temporary password</td><td style="padding:6px 10px;font-family:Menlo,monospace;font-weight:600">{password}</td></tr></table>
<a href="{link}" style="display:inline-block;background:#0d5c63;color:#fff;text-decoration:none;padding:12px 22px;border-radius:10px;font-weight:600">Open my onboarding</a>
<p style="color:#4c6a6d;font-size:13px;margin-top:22px">You'll choose your own password at first sign-in. The temporary password expires in 7 days.<br>Tip: copy the password exactly as shown (letters, numbers and dashes).</p>
</div></div>"""
    m.set_content(text)
    m.add_alternative(html, subtype="html")
    return m


def send(msg: EmailMessage) -> None:
    host = os.environ.get("SMTP_HOST", config.SMTP_HOST)
    port = int(os.environ.get("SMTP_PORT", config.SMTP_PORT))
    with smtplib.SMTP(host, port, timeout=30) as s:
        s.ehlo(); s.starttls(); s.ehlo()
        # Single AUTH PLAIN attempt: smtplib's fallback to AUTH LOGIN makes Gmail drop the connection and hides the real error.
        s.user = os.environ.get("SMTP_USER", config.SMTP_USER)
        s.password = os.environ.get("SMTP_PASSWORD", config.SMTP_PASSWORD).replace(" ", "")  # Gmail shows app passwords with spaces
        try:
            s.auth("PLAIN", s.auth_plain, initial_response_ok=True)
        except smtplib.SMTPAuthenticationError as e:
            raise RuntimeError("Gmail rejected the username or app password (535). Create a new App Password and update .env.") from e
        s.send_message(msg)
