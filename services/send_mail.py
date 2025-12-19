## File: `services/send_email.py`

import os
import smtplib
import ssl
from email.message import EmailMessage
from dotenv import load_dotenv
load_dotenv()

SENDER = os.getenv("SENDER_EMAIL")
PASSWORD = os.getenv("SENDER_PASSWORD")


def send_email(receiver_email: str, subject: str, body: str) -> dict:
    if not receiver_email:
        return {"ok": False, "reason": "missing receiver email"}
    message = EmailMessage()
    message['From'] = SENDER or "no-reply@example.com"
    message['To'] = receiver_email
    message['Subject'] = subject
    message.set_content(body)
    if SENDER and PASSWORD:
        try:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as smtp:
                smtp.login(SENDER, PASSWORD)
                smtp.send_message(message)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "reason": str(e)}
    else:
        print("=== EMAIL (dev fallback) ===")
        print("To:", receiver_email)
        print("Subject:", subject)
        print(body)
        return {"ok": True, "note": "printed (no SMTP configured)"}