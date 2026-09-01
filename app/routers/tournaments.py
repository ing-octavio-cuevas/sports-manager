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
    JugadorResumenPublico,
    ResultadosEquipoPublicoResponse,
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


@router.get("/equipo/{equipo_uuid}/resultados", response_model=ResultadosEquipoPublicoResponse)
@limiter.limit("30/minute")
def get_resultados_equipo_publico(request: Request, equipo_uuid: str, db: Session = Depends(get_db)):
    """Resultados de todos los partidos oficiales jugados de un equipo (público, por UUID)."""
    from app.models import Equipo, Jornada
    from app.schemas import ResultadosEquipoPublicoResponse, ResultadoPartidoPublico
    from sqlalchemy import or_

    equipo = db.query(Equipo).filter(Equipo.uuid == equipo_uuid).first()
    if not equipo:
        raise HTTPException(status_code=404, detail="Equipo no encontrado")

    torneo = db.query(Torneo).filter(Torneo.id == equipo.torneo_id).first()

    # Partidos oficiales jugados del equipo
    partidos = db.query(Partido).filter(
        Partido.torneo_id == equipo.torneo_id,
        Partido.estatus == "Jugado",
        Partido.tipo == "Oficial",
        or_(
            Partido.equipo_local_id == equipo.id,
            Partido.equipo_visitante_id == equipo.id,
        ),
    ).order_by(Partido.fecha_hora.desc()).all()

    # Precargar equipos del torneo para nombres/logos
    equipos_torneo = db.query(Equipo).filter(Equipo.torneo_id == equipo.torneo_id).all()
    equipos_map = {e.id: e for e in equipos_torneo}

    resultados = []
    for p in partidos:
        local = equipos_map.get(p.equipo_local_id)
        visitante = equipos_map.get(p.equipo_visitante_id)

        # Determinar resultado desde la perspectiva del equipo consultado
        if p.equipo_local_id == equipo.id:
            pts_equipo = p.puntos_local or 0
            pts_rival = p.puntos_visitante or 0
        else:
            pts_equipo = p.puntos_visitante or 0
            pts_rival = p.puntos_local or 0

        if pts_equipo > pts_rival:
            resultado = "G"
        elif pts_rival > pts_equipo:
            resultado = "P"
        else:
            resultado = "E"

        # Jornada
        jornada = db.query(Jornada).filter(Jornada.id == p.jornada_id).first() if p.jornada_id else None

        resultados.append(ResultadoPartidoPublico(
            partido_id=p.id,
            jornada_numero=jornada.numero if jornada else None,
            fecha=p.fecha_hora,
            tipo=p.tipo,
            equipo_local=local.nombre if local else "Desconocido",
            equipo_local_logo=local.logo if local else None,
            equipo_visitante=visitante.nombre if visitante else "Desconocido",
            equipo_visitante_logo=visitante.logo if visitante else None,
            puntos_local=p.puntos_local,
            puntos_visitante=p.puntos_visitante,
            resultado=resultado,
        ))

    return ResultadosEquipoPublicoResponse(
        equipo_id=equipo.id,
        equipo_nombre=equipo.nombre,
        equipo_logo=equipo.logo,
        torneo_nombre=torneo.nombre if torneo else None,
        resultados=resultados,
    )


