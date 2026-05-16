from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Torneo, TorneoUbicacion, Partido
from app.auth import require_role
from app.config import ROL_ANFITRION, ROL_JUGADOR, ROL_JUGADOR
from app.schemas import (
    TorneoCreate,
    TorneoUpdate,
    TorneoResponse,
    TorneoUbicacionCreate,
    TorneoUbicacionUpdate,
    TorneoUbicacionResponse,
)

router = APIRouter(prefix="/torneos", tags=["Torneos"])


def _verificar_acceso_torneo(torneo, usuario):
    """Verifica que el anfitrión tenga acceso al torneo. No bloquea jugadores."""
    if ROL_ANFITRION in usuario.roles and ROL_JUGADOR not in usuario.roles:
        if torneo.anfitrion_id != usuario.anfitrion_id:
            raise HTTPException(status_code=403, detail="No tienes acceso a este torneo")


@router.post("", response_model=TorneoResponse, status_code=201)
def create_torneo(torneo: TorneoCreate, db: Session = Depends(get_db), usuario=Depends(require_role(ROL_ANFITRION))):
    """Crear un nuevo torneo."""
    db_torneo = Torneo(**torneo.model_dump())
    db.add(db_torneo)
    db.commit()
    db.refresh(db_torneo)
    return db_torneo


@router.get("", response_model=list[TorneoResponse])
def list_torneos(db: Session = Depends(get_db), usuario=Depends(require_role(ROL_ANFITRION, ROL_JUGADOR))):
    """Listar torneos. Anfitrión ve solo los suyos."""
    if ROL_ANFITRION in usuario.roles and usuario.anfitrion_id:
        return db.query(Torneo).filter(Torneo.anfitrion_id == usuario.anfitrion_id).all()
    return db.query(Torneo).all()


@router.get("/{torneo_id}", response_model=TorneoResponse)
def get_torneo(torneo_id: int, db: Session = Depends(get_db), usuario=Depends(require_role(ROL_ANFITRION, ROL_JUGADOR))):
    """Obtener un torneo por ID."""
    torneo = db.query(Torneo).filter(Torneo.id == torneo_id).first()
    if not torneo:
        raise HTTPException(status_code=404, detail="Torneo no encontrado")
    # Solo restringir si es anfitrión puro (sin rol jugador)
    if ROL_ANFITRION in usuario.roles and ROL_JUGADOR not in usuario.roles:
        if torneo.anfitrion_id != usuario.anfitrion_id:
            raise HTTPException(status_code=403, detail="No tienes acceso a este torneo")
    return torneo


@router.put("/{torneo_id}", response_model=TorneoResponse)
def update_torneo(torneo_id: int, torneo_data: TorneoUpdate, db: Session = Depends(get_db), usuario=Depends(require_role(ROL_ANFITRION))):
    """Actualizar un torneo."""
    torneo = db.query(Torneo).filter(Torneo.id == torneo_id).first()
    if not torneo:
        raise HTTPException(status_code=404, detail="Torneo no encontrado")
    _verificar_acceso_torneo(torneo, usuario)
    for field, value in torneo_data.model_dump(exclude_unset=True).items():
        setattr(torneo, field, value)
    db.commit()
    db.refresh(torneo)
    return torneo


@router.post("/{torneo_id}/ubicaciones", response_model=TorneoUbicacionResponse, status_code=201)
def create_ubicacion(torneo_id: int, ubicacion: TorneoUbicacionCreate, db: Session = Depends(get_db), usuario=Depends(require_role(ROL_ANFITRION))):
    """Agregar una ubicación a un torneo."""
    torneo = db.query(Torneo).filter(Torneo.id == torneo_id).first()
    if not torneo:
        raise HTTPException(status_code=404, detail="Torneo no encontrado")
    _verificar_acceso_torneo(torneo, usuario)
    db_ubicacion = TorneoUbicacion(torneo_id=torneo_id, **ubicacion.model_dump())
    db.add(db_ubicacion)
    db.commit()
    db.refresh(db_ubicacion)
    return db_ubicacion


