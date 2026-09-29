"""
Scheduler in-process (APScheduler) para recordatorios de asistencia por WhatsApp.

Corre dentro del mismo proceso de FastAPI. Como el despliegue es de un solo
worker/instancia, no hay riesgo de duplicación entre procesos. El anti-duplicados
por (capitán, día) lo garantiza la tabla `recordatorio_asistencia`: un capitán
recibe como máximo un recordatorio por día.

El job corre a horas fijas (REMINDER_HOURS, por defecto 8:00 y 20:00 hora local
UTC-6). En cada corrida busca, para cada capitán, partidos que cumplan LAS TRES
condiciones:
  1. Asistencia PENDIENTE: el capitán aún no registró (Asistencia.registrado_por
     != capitan.id).
  2. Dentro del HORARIO PERMITIDO: la ventana de registro sigue abierta, es decir
     el registro ya inició (fecha_inicio_asistencias del torneo, si aplica) y aún
     no expiró (fecha_hora + horas_limite_asistencia >= ahora).
  3. Partido NO TERMINADO: Partido.estatus != "Jugado".

Se agrupan los partidos pendientes por capitán y se envía UN solo mensaje por
capitán (máximo uno por día gracias al anti-duplicados).
"""

import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.exc import IntegrityError

from app.database import SessionLocal, engine
from app.models import (
    Partido,
    Torneo,
    Jugador,
    Asistencia,
    RecordatorioAsistencia,
)
from app.audit import registrar_evento, TipoEvento
from app.whatsapp_service import send_recordatorio_asistencia, WhatsAppError
from app.config import (
    TIMEZONE_OFFSET,
    REMINDER_ENABLED,
    REMINDER_HOURS,
    WHATSAPP_ENABLED,
    TEST_REMINDER_TIME,
    TEST_REMINDER_CELULAR,
    TEST_REMINDER_NOMBRE,
)

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None

# Zona horaria local del proyecto (UTC-6). fecha_hora se guarda naive en esta zona.
_TZ = timezone(timedelta(hours=TIMEZONE_OFFSET))

# Estatus que indica que el partido ya terminó (no se debe recordar).
_ESTATUS_TERMINADO = "Jugado"


def _ensure_table():
    """Crea la tabla recordatorio_asistencia si no existe (create_all selectivo)."""
    try:
        RecordatorioAsistencia.__table__.create(bind=engine, checkfirst=True)
    except Exception:
        logger.exception("No se pudo asegurar la tabla recordatorio_asistencia")


def _capitan_de_equipo(db, equipo_id: int) -> Jugador | None:
    return (
        db.query(Jugador)
        .filter(
            Jugador.equipo_id == equipo_id,
            Jugador.es_capitan == True,  # noqa: E712
            Jugador.estatus == True,  # noqa: E712
        )
        .first()
    )


def _asistencia_pendiente(db, partido_id: int, capitan_id: int) -> bool:
    """True si el capitán aún no registró la asistencia de su equipo en el partido."""
    existe = (
        db.query(Asistencia)
        .filter(
            Asistencia.partido_id == partido_id,
            Asistencia.registrado_por == capitan_id,
        )
        .first()
    )
    return existe is None


def _cierre_registro(partido, torneo):
    """
    Fecha/hora en que cierra el registro de asistencia del partido.
    Devuelve None si el torneo no define horas_limite_asistencia (sin cierre).
    """
    if not partido.fecha_hora or not torneo or not torneo.horas_limite_asistencia:
        return None
    return partido.fecha_hora + timedelta(hours=torneo.horas_limite_asistencia)


def _registro_dentro_horario(partido, torneo, ahora_naive) -> bool:
    """
    True si el registro de asistencia está dentro del horario permitido:
      - ya inició (fecha_inicio_asistencias del torneo, si está definida), y
      - no ha expirado (fecha_hora + horas_limite_asistencia >= ahora).
    Si el torneo no define horas_limite_asistencia, se considera siempre abierto.
    """
    if not partido.fecha_hora:
        return False

    # ¿Ya inició el periodo de asistencias del torneo?
    if torneo and torneo.fecha_inicio_asistencias:
        if ahora_naive < torneo.fecha_inicio_asistencias:
            return False

    # ¿Aún no expira la ventana?
    cierre = _cierre_registro(partido, torneo)
    if cierre is not None and ahora_naive > cierre:
        return False

    return True


