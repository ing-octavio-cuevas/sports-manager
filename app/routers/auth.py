from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from passlib.context import CryptContext

from app.database import get_db
from app.models import Usuario
from app.schemas import LoginRequest, TokenResponse, UsuarioResponse
from app.auth import create_access_token, get_current_user
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/auth", tags=["Auth"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    """Iniciar sesión con celular + password."""
    usuario = db.query(Usuario).filter(Usuario.celular == data.celular).first()
    if not usuario or not pwd_context.verify(data.password, usuario.password_hash):
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")
    if not usuario.estatus:
        raise HTTPException(status_code=401, detail="Usuario inactivo")

    # Si solo tiene rol jugador, verificar que tenga al menos un equipo activo
    if "jugador" in usuario.roles and "anfitrion" not in usuario.roles:
        from app.models import Jugador, Equipo
        tiene_equipo_activo = db.query(Jugador).join(Equipo, Jugador.equipo_id == Equipo.id).filter(
            Jugador.usuario_id == usuario.id,
            Equipo.estatus == True,
        ).first()
        if not tiene_equipo_activo:
            raise HTTPException(status_code=403, detail="No estás inscrito en ningún torneo activo")

    token = create_access_token(data={"sub": str(usuario.id)})

    return TokenResponse(
        access_token=token,
        usuario=UsuarioResponse(
            id=usuario.id,
            celular=usuario.celular,
            email=usuario.email,
            nombre=usuario.nombre,
            roles=usuario.roles,
            estatus=usuario.estatus,
            requiere_cambio_password=usuario.requiere_cambio_password,
            anfitrion_id=usuario.anfitrion_id,
            fecha_creacion=usuario.fecha_creacion,
        ),
    )


@router.get("/me", response_model=UsuarioResponse)
def get_me(usuario: Usuario = Depends(get_current_user)):
    """Obtener datos del usuario logueado."""
    return usuario


class CambiarPasswordRequest(BaseModel):
    new_password: str


@router.put("/cambiar-password", status_code=200)
def cambiar_password(data: CambiarPasswordRequest, db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_user)):
    """Cambiar contraseña del usuario logueado. Quita la bandera requiere_cambio_password."""
    usuario.password_hash = pwd_context.hash(data.new_password)
    usuario.requiere_cambio_password = False
    db.commit()
    return {"detail": "Contraseña actualizada"}


# ─── Recuperar contraseña ────────────────────────────────────

import random
import string
from datetime import datetime, timedelta, timezone
from app.config import TIMEZONE_OFFSET


class RecuperarPasswordRequest(BaseModel):
    celular: Optional[str] = None
    email: Optional[str] = None


class VerificarCodigoRequest(BaseModel):
    celular: Optional[str] = None
    email: Optional[str] = None
    codigo: str
    new_password: str


# Almacén temporal de códigos (en producción usar Redis o BD)
_codigos_reset = {}


@router.post("/recuperar-password", status_code=200)
def recuperar_password(data: RecuperarPasswordRequest, db: Session = Depends(get_db)):
    """
    Solicitar recuperación de contraseña.
    Envía un código de 6 dígitos al email del usuario.
    """
    if not data.celular and not data.email:
        raise HTTPException(status_code=400, detail="Debes proporcionar celular o email")

    # Buscar usuario
    if data.celular:
        usuario = db.query(Usuario).filter(Usuario.celular == data.celular).first()
    else:
        usuario = db.query(Usuario).filter(Usuario.email == data.email).first()

    if not usuario:
        # No revelar si el usuario existe o no
        return {"detail": "Si el dato es correcto, recibirás un código en tu correo"}

    if not usuario.email:
        raise HTTPException(status_code=400, detail="El usuario no tiene email registrado para recuperación")

    # Generar código de 6 dígitos
    codigo = ''.join(random.choices(string.digits, k=6))

    # Guardar código con expiración (15 minutos)
    tz = timezone(timedelta(hours=TIMEZONE_OFFSET))
    _codigos_reset[usuario.id] = {
        "codigo": codigo,
        "expira": datetime.now(tz) + timedelta(minutes=15),
    }

    # Enviar email
    from app.email_service import send_reset_code
    try:
        send_reset_code(usuario.email, usuario.nombre, codigo)
    except Exception:
        raise HTTPException(status_code=500, detail="Error al enviar el correo")

    return {"detail": "Si el dato es correcto, recibirás un código en tu correo"}


@router.post("/verificar-codigo-reset", status_code=200)
def verificar_codigo_reset(data: VerificarCodigoRequest, db: Session = Depends(get_db)):
    """
    Verificar código y cambiar contraseña.
    """
    if not data.celular and not data.email:
        raise HTTPException(status_code=400, detail="Debes proporcionar celular o email")

    # Buscar usuario
    if data.celular:
        usuario = db.query(Usuario).filter(Usuario.celular == data.celular).first()
    else:
        usuario = db.query(Usuario).filter(Usuario.email == data.email).first()

    if not usuario:
        raise HTTPException(status_code=400, detail="Código inválido o expirado")

    # Verificar código
    reset_data = _codigos_reset.get(usuario.id)
    if not reset_data:
        raise HTTPException(status_code=400, detail="Código inválido o expirado")

    tz = timezone(timedelta(hours=TIMEZONE_OFFSET))
    if reset_data["codigo"] != data.codigo:
        raise HTTPException(status_code=400, detail="Código inválido o expirado")

    if datetime.now(tz) > reset_data["expira"]:
        del _codigos_reset[usuario.id]
        raise HTTPException(status_code=400, detail="Código inválido o expirado")

    # Cambiar contraseña
    usuario.password_hash = pwd_context.hash(data.new_password)
    usuario.requiere_cambio_password = False
    db.commit()

    # Limpiar código usado
    del _codigos_reset[usuario.id]

    return {"detail": "Contraseña actualizada exitosamente"}
