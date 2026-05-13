from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from passlib.context import CryptContext

from app.database import get_db
from app.models import Usuario, Jugador
from app.schemas import UsuarioCreate, UsuarioResponse
from app.auth import require_role
from app.config import ROL_ANFITRION

router = APIRouter(prefix="/usuarios", tags=["Usuarios"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


@router.post("", response_model=UsuarioResponse, status_code=201)
def create_usuario(usuario: UsuarioCreate, db: Session = Depends(get_db), usuario_auth=Depends(require_role(ROL_ANFITRION))):
    """Crear un nuevo usuario. Si ya existe y se envía rol jugador, se vincula el jugador."""
    # Validar roles
    roles_validos = {"anfitrion", "arbitro", "jugador"}
    for rol in usuario.roles:
        if rol not in roles_validos:
            raise HTTPException(status_code=400, detail=f"Rol '{rol}' inválido. Usa: {', '.join(roles_validos)}")

    # Validar campos requeridos según rol
    if "anfitrion" in usuario.roles and not usuario.anfitrion_id:
        raise HTTPException(status_code=400, detail="El rol anfitrion requiere anfitrion_id")
    if "jugador" in usuario.roles and not usuario.jugador_id:
        raise HTTPException(status_code=400, detail="El rol jugador requiere jugador_id")

    # Verificar si el email ya existe
    existe = db.query(Usuario).filter(Usuario.email == usuario.email).first()
    if existe:
        # Si viene con rol jugador, agregar el rol y vincular el jugador
        if "jugador" in usuario.roles:
            roles_actuales = set(existe.roles)
            roles_actuales.add("jugador")
            existe.rol = ",".join(roles_actuales)
            # Vincular jugador al usuario
            if usuario.jugador_id:
                jugador = db.query(Jugador).filter(Jugador.id == usuario.jugador_id).first()
                if not jugador:
                    raise HTTPException(status_code=404, detail="Jugador no encontrado")
                jugador.usuario_id = existe.id
            db.commit()
            db.refresh(existe)
            return existe
        raise HTTPException(status_code=400, detail="El email ya está registrado")

    # Crear usuario
    db_usuario = Usuario(
        email=usuario.email,
        password_hash=pwd_context.hash(usuario.password),
        nombre=usuario.nombre,
        rol=",".join(usuario.roles),
        anfitrion_id=usuario.anfitrion_id,
    )
    db.add(db_usuario)
    db.flush()

    # Si es jugador, vincular el jugador al usuario
    if "jugador" in usuario.roles and usuario.jugador_id:
        jugador = db.query(Jugador).filter(Jugador.id == usuario.jugador_id).first()
        if not jugador:
            raise HTTPException(status_code=404, detail="Jugador no encontrado")
        jugador.usuario_id = db_usuario.id

    db.commit()
    db.refresh(db_usuario)
    return db_usuario
