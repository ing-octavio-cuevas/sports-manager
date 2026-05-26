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
def list_equipos(torneo_id: int = None, anfitrion_id: int = None, db: Session = Depends(get_db), usuario=Depends(require_role(ROL_ANFITRION, ROL_JUGADOR))):
    """Listar equipos. Filtrar por torneo_id y/o anfitrion_id."""
    query = db.query(Equipo)
    if anfitrion_id:
        torneos_ids = [t.id for t in db.query(Torneo).filter(Torneo.anfitrion_id == anfitrion_id).all()]
        query = query.filter(Equipo.torneo_id.in_(torneos_ids))
    elif ROL_ANFITRION in usuario.roles and ROL_JUGADOR not in usuario.roles and usuario.anfitrion_id:
        torneos_ids = [t.id for t in db.query(Torneo).filter(Torneo.anfitrion_id == usuario.anfitrion_id).all()]
        query = query.filter(Equipo.torneo_id.in_(torneos_ids))
    if torneo_id:
        query = query.filter(Equipo.torneo_id == torneo_id)
    return query.all()


@router.get("/{equipo_id}", response_model=EquipoResponse)
def get_equipo(equipo_id: int, db: Session = Depends(get_db), usuario=Depends(require_role(ROL_ANFITRION, ROL_JUGADOR))):
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


# ─── Upload de logo del equipo ───────────────────────────────

from fastapi import UploadFile, File
import boto3
import uuid
import os
from app.config import S3_BUCKET, S3_REGION, S3_URL_BASE

ALLOWED_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB


@router.post("/{equipo_id}/logo", response_model=EquipoResponse)
def upload_logo_equipo(equipo_id: int, logo: UploadFile = File(...), db: Session = Depends(get_db), usuario=Depends(require_role(ROL_ANFITRION, ROL_JUGADOR))):
    """Subir logo/foto del equipo a S3. El capitán o anfitrión pueden subir."""
    from app.models import Jugador

    equipo = db.query(Equipo).filter(Equipo.id == equipo_id).first()
    if not equipo:
        raise HTTPException(status_code=404, detail="Equipo no encontrado")

    # Si es jugador, verificar que sea capitán de este equipo
    if ROL_JUGADOR in usuario.roles and ROL_ANFITRION not in usuario.roles:
        capitan = db.query(Jugador).filter(
            Jugador.usuario_id == usuario.id,
            Jugador.equipo_id == equipo_id,
            Jugador.es_capitan == True,
        ).first()
        if not capitan:
            raise HTTPException(status_code=403, detail="Solo el capitán puede subir la foto del equipo")

    ext = os.path.splitext(logo.filename)[1].lower()
    if ext not in ALLOWED_IMAGE_EXT:
        raise HTTPException(status_code=400, detail=f"Formato no permitido. Usa: {', '.join(ALLOWED_IMAGE_EXT)}")

    content = logo.file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="El archivo excede el límite de 5 MB")

    s3 = boto3.client("s3", region_name=S3_REGION)

    # Eliminar logo anterior si existe
    if equipo.logo and S3_URL_BASE and S3_URL_BASE in equipo.logo:
        old_key = equipo.logo.replace(f"{S3_URL_BASE}/", "")
        try:
            s3.delete_object(Bucket=S3_BUCKET, Key=old_key)
        except Exception:
            pass

    torneo = db.query(Torneo).filter(Torneo.id == equipo.torneo_id).first()
    filename = f"equipo_{equipo_id}_{uuid.uuid4().hex[:8]}{ext}"
    s3_key = f"anfitrion_{torneo.anfitrion_id}/torneo_{torneo.id}/equipo_{equipo_id}/{filename}"

    s3.put_object(Bucket=S3_BUCKET, Key=s3_key, Body=content, ContentType=logo.content_type)

    equipo.logo = f"{S3_URL_BASE}/{s3_key}"
    db.commit()
    db.refresh(equipo)
    return equipo
