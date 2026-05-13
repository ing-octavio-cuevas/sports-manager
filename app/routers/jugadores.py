from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
import os
import uuid

from app.database import get_db
from app.models import Jugador, Equipo, Torneo, Partido, Usuario
from app.schemas import JugadorCreate, JugadorUpdate, JugadorResponse
from app.auth import require_role, get_current_user
from app.config import ROL_ANFITRION, ROL_JUGADOR

router = APIRouter(prefix="/jugadores", tags=["Jugadores"])

UPLOAD_DIR = "uploads"
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_FILE_SIZE = 2 * 1024 * 1024  # 2 MB


@router.post("", response_model=JugadorResponse, status_code=201)
def create_jugador(jugador: JugadorCreate, db: Session = Depends(get_db), usuario=Depends(require_role(ROL_ANFITRION, ROL_JUGADOR))):
    """Crear un nuevo jugador."""
    equipo = db.query(Equipo).filter(Equipo.id == jugador.equipo_id).first()
    if not equipo:
        raise HTTPException(status_code=404, detail="Equipo no encontrado")

    # Si es jugador, solo puede crear en su propio equipo
    if ROL_JUGADOR in usuario.roles and ROL_ANFITRION not in usuario.roles:
        mis_jugadores = db.query(Jugador).filter(Jugador.usuario_id == usuario.id).all()
        mis_equipos = [j.equipo_id for j in mis_jugadores]
        if jugador.equipo_id not in mis_equipos:
            raise HTTPException(status_code=403, detail="Solo puedes agregar jugadores a tu propio equipo")

    db_jugador = Jugador(**jugador.model_dump())
    db_jugador.codigo_qr = f"JUG-{uuid.uuid4().hex[:16].upper()}"
    db.add(db_jugador)
    db.commit()
    db.refresh(db_jugador)
    return db_jugador


@router.get("", response_model=list[JugadorResponse])
def list_jugadores(equipo_id: int = None, db: Session = Depends(get_db), usuario=Depends(require_role(ROL_ANFITRION))):
    """Listar jugadores. Filtrar por equipo_id opcionalmente."""
    query = db.query(Jugador)
    if equipo_id:
        query = query.filter(Jugador.equipo_id == equipo_id)
    return query.all()


@router.get("/mi-informacion")
def get_mi_informacion(db: Session = Depends(get_db), usuario=Depends(require_role(ROL_JUGADOR))):
    """
    Información del jugador logueado.
    Torneos a los que está inscrito, con sus partidos.
    """
    from app.schemas import JugadorInfoCompleta, TorneoInfoJugador
    from sqlalchemy import or_

    jugadores = db.query(Jugador).filter(Jugador.usuario_id == usuario.id).all()
    if not jugadores:
        raise HTTPException(status_code=404, detail="No tienes jugadores vinculados")

    torneos = []
    for jugador in jugadores:
        equipo = db.query(Equipo).filter(Equipo.id == jugador.equipo_id).first()
        torneo = db.query(Torneo).filter(Torneo.id == equipo.torneo_id).first()

        partidos = db.query(Partido).filter(
            or_(
                Partido.equipo_local_id == equipo.id,
                Partido.equipo_visitante_id == equipo.id,
            )
        ).all()

        torneos.append(TorneoInfoJugador(
            torneo_id=torneo.id,
            torneo_nombre=torneo.nombre,
            equipo_id=equipo.id,
            equipo_nombre=equipo.nombre,
            jugador_id=jugador.id,
            es_capitan=jugador.es_capitan,
            partidos=partidos,
        ))

    return JugadorInfoCompleta(
        usuario_id=usuario.id,
        nombre=usuario.nombre,
        email=usuario.email,
        torneos=torneos,
    )


@router.get("/{jugador_id}", response_model=JugadorResponse)
def get_jugador(jugador_id: int, db: Session = Depends(get_db), usuario=Depends(require_role(ROL_ANFITRION))):
    """Obtener un jugador por ID."""
    jugador = db.query(Jugador).filter(Jugador.id == jugador_id).first()
    if not jugador:
        raise HTTPException(status_code=404, detail="Jugador no encontrado")
    return jugador


@router.put("/{jugador_id}", response_model=JugadorResponse)
def update_jugador(jugador_id: int, jugador_data: JugadorUpdate, db: Session = Depends(get_db), usuario=Depends(require_role(ROL_ANFITRION, ROL_JUGADOR))):
    """Actualizar un jugador. Solo se actualizan los campos enviados."""
    jugador = db.query(Jugador).filter(Jugador.id == jugador_id).first()
    if not jugador:
        raise HTTPException(status_code=404, detail="Jugador no encontrado")

    # Si es jugador, solo puede editar jugadores de su propio equipo
    if ROL_JUGADOR in usuario.roles and ROL_ANFITRION not in usuario.roles:
        mis_jugadores = db.query(Jugador).filter(Jugador.usuario_id == usuario.id).all()
        mis_equipos = [j.equipo_id for j in mis_jugadores]
        if jugador.equipo_id not in mis_equipos:
            raise HTTPException(status_code=403, detail="Solo puedes editar jugadores de tu propio equipo")
    for field, value in jugador_data.model_dump(exclude_unset=True).items():
        setattr(jugador, field, value)
    db.commit()
    db.refresh(jugador)
    return jugador


@router.delete("/{jugador_id}", status_code=204)
def delete_jugador(jugador_id: int, db: Session = Depends(get_db), usuario=Depends(require_role(ROL_ANFITRION))):
    """Soft delete — desactiva el jugador (estatus = False)."""
    jugador = db.query(Jugador).filter(Jugador.id == jugador_id).first()
    if not jugador:
        raise HTTPException(status_code=404, detail="Jugador no encontrado")
    jugador.estatus = False
    db.commit()


# ─── Upload de foto ──────────────────────────────────────────

import boto3
from app.config import S3_BUCKET, S3_REGION, S3_URL_BASE


@router.post("/{jugador_id}/foto", response_model=JugadorResponse)
def upload_foto(jugador_id: int, foto: UploadFile = File(...), db: Session = Depends(get_db), usuario=Depends(require_role(ROL_ANFITRION))):
    """
    Subir foto de un jugador a S3.
    Se guarda en: anfitrion_{id}/torneo_{id}/equipo_{id}/jugador_{id}_{uuid}.ext
    """
    jugador = db.query(Jugador).filter(Jugador.id == jugador_id).first()
    if not jugador:
        raise HTTPException(status_code=404, detail="Jugador no encontrado")

    # Validar extensión
    ext = os.path.splitext(foto.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Formato no permitido. Usa: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # Validar tamaño
    content = foto.file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"La foto excede el límite de {MAX_FILE_SIZE // (1024 * 1024)} MB"
        )

    # Obtener equipo y torneo para la ruta en S3
    equipo = db.query(Equipo).filter(Equipo.id == jugador.equipo_id).first()
    torneo = db.query(Torneo).filter(Torneo.id == equipo.torneo_id).first()

    # Key en S3
    filename = f"jugador_{jugador_id}_{uuid.uuid4().hex[:8]}{ext}"
    s3_key = f"anfitrion_{torneo.anfitrion_id}/torneo_{torneo.id}/equipo_{equipo.id}/{filename}"

    # Subir a S3
    s3 = boto3.client("s3", region_name=S3_REGION)
    s3.put_object(
        Bucket=S3_BUCKET,
        Key=s3_key,
        Body=content,
        ContentType=foto.content_type,
    )

    # Guardar URL pública en BD
    jugador.foto = f"{S3_URL_BASE}/{s3_key}"
    db.commit()
    db.refresh(jugador)
    return jugador
