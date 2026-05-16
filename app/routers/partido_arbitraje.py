from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import PartidoArbitraje, Partido, Torneo
from app.schemas import (
    PartidoArbitrajeCreate,
    PartidoArbitrajeUpdate,
    PartidoArbitrajeResponse,
)
from app.auth import require_role
from app.config import ROL_ANFITRION, ROL_JUGADOR

router = APIRouter(prefix="/partido-arbitraje", tags=["Partido Arbitraje"])



@router.get("", response_model=list[PartidoArbitrajeResponse])
def list_arbitrajes(partido_id: int = None, db: Session = Depends(get_db), usuario=Depends(require_role(ROL_ANFITRION, ROL_JUGADOR))):
    """Listar arbitrajes. Filtrar por partido_id opcionalmente."""
    query = db.query(PartidoArbitraje)
    # Filtro anfitrión
    if ROL_ANFITRION in usuario.roles and usuario.anfitrion_id:
        torneos_ids = [t.id for t in db.query(Torneo).filter(Torneo.anfitrion_id == usuario.anfitrion_id).all()]
        partidos_ids = [p.id for p in db.query(Partido).filter(Partido.torneo_id.in_(torneos_ids)).all()]
        query = query.filter(PartidoArbitraje.partido_id.in_(partidos_ids))
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
    # Filtro anfitrión
    if ROL_ANFITRION in usuario.roles and usuario.anfitrion_id:
        partido = db.query(Partido).filter(Partido.id == arbitraje.partido_id).first()
        if partido:
            torneo = db.query(Torneo).filter(Torneo.id == partido.torneo_id).first()
            if not torneo or torneo.anfitrion_id != usuario.anfitrion_id:
                raise HTTPException(status_code=403, detail="No tienes acceso a este recurso")
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

