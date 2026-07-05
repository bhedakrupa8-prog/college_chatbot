"""
mailer.py  ---  sends admin answers to students via Gmail SMTP.

Setup (one time):
  1. Turn on 2-Step Verification on your Gmail account.
  2. Create an App Password:  Google Account -> Security -> App passwords.
  3. Set two environment variables before running app.py:

     Windows (cmd):
        set GMAIL_USER=youraddress@gmail.com
        set GMAIL_APP_PASSWORD=your16charapppassword

     Windows (PowerShell):
        $env:GMAIL_USER="youraddress@gmail.com"
        $env:GMAIL_APP_PASSWORD="your16charapppassword"

If the variables aren't set, emails are skipped (logged to console) so the
ticket flow still works during development.
"""

import os
import ssl
import smtplib
from email.message import EmailMessage

GMAIL_USER = os.environ.get("GMAIL_USER")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")


def is_configured():
    return bool(GMAIL_USER and GMAIL_APP_PASSWORD)


def send_email(to_address, subject, body):
    """Returns (ok: bool, info: str)."""
    if not is_configured():
        print(f"[mailer] not configured — would have emailed {to_address}: {subject}")
        return False, "Email not configured. Set GMAIL_USER and GMAIL_APP_PASSWORD."

    msg = EmailMessage()
    msg["From"] = GMAIL_USER
    msg["To"] = to_address
    msg["Subject"] = subject
    msg.set_content(body)

    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ctx) as server:
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            server.send_message(msg)
        return True, "sent"
    except Exception as e:
        print("[mailer] send failed:", e)
        return False, str(e)