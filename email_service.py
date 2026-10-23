
# email_service.py

import os
import re
import ssl
import smtplib
from email.message import EmailMessage
from email.utils import parseaddr
from dotenv import load_dotenv

load_dotenv()

def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"La variable {name} est absente du fichier .env.")
    return value

def _validate_email(address: str) -> str:
    address = address.strip()
    _, parsed = parseaddr(address)

    if parsed != address or not re.fullmatch(
        r"[^@\s]+@[^@\s]+\.[^@\s]+", address
    ):
        raise ValueError(f"Adresse email invalide : {address}")

    return address

def send_email_smtp(to: str, subject: str, body: str) -> dict:
    sender = _validate_email(_required_env("SMTP_EMAIL"))
    password = _required_env("SMTP_PASSWORD")
    host = os.getenv("SMTP_HOST", "smtp.gmail.com").strip()
    port = int(os.getenv("SMTP_PORT", "587"))

    recipient = _validate_email(to)

    if not subject.strip():
        raise ValueError("L'objet de l'email est obligatoire.")
    if not body.strip():
        raise ValueError("Le contenu de l'email est obligatoire.")

    message = EmailMessage()
    message["From"] = (
        f"{os.getenv('SMTP_FROM_NAME', 'Personal AI Agent')} <{sender}>"
    )
    message["To"] = recipient
    message["Subject"] = subject.strip()
    message.set_content(body.strip())

    try:
        context = ssl.create_default_context()

        with smtplib.SMTP(host, port, timeout=30) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            server.login(sender, password)
            server.send_message(message)
            print(f"SMTP : message accepté pour {recipient} avec l'objet '{subject.strip()}'.")

        return {
            "success": True,
            "recipient": recipient,
            "subject": subject.strip(),
            "message": "Email accepté par le serveur SMTP.",
        }

    except (smtplib.SMTPException, OSError) as exc:
        print(f"Échec SMTP : {type(exc).__name__}: {exc}")
        raise