def _ya_recordado_hoy(db, capitan_id: int, fecha_dia) -> bool:
    """True si ya se registró un recordatorio para este capitán en este día."""
    return (
        db.query(RecordatorioAsistencia)
        .filter(
            RecordatorioAsistencia.capitan_id == capitan_id,
            RecordatorioAsistencia.fecha_dia == fecha_dia,
        )
        .first()
        is not None
    )


def _marcar_recordatorio(db, capitan_id, fecha_dia, celular, num_partidos, estado, detalle):
    """Inserta el registro anti-duplicados (capitán + día). Devuelve True si se insertó."""
    registro = RecordatorioAsistencia(
        capitan_id=capitan_id,
        fecha_dia=fecha_dia,
        celular=celular,
        num_partidos=num_partidos,
        estado=estado,
        detalle=detalle,
    )
    db.add(registro)
    try:
        db.commit()
        return True
    except IntegrityError:
        # Otra corrida ya lo insertó (carrera). No es un error real.
        db.rollback()
        return False


def _recolectar_pendientes_por_capitan(db, ahora_naive):
    """
    Recorre los partidos publicados y devuelve un dict:
        { capitan_id: {"capitan": Jugador, "num_partidos": int} }
    con solo los partidos que cumplen las 3 condiciones (pendiente, dentro de
    horario permitido, no terminado) para ese capitán.
    """
    torneos = {
        t.id: t for t in db.query(Torneo).filter(Torneo.publicado == True).all()  # noqa: E712
    }
    if not torneos:
        return {}

    # Partidos publicados, con fecha_hora, no terminados.
    partidos = (
        db.query(Partido)
        .filter(
            Partido.torneo_id.in_(list(torneos.keys())),
            Partido.fecha_hora.isnot(None),
            (Partido.estatus.is_(None)) | (Partido.estatus != _ESTATUS_TERMINADO),
        )
        .all()
    )

    pendientes: dict[int, dict] = {}
    capitan_cache: dict[int, Jugador | None] = {}

    for partido in partidos:
        torneo = torneos.get(partido.torneo_id)

        # Condición 2: dentro del horario permitido de registro.
        if not _registro_dentro_horario(partido, torneo, ahora_naive):
            continue

        for equipo_id in (partido.equipo_local_id, partido.equipo_visitante_id):
            if equipo_id not in capitan_cache:
                capitan_cache[equipo_id] = _capitan_de_equipo(db, equipo_id)
            capitan = capitan_cache[equipo_id]
            if not capitan:
                continue  # equipo sin capitán activo

            # Condición 1: asistencia pendiente para este capitán.
            if not _asistencia_pendiente(db, partido.id, capitan.id):
                continue

            entry = pendientes.setdefault(
                capitan.id, {"capitan": capitan, "num_partidos": 0}
            )
            entry["num_partidos"] += 1

    return pendientes


def _procesar_capitan(db, capitan, num_partidos, fecha_dia):
    """Envía UN recordatorio al capitán agrupando sus partidos pendientes."""
    if _ya_recordado_hoy(db, capitan.id, fecha_dia):
        return

    celular = capitan.celular  # via Jugador.usuario.celular
    if not celular:
        _marcar_recordatorio(
            db, capitan.id, fecha_dia, None, num_partidos,
            "error", "Capitán sin celular asociado",
        )
        logger.warning("Recordatorio omitido: capitán %s sin celular", capitan.id)
        return

    try:
        send_recordatorio_asistencia(
            celular=celular,
            nombre_capitan=capitan.nombre,
        )
        inserted = _marcar_recordatorio(
            db, capitan.id, fecha_dia, celular, num_partidos, "enviado", None
        )
        if inserted:
            registrar_evento(
                db,
                TipoEvento.RECORDATORIO_WHATSAPP,
                usuario_id=capitan.usuario_id,
                jugador_id=capitan.id,
                descripcion=(
                    f"Recordatorio de asistencia enviado a {celular} "
                    f"({num_partidos} partido(s) pendientes)"
                ),
            )
            db.commit()
        logger.info(
            "Recordatorio enviado: capitán %s (%s partidos pendientes)",
            capitan.id,
            num_partidos,
        )
    except WhatsAppError as exc:
        _marcar_recordatorio(
            db, capitan.id, fecha_dia, celular, num_partidos, "error", str(exc)[:1000]
        )
        logger.error("Fallo al enviar recordatorio (capitán %s): %s", capitan.id, exc)


