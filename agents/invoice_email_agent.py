# agents/invoice_email_agent.py
import smtplib
from email.message import EmailMessage
import os
from dotenv import load_dotenv
from .invoice_templates import get_invoice_html
load_dotenv()

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASS = os.getenv("PASSWORD")

import smtplib
from email.message import EmailMessage
import os
from dotenv import load_dotenv
from .invoice_templates import get_invoice_html

load_dotenv()

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASS = os.getenv("PASSWORD")


def send_to_finance(summary: dict, detailed_invoice: dict, finance_email: str):
    """
    Sends finance email using LLM-generated subject + body.
    NO business logic here. Rendering only.
    """
    if not finance_email:
        print("⚠️ No finance email configured; skipping send_to_finance")
        return

    if not summary:
        print("⚠️ Missing summary; cannot send finance email")
        return

    msg = EmailMessage()
    msg["From"] = SENDER_EMAIL
    msg["To"] = finance_email
    msg["Subject"] = summary.get(
        "email_subject_finance", "Invoice Review Notification"
    )

    # ---- TEXT BODY (LLM GENERATED) ----
    msg.set_content(summary.get("email_body_finance", ""))

    # ---- HTML BODY (LLM-AWARE TEMPLATE) ----
    html_content = get_invoice_html(
        invoice=detailed_invoice,
        summary=summary
    )
    msg.add_alternative(html_content, subtype="html")

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as smtp:
            smtp.starttls()
            smtp.login(SENDER_EMAIL, SENDER_PASS)
            smtp.send_message(msg)

        print("✅ Finance email sent successfully")

    except Exception as e:
        print("❌ send_to_finance error:", e)


def send_to_vendor(parsed_invoice: dict, vendor_email: str):
    if not vendor_email:
        print("No vendor email configured; skipping send_to_vendor")
        return
    msg = EmailMessage()
    msg["From"] = SENDER_EMAIL
    msg["To"] = vendor_email
    msg["Subject"] = f"Invoice {parsed_invoice.get('invoice_no')} - Action Required"
    body = f"Invoice flagged with anomalies:\n\n{parsed_invoice}\n\n"
    msg.set_content(body)
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
            s.starttls()
            s.login(SENDER_EMAIL, SENDER_PASS)
            s.send_message(msg)
        print("Sent vendor email.")
    except Exception as e:
        print("send_to_vendor error:", e)
