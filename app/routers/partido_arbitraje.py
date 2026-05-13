from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import PartidoArbitraje, Partido
from app.schemas import (
    PartidoArbitrajeCreate,
    PartidoArbitrajeUpdate,
    PartidoArbitrajeResponse,
)
from app.auth import require_role
from app.config import ROL_ANFITRION, ROL_JUGADOR, ROL_JUGADOR

router = APIRouter(prefix="/partido-arbitraje", tags=["Partido Arbitraje"])



@router.get("", response_model=list[PartidoArbitrajeResponse])
def list_arbitrajes(partido_id: int = None, db: Session = Depends(get_db), usuario=Depends(require_role(ROL_ANFITRION, ROL_JUGADOR))):
    """Listar arbitrajes. Filtrar por partido_id opcionalmente."""
    query = db.query(PartidoArbitraje)
    if partido_id:
        query = query.filter(PartidoArbitraje.partido_id == partido_id)
    return query.all()


@router.get("/{arbitraje_id}", response_model=PartidoArbitrajeResponse)
def get_arbitraje(arbitraje_id: int, db: Session = Depends(get_db), usuario=Depends(require_role(ROL_ANFITRION))):
    """Obtener un registro de arbitraje por ID."""
    arbitraje = db.query(PartidoArbitraje).filter(
        PartidoArbitraje.id == arbitraje_id
    ).first()
    if not arbitraje:
        raise HTTPException(status_code=404, detail="Arbitraje no encontrado")
    return arbitraje


@router.put("/{arbitraje_id}", response_model=PartidoArbitrajeResponse)
def update_arbitraje(arbitraje_id: int, data: PartidoArbitrajeUpdate, db: Session = Depends(get_db), usuario=Depends(require_role(ROL_ANFITRION))):
    """Actualizar un registro de arbitraje."""
    arbitraje = db.query(PartidoArbitraje).filter(
        PartidoArbitraje.id == arbitraje_id
    ).first()
    if not arbitraje:
        raise HTTPException(status_code=404, detail="Arbitraje no encontrado")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(arbitraje, field, value)
    db.commit()
    db.refresh(arbitraje)
    return arbitraje

