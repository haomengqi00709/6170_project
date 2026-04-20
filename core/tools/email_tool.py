"""
Email Tool
----------
Sends real emails via Gmail SMTP.

Required .env variables:
    SMTP_FROM_EMAIL    — your Gmail address (e.g. yourname@gmail.com)
    SMTP_APP_PASSWORD  — Gmail App Password (Settings → Security → App passwords)

If credentials are missing, falls back to simulation mode (prints what would be sent).
"""

import os
import smtplib
import ssl
from dataclasses import dataclass
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465


@dataclass
class EmailResult:
    sent: bool
    to: List[str]
    subject: str
    body: str
    simulated: bool = False
    error: str = ""


def send_email(
    to: List[str],
    subject: str,
    body: str,
) -> EmailResult:
    """
    Send an email to one or more recipients.
    Returns EmailResult — always succeeds (falls back to simulation if no credentials).
    """
    from_email = os.getenv("SMTP_FROM_EMAIL", "").strip()
    app_password = os.getenv("SMTP_APP_PASSWORD", "").strip().replace(" ", "")

    # ── Simulation mode ───────────────────────────────────────────────────────
    if not from_email or not app_password:
        print("\n[EmailTool] SIMULATION MODE (no SMTP credentials configured)")
        print(f"  From:    {from_email or '(not set)'}")
        print(f"  To:      {', '.join(to)}")
        print(f"  Subject: {subject}")
        print(f"  Body:\n{_indent(body)}\n")
        return EmailResult(sent=True, to=to, subject=subject, body=body, simulated=True)

    # ── Real send ─────────────────────────────────────────────────────────────
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = from_email
        msg["To"]      = ", ".join(to)
        msg.attach(MIMEText(body, "plain"))

        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context) as server:
            server.login(from_email, app_password)
            server.sendmail(from_email, to, msg.as_string())

        print(f"\n[EmailTool] ✅ Email sent to: {', '.join(to)}")
        return EmailResult(sent=True, to=to, subject=subject, body=body, simulated=False)

    except Exception as e:
        print(f"\n[EmailTool] ❌ Send failed: {e}")
        return EmailResult(sent=False, to=to, subject=subject, body=body, error=str(e))


def _indent(text: str, prefix: str = "    ") -> str:
    return "\n".join(prefix + line for line in text.splitlines())
