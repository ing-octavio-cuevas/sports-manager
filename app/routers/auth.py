from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from passlib.context import CryptContext

from app.database import get_db
from app.models import Usuario
from app.schemas import LoginRequest, TokenResponse, UsuarioResponse
from app.auth import create_access_token, get_current_user
from pydantic import BaseModel

router = APIRouter(prefix="/auth", tags=["Auth"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    """Iniciar sesión. Devuelve JWT token."""
    usuario = db.query(Usuario).filter(Usuario.email == data.email).first()
    if not usuario or not pwd_context.verify(data.password, usuario.password_hash):
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")
    if not usuario.estatus:
        raise HTTPException(status_code=401, detail="Usuario inactivo")

    token = create_access_token(data={"sub": str(usuario.id)})

    return TokenResponse(
        access_token=token,
        usuario=UsuarioResponse(
            id=usuario.id,
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
