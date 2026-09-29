"""
Configuración de la base de datos PostgreSQL y AWS.
Modifica estos valores según tu entorno local.
"""
import os
from dotenv import load_dotenv

load_dotenv()  # Carga variables desde .env o .env.example
if not os.getenv("S3_BUCKET"):
    load_dotenv(".env.example")
from urllib.parse import quote_plus

# ─── Base de datos ───────────────────────────────────────────

DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "root")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "volei")

DATABASE_URL = f"postgresql://{DB_USER}:{quote_plus(DB_PASSWORD)}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# ─── AWS S3 ─────────────────────────────────────────────────

S3_BUCKET = os.getenv("S3_BUCKET", "")
S3_REGION = os.getenv("S3_REGION", "us-east-1")
S3_URL_BASE = f"https://{S3_BUCKET}.s3.{S3_REGION}.amazonaws.com" if S3_BUCKET else ""
USE_S3 = bool(S3_BUCKET)  # Si no hay bucket configurado, guarda en local

# ─── JWT ─────────────────────────────────────────────────────

SECRET_KEY = os.getenv("SECRET_KEY", "tu-clave-secreta-cambiar-en-produccion")

# ─── Zona horaria ────────────────────────────────────────────

TIMEZONE_OFFSET = -6  # México Central (UTC-6)

# ─── Email SMTP ──────────────────────────────────────────────

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", "")

# ─── WhatsApp Cloud API ──────────────────────────────────────
# Credenciales de la WhatsApp Cloud API (Meta). Se configuran en el .env del servidor.
#   WHATSAPP_TOKEN     : token de acceso permanente del System User de Meta
#   WHATSAPP_PHONE_ID  : Phone Number ID del número emisor (no el número en sí)
#   WHATSAPP_API_VERSION : versión del Graph API (ej. "v21.0")

WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN", "")
WHATSAPP_PHONE_ID = os.getenv("WHATSAPP_PHONE_ID", "")
WHATSAPP_API_VERSION = os.getenv("WHATSAPP_API_VERSION", "v21.0")

# Nombre e idioma de la plantilla (template) pre-aprobada en Meta para el recordatorio.
WHATSAPP_TEMPLATE_RECORDATORIO = os.getenv("WHATSAPP_TEMPLATE_RECORDATORIO", "recordatorio_asistencia")
WHATSAPP_TEMPLATE_LANG = os.getenv("WHATSAPP_TEMPLATE_LANG", "es_MX")

# Código de país por defecto para normalizar celulares a formato E.164 (México = 52).
WHATSAPP_DEFAULT_COUNTRY_CODE = os.getenv("WHATSAPP_DEFAULT_COUNTRY_CODE", "52")

# True solo si hay token y phone id configurados.
WHATSAPP_ENABLED = bool(WHATSAPP_TOKEN and WHATSAPP_PHONE_ID)

# ─── Recordatorios de asistencia ─────────────────────────────
# El job corre a horas fijas (hora local UTC-6) y revisa si algún capitán tiene
# asistencias pendientes por registrar, dentro del horario permitido y en partidos
# aún no terminados. Lista de horas separadas por coma (formato 24h).
_reminder_hours_raw = os.getenv("REMINDER_HOURS", "8,20")
REMINDER_HOURS = [
    int(h.strip()) for h in _reminder_hours_raw.split(",") if h.strip().isdigit()
]
# Interruptor general del scheduler de recordatorios.
REMINDER_ENABLED = os.getenv("REMINDER_ENABLED", "true").lower() in ("1", "true", "yes")

# ─── Prueba controlada (temporal) ────────────────────────────
# Si se definen ambas, al arrancar la app se programa UN envío de prueba a la hora
# indicada (hora local UTC-6, formato HH:MM) al número dado, con datos dummy.
# Sirve para validar la integración con Meta sin depender de datos reales.
# Dejar vacías en operación normal.
TEST_REMINDER_TIME = os.getenv("TEST_REMINDER_TIME", "")          # ej. "16:30"
TEST_REMINDER_CELULAR = os.getenv("TEST_REMINDER_CELULAR", "")    # ej. "525512345678"
TEST_REMINDER_NOMBRE = os.getenv("TEST_REMINDER_NOMBRE", "Capitán de Prueba")

# ─── Roles ───────────────────────────────────────────────────

ROL_ANFITRION = "anfitrion"
ROL_ARBITRO = "arbitro"
ROL_JUGADOR = "jugador"
