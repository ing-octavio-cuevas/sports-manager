from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.database import get_db
from app.models import Asistencia, Partido, Jugador, Equipo
from app.schemas import AsistenciaCreate, AsistenciaResponse, PartidoCapitanResponse, AsistenciaResumenEquipo, AsistenciaResumenJugador
from app.auth import require_role
from app.config import ROL_ANFITRION, ROL_JUGADOR

router = APIRouter(prefix="/asistencias", tags=["Asistencias"])


@router.get("/capitan/{capitan_id}/partidos", response_model=list[PartidoCapitanResponse])
def get_partidos_capitan(capitan_id: int, db: Session = Depends(get_db), usuario=Depends(require_role(ROL_JUGADOR))):
    """
    Obtener los partidos en los que el capitán puede registrar asistencia.
    Incluye es_hoy y caducado para filtrar en el front.
    """
    from datetime import date

    capitan = db.query(Jugador).filter(
        Jugador.id == capitan_id,
        Jugador.es_capitan == True,
    ).first()
    if not capitan:
        raise HTTPException(status_code=404, detail="Capitán no encontrado")

    partidos = db.query(Partido).filter(
        or_(
            Partido.equipo_local_id == capitan.equipo_id,
            Partido.equipo_visitante_id == capitan.equipo_id,
        ),
        Partido.estatus != "Jugado",
    ).all()

    hoy = date.today()
    resultado = []
    for p in partidos:
        es_hoy = p.fecha_hora.date() == hoy if p.fecha_hora else False
        caducado = p.fecha_hora.date() < hoy if p.fecha_hora else False
        resultado.append(PartidoCapitanResponse(
            id=p.id,
            torneo_id=p.torneo_id,
            jornada_id=p.jornada_id,
            equipo_local_id=p.equipo_local_id,
            equipo_visitante_id=p.equipo_visitante_id,
            estatus=p.estatus,
            tipo=p.tipo,
            ubicacion_id=p.ubicacion_id,
            fecha_hora=p.fecha_hora,
            es_hoy=es_hoy,
            caducado=caducado,
        ))

    return resultado


@router.post("", response_model=list[AsistenciaResponse], status_code=201)
def registrar_asistencia_lote(data: AsistenciaCreate, db: Session = Depends(get_db), usuario=Depends(require_role(ROL_JUGADOR))):
    """
    Registrar asistencia en lote del equipo contrario.
    El capitán envía la lista completa de jugadores presentes.
    Una vez enviada, no se puede volver a registrar para ese partido/capitán.
    """
    # Verificar que quien registra es capitán
    capitan = db.query(Jugador).filter(
        Jugador.id == data.registrado_por,
        Jugador.es_capitan == True,
    ).first()
    if not capitan:
        raise HTTPException(status_code=403, detail="Solo un capitán puede registrar asistencia")

    # Verificar partido
    partido = db.query(Partido).filter(Partido.id == data.partido_id).first()
    if not partido:
        raise HTTPException(status_code=404, detail="Partido no encontrado")

    # Validar que sea el día del partido
    from datetime import date
    if partido.fecha_hora:
        hoy = date.today()
        if partido.fecha_hora.date() != hoy:
            raise HTTPException(status_code=400, detail="Solo se puede registrar asistencia el día del partido")

    # Validar que el capitán pertenece a uno de los equipos del partido
    if capitan.equipo_id not in [partido.equipo_local_id, partido.equipo_visitante_id]:
        raise HTTPException(status_code=400, detail="El capitán no pertenece a este partido")

    # Verificar si ya se registró asistencia por este capitán para este partido
    ya_registro = db.query(Asistencia).filter(
        Asistencia.partido_id == data.partido_id,
        Asistencia.registrado_por == data.registrado_por,
    ).first()
    if ya_registro:
        raise HTTPException(status_code=400, detail="Ya se registró asistencia para este partido. No se puede modificar")

    # Determinar el equipo contrario al capitán
    if capitan.equipo_id == partido.equipo_local_id:
        equipo_contrario_id = partido.equipo_visitante_id
    else:
        equipo_contrario_id = partido.equipo_local_id

    # Validar y registrar cada jugador
    resultado = []
    for jugador_id in data.jugador_ids:
        jugador = db.query(Jugador).filter(Jugador.id == jugador_id).first()
        if not jugador:
            raise HTTPException(status_code=404, detail=f"Jugador con id {jugador_id} no encontrado")
        if jugador.equipo_id != equipo_contrario_id:
            raise HTTPException(status_code=400, detail=f"Jugador {jugador.nombre} no pertenece al equipo contrario")

        db_asistencia = Asistencia(
            partido_id=data.partido_id,
            jugador_id=jugador_id,
            registrado_por=data.registrado_por,
            metodo="manual",
        )
        db.add(db_asistencia)
        db.flush()

        resultado.append(AsistenciaResponse(
            id=db_asistencia.id,
            partido_id=db_asistencia.partido_id,
            jugador_id=db_asistencia.jugador_id,
            registrado_por=db_asistencia.registrado_por,
            metodo=db_asistencia.metodo,
            hora_registro=db_asistencia.hora_registro,
            jugador_nombre=jugador.nombre,
            jugador_numero=jugador.numero,
            jugador_foto=jugador.foto,
        ))

    db.commit()
    return resultado


