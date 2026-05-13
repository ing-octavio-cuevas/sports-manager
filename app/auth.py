"""
Módulo de autenticación JWT.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Usuario

# Configuración JWT
from app.config import SECRET_KEY
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480  # 8 horas

security = HTTPBearer()


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Generar un JWT token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> Usuario:
    """Dependency: extrae el usuario del token JWT."""
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM], options={"verify_exp": True})
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Token inválido")
        user_id = int(user_id)
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Token inválido o expirado: {str(e)}")

    usuario = db.query(Usuario).filter(Usuario.id == user_id).first()
    if not usuario or not usuario.estatus:
        raise HTTPException(status_code=401, detail="Usuario no encontrado o inactivo")
    return usuario


def require_role(*roles_requeridos):
    """
    Dependency factory: verifica que el usuario tenga al menos uno de los roles requeridos.
    Uso: Depends(require_role("admin", "arbitro"))
    """
    def role_checker(usuario: Usuario = Depends(get_current_user)):
        user_roles = set(usuario.roles)
        if not user_roles.intersection(roles_requeridos):
            raise HTTPException(
                status_code=403,
                detail=f"Acceso denegado. Se requiere rol: {', '.join(roles_requeridos)}"
            )
        return usuario
    return role_checker