@router.get("/{torneo_id}/resumen", response_model=TorneoResumenCompleto)
@limiter.limit("15/minute")
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

        # Ganador/perdedor: solo por puntos del partido
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
            Jugador.equipo_id == equipo.id,
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

            # Jugadores presentes (detalle) - incluye jugadores dados de baja
            # Obtener todos los jugadores del equipo (activos e inactivos) para buscar asistencias
            todos_jugadores_equipo = db.query(Jugador).filter(Jugador.equipo_id == equipo.id).all()
            asistencias_partido = db.query(Asistencia).filter(
                Asistencia.partido_id == p.id,
                Asistencia.jugador_id.in_([j.id for j in todos_jugadores_equipo]),
            ).all()

            from app.schemas import JugadorAsistenciaInfo
            jugadores_presentes = []
            for a in asistencias_partido:
                jug = next((j for j in todos_jugadores_equipo if j.id == a.jugador_id), None)
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
                        es_capitan=jug.es_capitan if jug.es_capitan else False,
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

        # ─── Estadísticas del equipo ─────────────────────────
        from app.schemas import EstadisticasEquipo

        # Partidos oficiales jugados de este equipo
        partidos_equipo_jugados = [p for p in partidos_jugados
            if p.equipo_local_id == equipo.id or p.equipo_visitante_id == equipo.id]

        pj = len(partidos_equipo_jugados)
        pg = 0
        pp = 0
        puntos_totales = 0
        resultados = []

        # Ordenar por fecha desc para ultimos_resultados
        partidos_ordenados = sorted(partidos_equipo_jugados, key=lambda x: x.fecha_hora or '', reverse=True)

        for partido in partidos_ordenados:
            if partido.equipo_local_id == equipo.id:
                pts_equipo = partido.puntos_local or 0
                pts_rival = partido.puntos_visitante or 0
            else:
                pts_equipo = partido.puntos_visitante or 0
                pts_rival = partido.puntos_local or 0

            puntos_totales += pts_equipo

            # Determinar ganador: solo por puntos
            if pts_equipo > pts_rival:
                pg += 1
                resultados.append("G")
            elif pts_rival > pts_equipo:
                pp += 1
                resultados.append("P")
            else:
                resultados.append("E")

        ultimos_10 = resultados[:10]

        # Racha actual
        racha = 0
        if ultimos_10:
            primer_resultado = ultimos_10[0]
            for r in ultimos_10:
                if r == primer_resultado:
                    racha += 1
                else:
                    break
            if primer_resultado == "P":
                racha = -racha

        porcentaje_victorias = round((pg / pj) * 100, 1) if pj > 0 else 0.0
        promedio_puntos = round(puntos_totales / pj, 2) if pj > 0 else 0.0

        # Distribución de posiciones
        distribucion = {}
        for j in jugadores:
            pos = j.posicion or "Sin posición"
            if pos.strip():
                distribucion[pos] = distribucion.get(pos, 0) + 1

        # Puntos acumulados (orden cronológico)
        partidos_cronologicos = sorted(partidos_ordenados, key=lambda x: x.fecha_hora or '')
        puntos_acumulados = []
        acumulado = 0
        for p in partidos_cronologicos:
            if p.equipo_local_id == equipo.id:
                acumulado += p.puntos_local or 0
            else:
                acumulado += p.puntos_visitante or 0
            puntos_acumulados.append(acumulado)

        estadisticas = EstadisticasEquipo(
            total_jugadores=len(jugadores),
            partidos_jugados=pj,
            partidos_ganados=pg,
            partidos_perdidos=pp,
            puntos_totales=puntos_totales,
            porcentaje_victorias=porcentaje_victorias,
            promedio_puntos_partido=promedio_puntos,
            ultimos_resultados=ultimos_10,
            puntos_acumulados=puntos_acumulados,
            racha_actual=racha,
            distribucion_posiciones=distribucion,
        )

        # ─── Asistencia por jugador ──────────────────────────
        # Filtrar partidos oficiales jugados a partir de fecha_inicio_asistencias
        if torneo.fecha_inicio_asistencias:
            partidos_para_asistencia = [
                p for p in partidos_equipo_jugados
                if p.fecha_hora and p.fecha_hora >= torneo.fecha_inicio_asistencias
            ]
        else:
            partidos_para_asistencia = partidos_equipo_jugados

        total_partidos_equipo = len(partidos_para_asistencia)
        minimo_porcentaje = torneo.asistencia_minima_porcentaje

        jugadores_resumen = []
        if equipo.mostrar_publico:
            partidos_asistencia_ids = [p.id for p in partidos_para_asistencia]
            for jug in jugadores:
                # Campos de asistencia solo si la bandera del torneo lo permite
                if torneo.mostrar_asistencia_publica:
                    asistencias_jug = db.query(Asistencia).filter(
                        Asistencia.jugador_id == jug.id,
                        Asistencia.partido_id.in_(partidos_asistencia_ids),
                    ).count() if partidos_asistencia_ids else 0

                    porcentaje_asist = round((asistencias_jug / total_partidos_equipo) * 100, 1) if total_partidos_equipo > 0 else 0.0
                    cumple = porcentaje_asist >= minimo_porcentaje if minimo_porcentaje is not None else True
                else:
                    asistencias_jug = None
                    porcentaje_asist = None
                    cumple = None

                jugadores_resumen.append(JugadorResumenPublico(
                    id=jug.id,
                    nombre=jug.nombre,
                    numero=jug.numero,
                    posicion=jug.posicion,
                    es_capitan=jug.es_capitan if jug.es_capitan else False,
                    foto=jug.foto,
                    estatus=jug.estatus,
                    fecha_baja=jug.fecha_baja,
                    asistencia_partidos=asistencias_jug,
                    asistencia_total_partidos=total_partidos_equipo if torneo.mostrar_asistencia_publica else None,
                    asistencia_porcentaje=porcentaje_asist,
                    asistencia_cumple=cumple,
                ))

        equipos_resumen.append(EquipoResumenCompleto(
            id=equipo.id,
            uuid=equipo.uuid,
            nombre=equipo.nombre,
            logo=equipo.logo,
            mostrar_publico=equipo.mostrar_publico,
            jugadores=jugadores_resumen,
            ultimas_asistencias=ultimas_asistencias,
            estadisticas=estadisticas if equipo.mostrar_publico else None,
        ))

    # ─── Rol: jornada activa (próxima con partidos pendientes) ──
    from app.schemas import RolJornada, PartidoRolItem
    from datetime import datetime as dt_rol, timezone as tz_rol, timedelta as td_rol
    from app.config import TIMEZONE_OFFSET as TZ_OFF_ROL

    tz_local = tz_rol(td_rol(hours=TZ_OFF_ROL))
    hoy_rol = dt_rol.now(tz_local).date()

    # Buscar jornada más próxima con partidos pendientes
    jornadas_torneo = db.query(Jornada).filter(Jornada.torneo_id == torneo_id).order_by(Jornada.numero).all()
    rol = None
    for jornada_r in jornadas_torneo:
        partidos_pendientes = db.query(Partido).filter(
            Partido.jornada_id == jornada_r.id,
            Partido.estatus != "Jugado",
            Partido.fecha_hora >= dt_rol.combine(hoy_rol, dt_rol.min.time()),
        ).order_by(Partido.ubicacion_id, Partido.fecha_hora).all()
        if partidos_pendientes:
            partidos_rol = []
            for pr in partidos_pendientes:
                local = next((e for e in equipos if e.id == pr.equipo_local_id), None)
                visitante = next((e for e in equipos if e.id == pr.equipo_visitante_id), None)
                ubic = db.query(TorneoUbicacion).filter(TorneoUbicacion.id == pr.ubicacion_id).first() if pr.ubicacion_id else None
                partidos_rol.append(PartidoRolItem(
                    equipo_local_nombre=local.nombre if local else "Desconocido",
                    equipo_local_logo=local.logo if local else None,
                    equipo_visitante_nombre=visitante.nombre if visitante else "Desconocido",
                    equipo_visitante_logo=visitante.logo if visitante else None,
                    fecha_hora=pr.fecha_hora,
                    ubicacion_nombre=ubic.nombre if ubic else None,
                    ubicacion_direccion=ubic.direccion if ubic else None,
                    ubicacion_url=ubic.ubicacion if ubic else None,
                ))
            rol = RolJornada(
                jornada_numero=jornada_r.numero,
                jornada_fecha=jornada_r.fecha,
                partidos=partidos_rol,
            )
            break

    return TorneoResumenCompleto(
        torneo=torneo_info,
        tabla_posiciones=tabla_posiciones,
        equipos=equipos_resumen,
        rol=rol,
    )


