from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Jornada, Torneo, Partido
from app.schemas import JornadaCreate, JornadaUpdate, JornadaResponse
from app.auth import require_role
from app.config import ROL_ANFITRION

router = APIRouter(prefix="/jornadas", tags=["Jornadas"])


@router.post("", response_model=JornadaResponse, status_code=201)
def create_jornada(jornada: JornadaCreate, db: Session = Depends(get_db), usuario=Depends(require_role(ROL_ANFITRION))):
    """Crear una nueva jornada."""
    torneo = db.query(Torneo).filter(Torneo.id == jornada.torneo_id).first()
    if not torneo:
        raise HTTPException(status_code=404, detail="Torneo no encontrado")
    # Verificar que no exista la misma jornada (torneo + numero)
    existe = db.query(Jornada).filter(
        Jornada.torneo_id == jornada.torneo_id,
        Jornada.numero == jornada.numero,
    ).first()
    if existe:
        raise HTTPException(status_code=400, detail="Ya existe esa jornada para este torneo")
    db_jornada = Jornada(**jornada.model_dump())
    db.add(db_jornada)
    db.commit()
    db.refresh(db_jornada)
    return db_jornada


@router.get("", response_model=list[JornadaResponse])
def list_jornadas(torneo_id: int = None, db: Session = Depends(get_db), usuario=Depends(require_role(ROL_ANFITRION))):
    """Listar jornadas. Filtrar por torneo_id opcionalmente."""
    query = db.query(Jornada)
    if torneo_id:
        query = query.filter(Jornada.torneo_id == torneo_id)
    return query.order_by(Jornada.numero).all()


@router.get("/{jornada_id}", response_model=JornadaResponse)
def get_jornada(jornada_id: int, db: Session = Depends(get_db), usuario=Depends(require_role(ROL_ANFITRION))):
    """Obtener una jornada por ID."""
    jornada = db.query(Jornada).filter(Jornada.id == jornada_id).first()
    if not jornada:
        raise HTTPException(status_code=404, detail="Jornada no encontrada")
    return jornada


@router.put("/{jornada_id}", response_model=JornadaResponse)
def update_jornada(jornada_id: int, jornada_data: JornadaUpdate, db: Session = Depends(get_db), usuario=Depends(require_role(ROL_ANFITRION))):
    """Actualizar una jornada. Solo se actualizan los campos enviados."""
    jornada = db.query(Jornada).filter(Jornada.id == jornada_id).first()
    if not jornada:
        raise HTTPException(status_code=404, detail="Jornada no encontrada")
    for field, value in jornada_data.model_dump(exclude_unset=True).items():
        setattr(jornada, field, value)
    db.commit()
    db.refresh(jornada)
    return jornada



@router.delete("/{jornada_id}", status_code=204)
def delete_jornada(jornada_id: int, db: Session = Depends(get_db), usuario=Depends(require_role(ROL_ANFITRION))):
    """Eliminar jornada — solo si no tiene partidos asignados."""
    jornada = db.query(Jornada).filter(Jornada.id == jornada_id).first()
    if not jornada:
        raise HTTPException(status_code=404, detail="Jornada no encontrada")
    tiene_partidos = db.query(Partido).filter(Partido.jornada_id == jornada_id).first()
    if tiene_partidos:
        raise HTTPException(status_code=400, detail="No se puede eliminar, la jornada tiene partidos asignados")
    db.delete(jornada)
    db.commit()
