import smtplib
import os

from email.mime.text import MIMEText
from dotenv import load_dotenv

load_dotenv()

EMAIL = os.getenv("MAIL_EMAIL")
PASSWORD = os.getenv("MAIL_PASSWORD")


def send_email(receiver, subject, body):

    msg = MIMEText(body, "html")

    msg["Subject"] = subject
    msg["From"] = EMAIL
    msg["To"] = receiver

    server = smtplib.SMTP("smtp.gmail.com", 587)

    server.starttls()

    server.login(EMAIL, PASSWORD)

    server.send_message(msg)

    server.quit()