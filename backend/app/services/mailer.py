"""Optional SMTP sender (stdlib only). If SMTP is not configured, nothing is sent and callers are told so."""
import asyncio
import smtplib
from email.message import EmailMessage

from app.core.config import get_settings


def smtp_configured() -> bool:
    s = get_settings()
    return bool(s.SMTP_HOST.strip() and (s.SMTP_FROM.strip() or s.SMTP_USER.strip()))


def _send(to: str, subject: str, body: str) -> None:
    s = get_settings()
    msg = EmailMessage()
    msg["From"] = s.SMTP_FROM or s.SMTP_USER
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    with smtplib.SMTP(s.SMTP_HOST, s.SMTP_PORT, timeout=15) as srv:
        srv.starttls()
        if s.SMTP_USER:
            srv.login(s.SMTP_USER, s.SMTP_PASSWORD)
        srv.send_message(msg)


async def send_email(to: str, subject: str, body: str) -> tuple[bool, str]:
    if not smtp_configured():
        return False, "SMTP is not configured (set SMTP_HOST / SMTP_FROM in backend/.env)."
    try:
        await asyncio.to_thread(_send, to, subject, body)
        return True, "sent"
    except Exception as e:  # network/auth errors must never crash the request
        return False, f"Could not send e-mail: {e.__class__.__name__}"