@router.get("/{torneo_id}/ubicaciones", response_model=list[TorneoUbicacionResponse])
def list_ubicaciones(torneo_id: int, db: Session = Depends(get_db), usuario=Depends(require_role(ROL_ANFITRION, ROL_JUGADOR))):
    """Listar ubicaciones de un torneo."""
    torneo = db.query(Torneo).filter(Torneo.id == torneo_id).first()
    if not torneo:
        raise HTTPException(status_code=404, detail="Torneo no encontrado")
    return db.query(TorneoUbicacion).filter(TorneoUbicacion.torneo_id == torneo_id).all()


@router.put("/{torneo_id}/ubicaciones/{ubicacion_id}", response_model=TorneoUbicacionResponse)
def update_ubicacion(torneo_id: int, ubicacion_id: int, ubicacion_data: TorneoUbicacionUpdate, db: Session = Depends(get_db), usuario=Depends(require_role(ROL_ANFITRION))):
    """Actualizar una ubicación de un torneo."""
    torneo = db.query(Torneo).filter(Torneo.id == torneo_id).first()
    if not torneo:
        raise HTTPException(status_code=404, detail="Torneo no encontrado")
    _verificar_acceso_torneo(torneo, usuario)
    ubicacion = db.query(TorneoUbicacion).filter(
        TorneoUbicacion.id == ubicacion_id,
        TorneoUbicacion.torneo_id == torneo_id,
    ).first()
    if not ubicacion:
        raise HTTPException(status_code=404, detail="Ubicación no encontrada")
    for field, value in ubicacion_data.model_dump(exclude_unset=True).items():
        setattr(ubicacion, field, value)
    db.commit()
    db.refresh(ubicacion)
    return ubicacion


@router.delete("/{torneo_id}/ubicaciones/{ubicacion_id}", status_code=204)
def delete_ubicacion(torneo_id: int, ubicacion_id: int, db: Session = Depends(get_db), usuario=Depends(require_role(ROL_ANFITRION))):
    """Eliminar una ubicación de un torneo."""
    torneo = db.query(Torneo).filter(Torneo.id == torneo_id).first()
    if not torneo:
        raise HTTPException(status_code=404, detail="Torneo no encontrado")
    _verificar_acceso_torneo(torneo, usuario)
    ubicacion = db.query(TorneoUbicacion).filter(
        TorneoUbicacion.id == ubicacion_id,
        TorneoUbicacion.torneo_id == torneo_id,
    ).first()
    if not ubicacion:
        raise HTTPException(status_code=404, detail="Ubicación no encontrada")
    tiene_partidos = db.query(Partido).filter(Partido.ubicacion_id == ubicacion_id).first()
    if tiene_partidos:
        raise HTTPException(status_code=400, detail="No se puede eliminar, la ubicación tiene partidos asignados")
    db.delete(ubicacion)
    db.commit()


@router.delete("/{torneo_id}", status_code=204)
def delete_torneo(torneo_id: int, db: Session = Depends(get_db), usuario=Depends(require_role(ROL_ANFITRION))):
    """Eliminar un torneo. Solo si no tiene equipos, jornadas ni partidos."""
    from app.models import Equipo, Jornada

    torneo = db.query(Torneo).filter(Torneo.id == torneo_id).first()
    if not torneo:
        raise HTTPException(status_code=404, detail="Torneo no encontrado")
    _verificar_acceso_torneo(torneo, usuario)

    tiene_equipos = db.query(Equipo).filter(Equipo.torneo_id == torneo_id).first()
    if tiene_equipos:
        raise HTTPException(status_code=400, detail="No se puede eliminar, el torneo tiene equipos")

    tiene_jornadas = db.query(Jornada).filter(Jornada.torneo_id == torneo_id).first()
    if tiene_jornadas:
        raise HTTPException(status_code=400, detail="No se puede eliminar, el torneo tiene jornadas")

    tiene_partidos = db.query(Partido).filter(Partido.torneo_id == torneo_id).first()
    if tiene_partidos:
        raise HTTPException(status_code=400, detail="No se puede eliminar, el torneo tiene partidos")

    # Eliminar ubicaciones del torneo primero
    db.query(TorneoUbicacion).filter(TorneoUbicacion.torneo_id == torneo_id).delete()
    db.delete(torneo)
    db.commit()
