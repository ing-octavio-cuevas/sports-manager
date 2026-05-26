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

# ─── Roles ───────────────────────────────────────────────────

ROL_ANFITRION = "anfitrion"
ROL_ARBITRO = "arbitro"
ROL_JUGADOR = "jugador"
