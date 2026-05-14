"""
Configuración de la base de datos PostgreSQL y AWS.
Modifica estos valores según tu entorno local.
"""
import os
from urllib.parse import quote_plus

# ─── Base de datos ───────────────────────────────────────────

DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")

DATABASE_URL = f"postgresql://{DB_USER}:{quote_plus(DB_PASSWORD)}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# ─── AWS S3 ─────────────────────────────────────────────────

S3_BUCKET = os.getenv("S3_BUCKET", "vsportmanager-fotos")
S3_REGION = os.getenv("S3_REGION", "us-east-1")
S3_URL_BASE = f"https://{S3_BUCKET}.s3.{S3_REGION}.amazonaws.com"

# ─── JWT ─────────────────────────────────────────────────────

SECRET_KEY = os.getenv("SECRET_KEY", "tu-clave-secreta-cambiar-en-produccion")

# ─── Roles ───────────────────────────────────────────────────

ROL_ANFITRION = "anfitrion"
ROL_ARBITRO = "arbitro"
ROL_JUGADOR = "jugador"
