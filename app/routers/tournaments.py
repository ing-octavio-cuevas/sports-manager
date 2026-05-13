from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Torneo, TorneoUbicacion, Partido
from app.auth import require_role
from app.config import ROL_ANFITRION, ROL_JUGADOR
from app.schemas import (
    TorneoCreate,
    TorneoUpdate,
    TorneoResponse,
    TorneoUbicacionCreate,
    TorneoUbicacionUpdate,
    TorneoUbicacionResponse,
)

router = APIRouter(prefix="/torneos", tags=["Torneos"])


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
    """Listar todos los torneos."""
    return db.query(Torneo).all()


@router.get("/{torneo_id}", response_model=TorneoResponse)
def get_torneo(torneo_id: int, db: Session = Depends(get_db), usuario=Depends(require_role(ROL_ANFITRION))):
    """Obtener un torneo por ID."""
    torneo = db.query(Torneo).filter(Torneo.id == torneo_id).first()
    if not torneo:
        raise HTTPException(status_code=404, detail="Torneo no encontrado")
    return torneo


@router.put("/{torneo_id}", response_model=TorneoResponse)
def update_torneo(torneo_id: int, torneo_data: TorneoUpdate, db: Session = Depends(get_db), usuario=Depends(require_role(ROL_ANFITRION))):
    """Actualizar un torneo."""
    torneo = db.query(Torneo).filter(Torneo.id == torneo_id).first()
    if not torneo:
        raise HTTPException(status_code=404, detail="Torneo no encontrado")
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
    db_ubicacion = TorneoUbicacion(torneo_id=torneo_id, **ubicacion.model_dump())
    db.add(db_ubicacion)
    db.commit()
    db.refresh(db_ubicacion)
    return db_ubicacion


@router.get("/{torneo_id}/ubicaciones", response_model=list[TorneoUbicacionResponse])
def list_ubicaciones(torneo_id: int, db: Session = Depends(get_db), usuario=Depends(require_role(ROL_ANFITRION))):
    """Listar ubicaciones de un torneo."""
    return db.query(TorneoUbicacion).filter(TorneoUbicacion.torneo_id == torneo_id).all()


@router.put("/{torneo_id}/ubicaciones/{ubicacion_id}", response_model=TorneoUbicacionResponse)
def update_ubicacion(torneo_id: int, ubicacion_id: int, ubicacion_data: TorneoUbicacionUpdate, db: Session = Depends(get_db), usuario=Depends(require_role(ROL_ANFITRION))):
    """Actualizar una ubicación de un torneo."""
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
