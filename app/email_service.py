"""
Servicio de envío de emails via SMTP.
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path

from app.config import SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM


def send_reset_code(to_email: str, nombre: str, codigo: str):
    """Enviar código de recuperación de contraseña."""
    # Cargar template
    template_path = Path(__file__).parent / "templates" / "reset_password.html"
    html = template_path.read_text(encoding="utf-8")
    html = html.replace("{{nombre}}", nombre)
    html = html.replace("{{codigo}}", codigo)

    # Construir mensaje
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Recuperar contraseña - Tornealo Sports"
    msg["From"] = SMTP_FROM
    msg["To"] = to_email
    msg.attach(MIMEText(html, "html"))

    # Enviar
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(SMTP_FROM, to_email, msg.as_string())
