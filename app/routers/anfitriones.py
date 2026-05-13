from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Anfitrion
from app.schemas import AnfitrionCreate, AnfitrionResponse
from app.auth import require_role
from app.config import ROL_ANFITRION

router = APIRouter(prefix="/anfitriones", tags=["Anfitriones"])


@router.post("", response_model=AnfitrionResponse, status_code=201)
def create_anfitrion(anfitrion: AnfitrionCreate, db: Session = Depends(get_db), usuario=Depends(require_role(ROL_ANFITRION))):
    """Crear un nuevo anfitrión."""
    db_anfitrion = Anfitrion(**anfitrion.model_dump())
    db.add(db_anfitrion)
    db.commit()
    db.refresh(db_anfitrion)
    return db_anfitrion


@router.get("", response_model=list[AnfitrionResponse])
def list_anfitriones(db: Session = Depends(get_db), usuario=Depends(require_role(ROL_ANFITRION))):
    """Listar todos los anfitriones."""
    return db.query(Anfitrion).all()


@router.get("/{anfitrion_id}", response_model=AnfitrionResponse)
def get_anfitrion(anfitrion_id: int, db: Session = Depends(get_db), usuario=Depends(require_role(ROL_ANFITRION))):
    """Obtener un anfitrión por ID."""
    anfitrion = db.query(Anfitrion).filter(Anfitrion.id == anfitrion_id).first()
    if not anfitrion:
        raise HTTPException(status_code=404, detail="Anfitrión no encontrado")
    return anfitrion