@router.get("/equipo/{equipo_id}/resumen", response_model=AsistenciaResumenEquipo)
def get_resumen_asistencia(equipo_id: int, torneo_id: int, db: Session = Depends(get_db), usuario=Depends(require_role(ROL_JUGADOR))):
    """
    Resumen de asistencia por equipo.
    Devuelve por cada jugador: partidos asistidos / total partidos del equipo.
    """
    equipo = db.query(Equipo).filter(Equipo.id == equipo_id).first()
    if not equipo:
        raise HTTPException(status_code=404, detail="Equipo no encontrado")

    # Total de partidos del equipo en el torneo con estatus "Jugado"
    partidos = db.query(Partido).filter(
        Partido.torneo_id == torneo_id,
        Partido.estatus == "Jugado",
        or_(
            Partido.equipo_local_id == equipo_id,
            Partido.equipo_visitante_id == equipo_id,
        ),
    ).all()
    total_partidos = len(partidos)
    partido_ids = [p.id for p in partidos]

    # Jugadores del equipo
    jugadores = db.query(Jugador).filter(Jugador.equipo_id == equipo_id).all()

    resumen = []
    for jugador in jugadores:
        # Contar asistencias de este jugador en los partidos del equipo
        asistidos = db.query(Asistencia).filter(
            Asistencia.jugador_id == jugador.id,
            Asistencia.partido_id.in_(partido_ids),
        ).count() if partido_ids else 0

        porcentaje = round((asistidos / total_partidos) * 100, 1) if total_partidos > 0 else 0.0

        resumen.append(AsistenciaResumenJugador(
            jugador_id=jugador.id,
            jugador_nombre=jugador.nombre,
            jugador_numero=jugador.numero,
            es_capitan=jugador.es_capitan,
            partidos_asistidos=asistidos,
            total_partidos=total_partidos,
            porcentaje_asistencia=porcentaje,
        ))

    return AsistenciaResumenEquipo(
        equipo_id=equipo.id,
        equipo_nombre=equipo.nombre,
        torneo_id=torneo_id,
        total_partidos=total_partidos,
        jugadores=resumen,
    )


@router.get("/partido/{partido_id}", response_model=list[AsistenciaResponse])
def list_asistencias(partido_id: int, db: Session = Depends(get_db), usuario=Depends(require_role(ROL_JUGADOR))):
    """Listar asistencias de un partido."""
    asistencias = db.query(Asistencia).filter(Asistencia.partido_id == partido_id).all()
    resultado = []
    for a in asistencias:
        jugador = db.query(Jugador).filter(Jugador.id == a.jugador_id).first()
        resultado.append(AsistenciaResponse(
            id=a.id,
            partido_id=a.partido_id,
            jugador_id=a.jugador_id,
            registrado_por=a.registrado_por,
            metodo=a.metodo,
            hora_registro=a.hora_registro,
            jugador_nombre=jugador.nombre if jugador else None,
            jugador_numero=jugador.numero if jugador else None,
            jugador_foto=jugador.foto if jugador else None,
        ))
    return resultado


from app.schemas import EstadoAsistenciaPartido


