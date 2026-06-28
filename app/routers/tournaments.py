from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from slowapi import Limiter
from slowapi.util import get_remote_address

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
    TorneoResumenCompleto,
    TorneoResumenInfo,
    EquipoResumenCompleto,
    AsistenciaResumenPartido,
    PosicionEquipo,
    JugadorResponse,
)

router = APIRouter(prefix="/torneos", tags=["Torneos"])

limiter = Limiter(key_func=get_remote_address)


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
    update_data = torneo_data.model_dump(exclude_unset=True)
    # No sobreescribir logo/reglamento si vienen vacíos (se manejan por sus propios endpoints)
    if "logo" in update_data and not update_data["logo"]:
        del update_data["logo"]
    if "reglamento" in update_data and not update_data["reglamento"]:
        del update_data["reglamento"]
    for field, value in update_data.items():
        setattr(torneo, field, value)
    db.commit()
    db.refresh(torneo)
    return torneo


# ─── Upload de logo y reglamento ─────────────────────────────

from fastapi import UploadFile, File
import boto3
import uuid
import os
from app.config import S3_BUCKET, S3_REGION, S3_URL_BASE

ALLOWED_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_DOC_EXT = {".pdf"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB


@router.post("/{torneo_id}/logo", response_model=TorneoResponse)
def upload_logo(torneo_id: int, logo: UploadFile = File(...), db: Session = Depends(get_db), usuario=Depends(require_role(ROL_ANFITRION))):
    """Subir logo del torneo a S3. Elimina el logo anterior si existe."""
    torneo = db.query(Torneo).filter(Torneo.id == torneo_id).first()
    if not torneo:
        raise HTTPException(status_code=404, detail="Torneo no encontrado")
    _verificar_acceso_torneo(torneo, usuario)

    ext = os.path.splitext(logo.filename)[1].lower()
    if ext not in ALLOWED_IMAGE_EXT:
        raise HTTPException(status_code=400, detail=f"Formato no permitido. Usa: {', '.join(ALLOWED_IMAGE_EXT)}")

    content = logo.file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="El archivo excede el límite de 5 MB")

    s3 = boto3.client("s3", region_name=S3_REGION)

    # Eliminar logo anterior de S3 si existe
    if torneo.logo and S3_URL_BASE and S3_URL_BASE in torneo.logo:
        old_key = torneo.logo.replace(f"{S3_URL_BASE}/", "")
        try:
            s3.delete_object(Bucket=S3_BUCKET, Key=old_key)
        except Exception:
            pass

    filename = f"logo_{torneo_id}_{uuid.uuid4().hex[:8]}{ext}"
    s3_key = f"anfitrion_{torneo.anfitrion_id}/torneo_{torneo_id}/{filename}"

    s3.put_object(Bucket=S3_BUCKET, Key=s3_key, Body=content, ContentType=logo.content_type)

    torneo.logo = f"{S3_URL_BASE}/{s3_key}"
    db.commit()
    db.refresh(torneo)
    return torneo


@router.post("/{torneo_id}/reglamento", response_model=TorneoResponse)
def upload_reglamento(torneo_id: int, reglamento: UploadFile = File(...), db: Session = Depends(get_db), usuario=Depends(require_role(ROL_ANFITRION))):
    """Subir reglamento del torneo (PDF) a S3."""
    torneo = db.query(Torneo).filter(Torneo.id == torneo_id).first()
    if not torneo:
        raise HTTPException(status_code=404, detail="Torneo no encontrado")
    _verificar_acceso_torneo(torneo, usuario)

    ext = os.path.splitext(reglamento.filename)[1].lower()
    if ext not in ALLOWED_DOC_EXT:
        raise HTTPException(status_code=400, detail="Solo se permite formato PDF")

    content = reglamento.file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="El archivo excede el límite de 5 MB")

    filename = f"reglamento_{torneo_id}_{uuid.uuid4().hex[:8]}{ext}"
    s3_key = f"anfitrion_{torneo.anfitrion_id}/torneo_{torneo_id}/{filename}"

    s3 = boto3.client("s3", region_name=S3_REGION)
    s3.put_object(Bucket=S3_BUCKET, Key=s3_key, Body=content, ContentType="application/pdf")

    torneo.reglamento = f"{S3_URL_BASE}/{s3_key}"
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


