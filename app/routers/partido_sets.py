from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import PartidoSet, Partido
from app.schemas import PartidoSetCreate, PartidoSetUpdate, PartidoSetResponse
from app.auth import require_role
from app.config import ROL_ANFITRION, ROL_JUGADOR

router = APIRouter(prefix="/partidos/{partido_id}/sets", tags=["Partido Sets"])


@router.post("", response_model=PartidoSetResponse, status_code=201)
def create_set(partido_id: int, set_data: PartidoSetCreate, db: Session = Depends(get_db), usuario=Depends(require_role(ROL_ANFITRION))):
    """Crear un set para un partido."""
    partido = db.query(Partido).filter(Partido.id == partido_id).first()
    if not partido:
        raise HTTPException(status_code=404, detail="Partido no encontrado")
    db_set = PartidoSet(partido_id=partido_id, **set_data.model_dump())
    db.add(db_set)
    db.commit()
    db.refresh(db_set)
    return db_set


@router.get("", response_model=list[PartidoSetResponse])
def list_sets(partido_id: int, db: Session = Depends(get_db), usuario=Depends(require_role(ROL_ANFITRION, ROL_JUGADOR))):
    """Listar sets de un partido."""
    return db.query(PartidoSet).filter(
        PartidoSet.partido_id == partido_id
    ).order_by(PartidoSet.numero_set).all()


@router.put("/{set_id}", response_model=PartidoSetResponse)
def update_set(partido_id: int, set_id: int, set_data: PartidoSetUpdate, db: Session = Depends(get_db), usuario=Depends(require_role(ROL_ANFITRION))):
    """Actualizar un set."""
    db_set = db.query(PartidoSet).filter(
        PartidoSet.id == set_id,
        PartidoSet.partido_id == partido_id,
    ).first()
    if not db_set:
        raise HTTPException(status_code=404, detail="Set no encontrado")
    for field, value in set_data.model_dump(exclude_unset=True).items():
        setattr(db_set, field, value)
    db.commit()
    db.refresh(db_set)
    return db_set


@router.delete("/{set_id}", status_code=204)
def delete_set(partido_id: int, set_id: int, db: Session = Depends(get_db), usuario=Depends(require_role(ROL_ANFITRION))):
    """Eliminar un set."""
    db_set = db.query(PartidoSet).filter(
        PartidoSet.id == set_id,
        PartidoSet.partido_id == partido_id,
    ).first()
    if not db_set:
        raise HTTPException(status_code=404, detail="Set no encontrado")
    db.delete(db_set)
    db.commit()