@router.get("/partido/{partido_id}/estado", response_model=EstadoAsistenciaPartido)
def get_estado_asistencia(partido_id: int, db: Session = Depends(get_db), usuario=Depends(require_role(ROL_JUGADOR))):
    """
    Estado de asistencia de un partido.
    Indica si cada equipo ya completó su registro de asistencia.
    El capitán del equipo local registra asistencia del visitante y viceversa.
    """
    partido = db.query(Partido).filter(Partido.id == partido_id).first()
    if not partido:
        raise HTTPException(status_code=404, detail="Partido no encontrado")

    # Buscar si el capitán del equipo local ya registró (registra jugadores del visitante)
    capitan_local = db.query(Jugador).filter(
        Jugador.equipo_id == partido.equipo_local_id,
        Jugador.es_capitan == True,
    ).first()

    capitan_visitante = db.query(Jugador).filter(
        Jugador.equipo_id == partido.equipo_visitante_id,
        Jugador.es_capitan == True,
    ).first()

    # El capitán local registra asistencia del visitante
    asistencia_local = None
    if capitan_local:
        asistencia_local = db.query(Asistencia).filter(
            Asistencia.partido_id == partido_id,
            Asistencia.registrado_por == capitan_local.id,
        ).first()

    # El capitán visitante registra asistencia del local
    asistencia_visitante = None
    if capitan_visitante:
        asistencia_visitante = db.query(Asistencia).filter(
            Asistencia.partido_id == partido_id,
            Asistencia.registrado_por == capitan_visitante.id,
        ).first()

    return EstadoAsistenciaPartido(
        partido_id=partido_id,
        equipo_local_id=partido.equipo_local_id,
        equipo_visitante_id=partido.equipo_visitante_id,
        asistencia_local_completada=asistencia_local is not None,
        asistencia_visitante_completada=asistencia_visitante is not None,
        registrado_por_local=capitan_local.id if capitan_local and asistencia_local else None,
        registrado_por_visitante=capitan_visitante.id if capitan_visitante and asistencia_visitante else None,
    )


@router.delete("/{asistencia_id}", status_code=204)
def delete_asistencia(asistencia_id: int, db: Session = Depends(get_db), usuario=Depends(require_role(ROL_ANFITRION))):
    """Eliminar un registro de asistencia."""
    asistencia = db.query(Asistencia).filter(Asistencia.id == asistencia_id).first()
    if not asistencia:
        raise HTTPException(status_code=404, detail="Asistencia no encontrada")
    db.delete(asistencia)
    db.commit()


# ─── Registro por árbitro (escaneo QR) ───────────────────────

@router.post("/arbitro/escanear", response_model=AsistenciaResponse, status_code=201)
def registrar_asistencia_arbitro(partido_id: int, jugador_id: int, db: Session = Depends(get_db), usuario=Depends(require_role(ROL_ANFITRION))):
    """
    Registro de asistencia por árbitro vía escaneo de QR.
    El QR contiene el jugador_id. El árbitro selecciona el partido.
    Devuelve foto, nombre y número del jugador como confirmación.
    """
    # Verificar partido
    partido = db.query(Partido).filter(Partido.id == partido_id).first()
    if not partido:
        raise HTTPException(status_code=404, detail="Partido no encontrado")

    # Verificar jugador
    jugador = db.query(Jugador).filter(Jugador.id == jugador_id).first()
    if not jugador:
        raise HTTPException(status_code=404, detail="Jugador no encontrado")

    # Validar que el jugador pertenece a uno de los equipos del partido
    if jugador.equipo_id not in [partido.equipo_local_id, partido.equipo_visitante_id]:
        raise HTTPException(status_code=400, detail="El jugador no pertenece a ninguno de los equipos de este partido")

    # Verificar duplicado
    existe = db.query(Asistencia).filter(
        Asistencia.partido_id == partido_id,
        Asistencia.jugador_id == jugador_id,
    ).first()
    if existe:
        raise HTTPException(status_code=400, detail="El jugador ya tiene asistencia registrada en este partido")

    db_asistencia = Asistencia(
        partido_id=partido_id,
        jugador_id=jugador_id,
        registrado_por=jugador_id,  # En modo árbitro, se registra como auto-registro
        metodo="qr",
    )
    db.add(db_asistencia)
    db.commit()
    db.refresh(db_asistencia)

    return AsistenciaResponse(
        id=db_asistencia.id,
        partido_id=db_asistencia.partido_id,
        jugador_id=db_asistencia.jugador_id,
        registrado_por=db_asistencia.registrado_por,
        metodo=db_asistencia.metodo,
        hora_registro=db_asistencia.hora_registro,
        jugador_nombre=jugador.nombre,
        jugador_numero=jugador.numero,
        jugador_foto=jugador.foto,
    )
