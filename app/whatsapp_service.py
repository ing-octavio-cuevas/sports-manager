"""
Servicio de envío de mensajes por WhatsApp Cloud API (Meta).

Mensajes iniciados por el negocio (como recordatorios) DEBEN usar una plantilla
(template) pre-aprobada en Meta; no se permite texto libre fuera de la ventana
de servicio de 24h.

Uso:
    from app.whatsapp_service import send_recordatorio_asistencia
    send_recordatorio_asistencia(
        celular="5215512345678",
        nombre_capitan="Juan",
    )
"""

import logging
import re

import requests

from app.config import (
    WHATSAPP_TOKEN,
    WHATSAPP_PHONE_ID,
    WHATSAPP_API_VERSION,
    WHATSAPP_TEMPLATE_RECORDATORIO,
    WHATSAPP_TEMPLATE_LANG,
    WHATSAPP_DEFAULT_COUNTRY_CODE,
    WHATSAPP_ENABLED,
)

logger = logging.getLogger(__name__)

# Timeout (segundos) para la llamada HTTP a Meta.
_HTTP_TIMEOUT = 15


class WhatsAppError(Exception):
    """Error al enviar un mensaje por WhatsApp Cloud API."""


def normalizar_celular(celular: str) -> str | None:
    """
    Normaliza un celular a formato E.164 sin el signo '+' (como lo espera la Cloud API).

    - Quita espacios, guiones, paréntesis y el signo '+'.
    - Si no trae código de país (típico número MX de 10 dígitos), antepone
      WHATSAPP_DEFAULT_COUNTRY_CODE.
    Devuelve None si no se puede formar un número plausible.
    """
    if not celular:
        return None

    # Dejar solo dígitos
    digitos = re.sub(r"\D", "", celular)
    if not digitos:
        return None

    cc = WHATSAPP_DEFAULT_COUNTRY_CODE

    # Ya trae el código de país
    if digitos.startswith(cc) and len(digitos) > 10:
        normalizado = digitos
    # Número nacional de 10 dígitos (MX) -> anteponer código de país
    elif len(digitos) == 10:
        normalizado = f"{cc}{digitos}"
    else:
        # Longitud inesperada: si ya parece internacional (>=11) lo dejamos tal cual,
        # de lo contrario lo descartamos.
        normalizado = digitos if len(digitos) >= 11 else None

    return normalizado


def _post_message(payload: dict) -> dict:
    """Ejecuta el POST a la Graph API y devuelve el JSON de respuesta. Lanza WhatsAppError si falla."""
    url = f"https://graph.facebook.com/{WHATSAPP_API_VERSION}/{WHATSAPP_PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=_HTTP_TIMEOUT)
    except requests.RequestException as exc:
        raise WhatsAppError(f"Fallo de red al llamar a WhatsApp Cloud API: {exc}") from exc

    if resp.status_code >= 400:
        # No exponemos el token; solo el cuerpo de error de Meta.
        raise WhatsAppError(
            f"WhatsApp Cloud API respondió {resp.status_code}: {resp.text}"
        )

    return resp.json()


def send_template_message(
    to_celular: str,
    template_name: str,
    body_params: list[str],
    lang_code: str = WHATSAPP_TEMPLATE_LANG,
) -> dict:
    """
    Envía un mensaje de plantilla.

    body_params: valores para las variables {{1}}, {{2}}, ... del cuerpo de la plantilla,
    en orden.
    """
    if not WHATSAPP_ENABLED:
        raise WhatsAppError(
            "WhatsApp Cloud API no está configurado (falta WHATSAPP_TOKEN o WHATSAPP_PHONE_ID)."
        )

    numero = normalizar_celular(to_celular)
    if not numero:
        raise WhatsAppError(f"Número de celular inválido: {to_celular!r}")

    payload = {
        "messaging_product": "whatsapp",
        "to": numero,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": lang_code},
            "components": [
                {
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": str(p)} for p in body_params
                    ],
                }
            ],
        },
    }

    return _post_message(payload)


def send_recordatorio_asistencia(
    celular: str,
    nombre_capitan: str,
) -> dict:
    """
    Envía un único recordatorio al capitán agrupando todos sus partidos pendientes del día.

    La plantilla WHATSAPP_TEMPLATE_RECORDATORIO tiene 1 variable en el cuerpo
    (el enlace va como texto estático dentro de la plantilla, no como variable):
        {{1}} = nombre del capitán
    """
    return send_template_message(
        to_celular=celular,
        template_name=WHATSAPP_TEMPLATE_RECORDATORIO,
        body_params=[nombre_capitan],
    )
