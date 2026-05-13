from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Equipo, Torneo
from app.schemas import EquipoCreate, EquipoUpdate, EquipoResponse
from app.auth import require_role
from app.config import ROL_ANFITRION, ROL_JUGADOR

router = APIRouter(prefix="/equipos", tags=["Equipos"])


@router.post("", response_model=EquipoResponse, status_code=201)
def create_equipo(equipo: EquipoCreate, db: Session = Depends(get_db), usuario=Depends(require_role(ROL_ANFITRION))):
    """Crear un nuevo equipo."""
    torneo = db.query(Torneo).filter(Torneo.id == equipo.torneo_id).first()
    if not torneo:
        raise HTTPException(status_code=404, detail="Torneo no encontrado")
    db_equipo = Equipo(**equipo.model_dump())
    db.add(db_equipo)
    db.commit()
    db.refresh(db_equipo)
    return db_equipo


@router.get("", response_model=list[EquipoResponse])
def list_equipos(torneo_id: int = None, db: Session = Depends(get_db), usuario=Depends(require_role(ROL_ANFITRION, ROL_JUGADOR))):
    """Listar equipos."""
    query = db.query(Equipo)
    if torneo_id:
        query = query.filter(Equipo.torneo_id == torneo_id)
    return query.all()


@router.get("/{equipo_id}", response_model=EquipoResponse)
def get_equipo(equipo_id: int, db: Session = Depends(get_db), usuario=Depends(require_role(ROL_ANFITRION))):
    """Obtener un equipo por ID."""
    equipo = db.query(Equipo).filter(Equipo.id == equipo_id).first()
    if not equipo:
        raise HTTPException(status_code=404, detail="Equipo no encontrado")
    return equipo


@router.put("/{equipo_id}", response_model=EquipoResponse)
def update_equipo(equipo_id: int, equipo_data: EquipoUpdate, db: Session = Depends(get_db), usuario=Depends(require_role(ROL_ANFITRION))):
    """Actualizar un equipo."""
    equipo = db.query(Equipo).filter(Equipo.id == equipo_id).first()
    if not equipo:
        raise HTTPException(status_code=404, detail="Equipo no encontrado")
    for field, value in equipo_data.model_dump(exclude_unset=True).items():
        setattr(equipo, field, value)
    db.commit()
    db.refresh(equipo)
    return equipo


@router.delete("/{equipo_id}", status_code=204)
def delete_equipo(equipo_id: int, db: Session = Depends(get_db), usuario=Depends(require_role(ROL_ANFITRION))):
    """Soft delete — desactiva el equipo."""
    equipo = db.query(Equipo).filter(Equipo.id == equipo_id).first()
    if not equipo:
        raise HTTPException(status_code=404, detail="Equipo no encontrado")
    equipo.estatus = False
    db.commit()