@router.get("/{torneo_id}/resumen", response_model=TorneoResumenCompleto)
@limiter.limit("30/minute")
def get_torneo_resumen(request: Request, torneo_id: int, db: Session = Depends(get_db)):
    """Resumen completo de un torneo (público, con rate limit)."""
    from app.models import Equipo, Jugador, PartidoSet, Asistencia, Jornada
    from sqlalchemy.orm import joinedload
    from sqlalchemy import or_

    torneo = db.query(Torneo).filter(Torneo.id == torneo_id).first()
    if not torneo:
        raise HTTPException(status_code=404, detail="Torneo no encontrado")

    if not torneo.publicado:
        raise HTTPException(status_code=404, detail="Torneo no encontrado")

    # Info del torneo
    torneo_info = TorneoResumenInfo(
        id=torneo.id,
        nombre=torneo.nombre,
        periodo=torneo.periodo,
        categoria=torneo.categoria,
        logo=torneo.logo,
    )

    # Equipos del torneo (solo activos)
    equipos = db.query(Equipo).filter(Equipo.torneo_id == torneo_id, Equipo.estatus == True).all()

    # Partidos oficiales jugados
    partidos_jugados = db.query(Partido).filter(
        Partido.torneo_id == torneo_id,
        Partido.estatus == "Jugado",
        Partido.tipo == "Oficial",
    ).all()

    # ─── Tabla de posiciones ───────────────────────────────
    stats = {}
    for equipo in equipos:
        stats[equipo.id] = {
            "equipo_id": equipo.id,
            "equipo_nombre": equipo.nombre,
            "pj": 0, "pg": 0, "pp": 0, "sg": 0, "sp": 0, "pts": 0,
        }

    for partido in partidos_jugados:
        local_id = partido.equipo_local_id
        visitante_id = partido.equipo_visitante_id
        if local_id not in stats or visitante_id not in stats:
            continue
        stats[local_id]["pj"] += 1
        stats[visitante_id]["pj"] += 1
        stats[local_id]["pts"] += partido.puntos_local or 0
        stats[visitante_id]["pts"] += partido.puntos_visitante or 0

        # Sets (si existen)
        sets = db.query(PartidoSet).filter(PartidoSet.partido_id == partido.id).all()
        sets_local = sum(1 for s in sets if s.marcador_local > s.marcador_visitante)
        sets_visitante = sum(1 for s in sets if s.marcador_visitante > s.marcador_local)
        stats[local_id]["sg"] += sets_local
        stats[local_id]["sp"] += sets_visitante
        stats[visitante_id]["sg"] += sets_visitante
        stats[visitante_id]["sp"] += sets_local

        # Ganador/perdedor: por sets si hay, sino por puntos del partido
        if sets:
            if sets_local > sets_visitante:
                stats[local_id]["pg"] += 1
                stats[visitante_id]["pp"] += 1
            elif sets_visitante > sets_local:
                stats[visitante_id]["pg"] += 1
                stats[local_id]["pp"] += 1
        else:
            if (partido.puntos_local or 0) > (partido.puntos_visitante or 0):
                stats[local_id]["pg"] += 1
                stats[visitante_id]["pp"] += 1
            elif (partido.puntos_visitante or 0) > (partido.puntos_local or 0):
                stats[visitante_id]["pg"] += 1
                stats[local_id]["pp"] += 1

    tabla = sorted(stats.values(), key=lambda x: (-x["pts"], -x["sg"]))
    tabla_posiciones = [PosicionEquipo(**row) for row in tabla]

    # ─── Equipos con jugadores y asistencias ───────────────
    equipos_resumen = []
    for equipo in equipos:
        jugadores = db.query(Jugador).options(joinedload(Jugador.usuario)).filter(
            Jugador.equipo_id == equipo.id
        ).all()

        # Últimas 4 asistencias del equipo (oficiales y amistosos)
        partidos_equipo = db.query(Partido).filter(
            Partido.torneo_id == torneo_id,
            or_(
                Partido.equipo_local_id == equipo.id,
                Partido.equipo_visitante_id == equipo.id,
            ),
        ).order_by(Partido.fecha_hora.desc()).limit(4).all()

        ultimas_asistencias = []
        total_jugadores = len(jugadores)
        for p in partidos_equipo:
            rival_id = p.equipo_visitante_id if p.equipo_local_id == equipo.id else p.equipo_local_id
            rival = db.query(Equipo).filter(Equipo.id == rival_id).first()

            # Jornada
            jornada_p = db.query(Jornada).filter(Jornada.id == p.jornada_id).first()

            # Jugadores presentes (detalle)
            asistencias_partido = db.query(Asistencia).filter(
                Asistencia.partido_id == p.id,
                Asistencia.jugador_id.in_([j.id for j in jugadores]),
            ).all()

            from app.schemas import JugadorAsistenciaInfo
            jugadores_presentes = []
            for a in asistencias_partido:
                jug = next((j for j in jugadores if j.id == a.jugador_id), None)
                if jug:
                    from datetime import datetime as dt_check
                    es_manual = a.hora_registro == dt_check(1970, 1, 1, 0, 0, 0) if a.hora_registro else False
                    jugadores_presentes.append(JugadorAsistenciaInfo(
                        jugador_id=jug.id,
                        nombre=jug.nombre,
                        numero=jug.numero,
                        foto=jug.foto,
                        hora_registro=a.hora_registro,
                        manual=es_manual,
                    ))

            # Fecha del partido (ya está en hora local)
            ultimas_asistencias.append(AsistenciaResumenPartido(
                partido_id=p.id,
                jornada_numero=jornada_p.numero if jornada_p else None,
                fecha=p.fecha_hora,
                rival=rival.nombre if rival else "Desconocido",
                tipo=p.tipo,
                jugadores_presentes=jugadores_presentes,
                total_jugadores=total_jugadores,
            ))

        equipos_resumen.append(EquipoResumenCompleto(
            id=equipo.id,
            nombre=equipo.nombre,
            logo=equipo.logo,
            jugadores=jugadores,
            ultimas_asistencias=ultimas_asistencias,
        ))

    return TorneoResumenCompleto(
        torneo=torneo_info,
        tabla_posiciones=tabla_posiciones,
        equipos=equipos_resumen,
    )


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