@router.get("/{torneo_id}/dashboard")
def get_torneo_dashboard(torneo_id: int, db: Session = Depends(get_db), usuario=Depends(require_role(ROL_ANFITRION))):
    """Dashboard completo del torneo para el anfitrión (KPIs, tabla, actividad, finanzas, asistencias)."""
    from app.models import (
        Equipo, Jugador, Jornada, PartidoSet, PartidoArbitraje,
        Asistencia, EventoAuditoria,
    )
    from app.schemas import (
        DashboardTorneoResponse, DashboardTorneoInfo, DashboardKpis,
        DashboardProximoPartido, DashboardPosicion, DashboardActividad,
        DashboardEstadisticasGenerales, DashboardFinanzas,
        DashboardAsistenciaEquipo, DashboardAsistenciaJugador, DashboardAsistenciaJornada,
        DashboardAsistenciaPartido,
    )
    from sqlalchemy import or_
    from datetime import datetime as dt_dash, timezone as tz_dash, timedelta as td_dash
    from app.config import TIMEZONE_OFFSET as TZ_DASH

    torneo = db.query(Torneo).filter(Torneo.id == torneo_id).first()
    if not torneo:
        raise HTTPException(status_code=404, detail="Torneo no encontrado")
    _verificar_acceso_torneo(torneo, usuario)

    # ─── Datos base ──────────────────────────────────────────
    equipos = db.query(Equipo).filter(Equipo.torneo_id == torneo_id, Equipo.estatus == True).all()
    equipos_map = {e.id: e for e in equipos}
    equipos_ids = list(equipos_map.keys())

    jugadores = db.query(Jugador).filter(Jugador.equipo_id.in_(equipos_ids)).all() if equipos_ids else []

    jornadas = db.query(Jornada).filter(Jornada.torneo_id == torneo_id).order_by(Jornada.numero).all()

    todos_partidos = db.query(Partido).filter(
        Partido.torneo_id == torneo_id,
        Partido.tipo == "Oficial",
    ).all()
    partidos_jugados = [p for p in todos_partidos if p.estatus == "Jugado"]

    # ─── KPIs ────────────────────────────────────────────────
    jugadores_activos = sum(1 for j in jugadores if j.estatus)
    jugadores_baja = len(jugadores) - jugadores_activos

    # Jornadas completadas: todas sus partidos oficiales están jugados (y tiene al menos uno)
    jornadas_completadas = 0
    for jor in jornadas:
        partidos_jor = [p for p in todos_partidos if p.jornada_id == jor.id]
        if partidos_jor and all(p.estatus == "Jugado" for p in partidos_jor):
            jornadas_completadas += 1

    partidos_programados = len(todos_partidos)
    n_jugados = len(partidos_jugados)
    avance = round((n_jugados / partidos_programados) * 100) if partidos_programados > 0 else 0

    kpis = DashboardKpis(
        equipos=len(equipos),
        jugadores_total=len(jugadores),
        jugadores_activos=jugadores_activos,
        jugadores_baja=jugadores_baja,
        partidos_jugados=n_jugados,
        partidos_programados=partidos_programados,
        jornadas_completadas=jornadas_completadas,
        jornadas_total=len(jornadas),
        avance_porcentaje=avance,
    )

    # ─── Próximos partidos (pendientes, futuros) ─────────────
    tz_local = tz_dash(td_dash(hours=TZ_DASH))
    ahora_local = dt_dash.now(tz_local).replace(tzinfo=None)

    pendientes = [
        p for p in todos_partidos
        if p.estatus != "Jugado" and p.fecha_hora and p.fecha_hora >= ahora_local
    ]
    pendientes.sort(key=lambda x: x.fecha_hora)

    proximos = []
    for p in pendientes[:10]:
        local = equipos_map.get(p.equipo_local_id)
        visitante = equipos_map.get(p.equipo_visitante_id)
        ubic = db.query(TorneoUbicacion).filter(TorneoUbicacion.id == p.ubicacion_id).first() if p.ubicacion_id else None
        proximos.append(DashboardProximoPartido(
            fecha_hora=p.fecha_hora,
            local_nombre=local.nombre if local else "Desconocido",
            local_logo=local.logo if local else None,
            visitante_nombre=visitante.nombre if visitante else "Desconocido",
            visitante_logo=visitante.logo if visitante else None,
            cancha=ubic.nombre if ubic else None,
        ))

    # ─── Sets por partido (para pf/pc y estadísticas) ────────
    partido_ids_jugados = [p.id for p in partidos_jugados]
    sets_por_partido = {}
    if partido_ids_jugados:
        todos_sets = db.query(PartidoSet).filter(PartidoSet.partido_id.in_(partido_ids_jugados)).all()
        for s in todos_sets:
            sets_por_partido.setdefault(s.partido_id, []).append(s)

    # ─── Tabla de posiciones (con pf/pc de sets) ─────────────
    stats = {}
    for e in equipos:
        stats[e.id] = {
            "equipo_id": e.id, "equipo_nombre": e.nombre, "equipo_logo": e.logo,
            "pj": 0, "pg": 0, "pp": 0, "pf": 0, "pc": 0, "pts": 0,
        }

    for p in partidos_jugados:
        li, vi = p.equipo_local_id, p.equipo_visitante_id
        if li not in stats or vi not in stats:
            continue
        stats[li]["pj"] += 1
        stats[vi]["pj"] += 1
        stats[li]["pts"] += p.puntos_local or 0
        stats[vi]["pts"] += p.puntos_visitante or 0

        # Puntos a favor / en contra a partir de los sets
        sets_p = sets_por_partido.get(p.id, [])
        pf_local = sum(s.puntos_local or 0 for s in sets_p)
        pf_visitante = sum(s.puntos_visitante or 0 for s in sets_p)
        stats[li]["pf"] += pf_local
        stats[li]["pc"] += pf_visitante
        stats[vi]["pf"] += pf_visitante
        stats[vi]["pc"] += pf_local

        # Ganador por puntos del partido
        if (p.puntos_local or 0) > (p.puntos_visitante or 0):
            stats[li]["pg"] += 1
            stats[vi]["pp"] += 1
        elif (p.puntos_visitante or 0) > (p.puntos_local or 0):
            stats[vi]["pg"] += 1
            stats[li]["pp"] += 1

    tabla_ordenada = sorted(stats.values(), key=lambda x: (-x["pts"], -(x["pf"] - x["pc"])))
    tabla_posiciones = [DashboardPosicion(**row) for row in tabla_ordenada]

    # ─── Estadísticas generales ──────────────────────────────
    sets_jugados = sum(len(v) for v in sets_por_partido.values())
    puntos_totales = 0
    for sets_p in sets_por_partido.values():
        for s in sets_p:
            puntos_totales += (s.puntos_local or 0) + (s.puntos_visitante or 0)
    promedio_por_set = round(puntos_totales / sets_jugados, 1) if sets_jugados > 0 else 0.0
    partidos_por_jugar = partidos_programados - n_jugados

    # Tendencia de puntos: puntos por jornada (cronológico, últimas jornadas jugadas)
    tendencia = []
    for jor in jornadas:
        partidos_jor = [p for p in partidos_jugados if p.jornada_id == jor.id]
        if not partidos_jor:
            continue
        pts_jor = 0
        for p in partidos_jor:
            for s in sets_por_partido.get(p.id, []):
                pts_jor += (s.puntos_local or 0) + (s.puntos_visitante or 0)
        tendencia.append(pts_jor)
    tendencia = tendencia[-7:]

    estadisticas_generales = DashboardEstadisticasGenerales(
        sets_jugados=sets_jugados,
        puntos_totales=puntos_totales,
        promedio_por_set=promedio_por_set,
        partidos_por_jugar=partidos_por_jugar,
        tendencia_puntos=tendencia,
    )

    # ─── Finanzas ────────────────────────────────────────────
    ingresos_inscripciones = sum(float(e.monto_pagado) for e in equipos if e.inscripcion_pagada and e.monto_pagado)
    arbitrajes = db.query(PartidoArbitraje).filter(PartidoArbitraje.equipo_id.in_(equipos_ids)).all() if equipos_ids else []
    # Filtrar arbitrajes de partidos de este torneo
    arb_torneo = []
    partidos_torneo_ids = {p.id for p in todos_partidos}
    for a in arbitrajes:
        if a.partido_id in partidos_torneo_ids:
            arb_torneo.append(a)
    ingresos_arbitrajes = sum(float(a.monto) for a in arb_torneo if a.pagado and a.monto)
    pendientes_arbitrajes = sum(float(a.monto) for a in arb_torneo if not a.pagado and a.monto)
    # Pendientes de inscripción
    pendientes_inscripcion = sum(float(e.monto_pagado) for e in equipos if not e.inscripcion_pagada and e.monto_pagado)

    ingresos_totales = ingresos_inscripciones + ingresos_arbitrajes
    pendientes_total = pendientes_arbitrajes + pendientes_inscripcion
    base_total = ingresos_totales + pendientes_total
    porcentaje_pagado = round((ingresos_totales / base_total) * 100) if base_total > 0 else 0

    finanzas = DashboardFinanzas(
        ingresos_totales=round(ingresos_totales, 2),
        pendientes=round(pendientes_total, 2),
        porcentaje_pagado=porcentaje_pagado,
    )

    # ─── Actividad reciente (desde auditoría + partidos) ─────
    actividad = []
    eventos = db.query(EventoAuditoria).filter(
        EventoAuditoria.partido_id.in_(partidos_torneo_ids) if partidos_torneo_ids else False,
        EventoAuditoria.tipo_evento == "SCORE_MODIFICACION",
    ).order_by(EventoAuditoria.fecha.desc()).limit(15).all() if partidos_torneo_ids else []

    for ev in eventos:
        actividad.append(DashboardActividad(
            tipo="resultado",
            descripcion=ev.descripcion or "Modificación de marcador",
            fecha=ev.fecha,
        ))

    # ─── Asistencias por equipo ──────────────────────────────
    numeros_jornadas = [jor.numero for jor in jornadas]

    # Filtro fecha_inicio_asistencias
    fecha_inicio = torneo.fecha_inicio_asistencias

    jornada_numero_por_id = {jor.id: jor.numero for jor in jornadas}

    asistencias_por_equipo = []
    for e in equipos:
        jugadores_equipo = [j for j in jugadores if j.equipo_id == e.id]

        # Partidos oficiales jugados del equipo (respetando fecha_inicio)
        partidos_equipo = [
            p for p in partidos_jugados
            if (p.equipo_local_id == e.id or p.equipo_visitante_id == e.id)
            and (not fecha_inicio or (p.fecha_hora and p.fecha_hora >= fecha_inicio))
        ]
        # Un equipo puede tener N partidos por jornada: se cuenta por PARTIDO, no por jornada.
        partidos_equipo.sort(key=lambda p: (jornada_numero_por_id.get(p.jornada_id, 0), p.fecha_hora or dt_dash.min))
        partido_ids_equipo = [p.id for p in partidos_equipo]

        # Agrupar partidos del equipo por jornada (preservando orden)
        partidos_por_jornada = {}
        for p in partidos_equipo:
            partidos_por_jornada.setdefault(p.jornada_id, []).append(p)
        # Orden de jornadas que el equipo jugó
        orden_jornadas = sorted(
            partidos_por_jornada.keys(),
            key=lambda jid: jornada_numero_por_id.get(jid, 0),
        )

        # Rival por partido
        def _rival_nombre(p):
            rival_id = p.equipo_visitante_id if p.equipo_local_id == e.id else p.equipo_local_id
            rival = equipos_map.get(rival_id)
            return rival.nombre if rival else "Desconocido"

        # Asistencias registradas de los jugadores del equipo
        asistencias_registradas = set()
        if partido_ids_equipo and jugadores_equipo:
            regs = db.query(Asistencia).filter(
                Asistencia.partido_id.in_(partido_ids_equipo),
                Asistencia.jugador_id.in_([j.id for j in jugadores_equipo]),
            ).all()
            for r in regs:
                asistencias_registradas.add((r.jugador_id, r.partido_id))

        total_partidos_equipo = len(partidos_equipo)

        jugadores_dash = []
        asistencias_totales_equipo = 0
        for j in jugadores_equipo:
            asistio = 0
            por_jornada = []
            # Una entrada por jornada, con el detalle de cada partido de esa jornada
            for jid in orden_jornadas:
                partidos_jor = partidos_por_jornada[jid]
                detalle_partidos = []
                asistio_jornada = 0
                for p in partidos_jor:
                    presente = (j.id, p.id) in asistencias_registradas
                    if presente:
                        asistio_jornada += 1
                        asistio += 1
                    detalle_partidos.append(DashboardAsistenciaPartido(
                        partido_id=p.id,
                        rival=_rival_nombre(p),
                        fecha_hora=p.fecha_hora,
                        estado="presente" if presente else "ausente",
                    ))

                total_jor = len(partidos_jor)
                if asistio_jornada == 0:
                    estado_jornada = "ausente"
                elif asistio_jornada == total_jor:
                    estado_jornada = "presente"
                else:
                    estado_jornada = "parcial"

                por_jornada.append(DashboardAsistenciaJornada(
                    jornada=jornada_numero_por_id.get(jid, 0),
                    estado=estado_jornada,
                    asistencias=asistio_jornada,
                    total_partidos=total_jor,
                    partidos=detalle_partidos,
                ))

            porcentaje = round((asistio / total_partidos_equipo) * 100, 1) if total_partidos_equipo > 0 else 0.0
            asistencias_totales_equipo += asistio
            jugadores_dash.append(DashboardAsistenciaJugador(
                id=j.id,
                nombre=j.nombre,
                numero=j.numero,
                posicion=j.posicion,
                foto=j.foto,
                asistencias=asistio,
                total=total_partidos_equipo,
                porcentaje=porcentaje,
                por_jornada=por_jornada,
            ))

        asistencias_posibles = total_partidos_equipo * len(jugadores_equipo)
        promedio_equipo = round((asistencias_totales_equipo / asistencias_posibles) * 100, 1) if asistencias_posibles > 0 else 0.0

        asistencias_por_equipo.append(DashboardAsistenciaEquipo(
            equipo_id=e.id,
            equipo_nombre=e.nombre,
            equipo_logo=e.logo,
            jornadas=numeros_jornadas,
            promedio_asistencia=promedio_equipo,
            asistencias_totales=asistencias_totales_equipo,
            asistencias_posibles=asistencias_posibles,
            jugadores=jugadores_dash,
        ))

    return DashboardTorneoResponse(
        torneo=DashboardTorneoInfo(
            id=torneo.id,
            nombre=torneo.nombre,
            periodo=torneo.periodo,
            categoria=torneo.categoria,
            logo=torneo.logo,
        ),
        kpis=kpis,
        proximos_partidos=proximos,
        tabla_posiciones=tabla_posiciones,
        actividad_reciente=actividad,
        estadisticas_generales=estadisticas_generales,
        finanzas=finanzas,
        asistencias_por_equipo=asistencias_por_equipo,
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