def enviar_recordatorios_pendientes():
    """Job principal: agrupa partidos pendientes por capitán y envía un recordatorio a cada uno."""
    if not WHATSAPP_ENABLED:
        logger.debug("WhatsApp no configurado; se omite el job de recordatorios.")
        return

    ahora_naive = datetime.now(_TZ).replace(tzinfo=None)
    fecha_dia = ahora_naive.date()

    db = SessionLocal()
    try:
        pendientes = _recolectar_pendientes_por_capitan(db, ahora_naive)
        for entry in pendientes.values():
            _procesar_capitan(db, entry["capitan"], entry["num_partidos"], fecha_dia)
    except Exception:
        logger.exception("Error en el job de recordatorios de asistencia")
        db.rollback()
    finally:
        db.close()


def start_scheduler():
    """Arranca el scheduler si está habilitado. Idempotente."""
    global _scheduler

    if not REMINDER_ENABLED:
        logger.info("Recordatorios deshabilitados (REMINDER_ENABLED=false).")
        return
    if not WHATSAPP_ENABLED:
        logger.warning(
            "REMINDER_ENABLED=true pero WhatsApp no está configurado; el scheduler no se arranca."
        )
        return
    if not REMINDER_HOURS:
        logger.warning("REMINDER_HOURS vacío; el scheduler no se arranca.")
        return
    if _scheduler and _scheduler.running:
        return

    _ensure_table()

    # El trigger corre en la zona local (UTC-6) a las horas configuradas.
    _scheduler = BackgroundScheduler(timezone=_TZ)
    horas = ",".join(str(h) for h in REMINDER_HOURS)
    _scheduler.add_job(
        enviar_recordatorios_pendientes,
        trigger=CronTrigger(hour=horas, minute=0, timezone=_TZ),
        id="recordatorios_asistencia",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    _scheduler.start()
    logger.info(
        "Scheduler de recordatorios iniciado (horas locales: %s).",
        horas,
    )

    # Envío de prueba puntual, si está configurado (temporal).
    _programar_prueba()


def _enviar_prueba():
    """Envío de prueba (datos dummy) al número configurado. Se ejecuta una sola vez."""
    logger.info(
        "Ejecutando envío de PRUEBA a %s (nombre dummy '%s')",
        TEST_REMINDER_CELULAR,
        TEST_REMINDER_NOMBRE,
    )
    try:
        resp = send_recordatorio_asistencia(
            celular=TEST_REMINDER_CELULAR,
            nombre_capitan=TEST_REMINDER_NOMBRE,
        )
        logger.info("Envío de PRUEBA OK. Respuesta de Meta: %s", resp)
    except WhatsAppError as exc:
        logger.error("Envío de PRUEBA falló: %s", exc)


def _programar_prueba():
    """Programa el envío de prueba si TEST_REMINDER_TIME y TEST_REMINDER_CELULAR están definidos."""
    if not (TEST_REMINDER_TIME and TEST_REMINDER_CELULAR):
        return
    try:
        hh, mm = TEST_REMINDER_TIME.strip().split(":")
        hora, minuto = int(hh), int(mm)
    except (ValueError, AttributeError):
        logger.warning("TEST_REMINDER_TIME inválido (%r); formato esperado HH:MM.", TEST_REMINDER_TIME)
        return

    _scheduler.add_job(
        _enviar_prueba,
        trigger=CronTrigger(hour=hora, minute=minuto, timezone=_TZ),
        id="recordatorio_prueba",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    logger.info(
        "Envío de PRUEBA programado para las %02d:%02d (hora local) -> %s",
        hora,
        minuto,
        TEST_REMINDER_CELULAR,
    )


def stop_scheduler():
    """Detiene el scheduler si está corriendo."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("Scheduler de recordatorios detenido.")
