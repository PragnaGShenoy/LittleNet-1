import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

EMAIL = os.getenv("MAIL_EMAIL")
PASSWORD = os.getenv("MAIL_PASSWORD")


def send_email(receiver, subject, body):
    """
    Sends an HTML email to the receiver.
    Gracefully catches and logs any SMTP errors to ensure system resilience.
    """
    if not EMAIL or not PASSWORD:
        print(f"[MAIL WARN] Mail credentials not set in .env. Email to {receiver} logged to console:\nSubject: {subject}\n")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"LittleNet Safe Supervision <{EMAIL}>"
        msg["To"] = receiver

        html_part = MIMEText(body, "html")
        msg.attach(html_part)

        server = smtplib.SMTP("smtp.gmail.com", 587, timeout=10)
        server.starttls()
        server.login(EMAIL, PASSWORD)
        server.send_message(msg)
        server.quit()
        print(f"[MAIL SUCCESS] Sent email to {receiver} | Subject: {subject}")
        return True
    except Exception as e:
        print(f"[MAIL ERROR] Could not deliver email to {receiver}: {e}")
        return False