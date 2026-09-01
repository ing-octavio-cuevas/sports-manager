"""
Utilidades para el registro de eventos de auditoría.

Uso:
    from app.audit import registrar_evento, TipoEvento
    registrar_evento(db, TipoEvento.LOGIN, usuario_id=usuario.id, descripcion="Inicio de sesión")

El helper hace flush pero NO commit: se persiste junto con el commit de la
operación de negocio. Nunca debe romper el flujo principal, por eso captura
cualquier excepción.
"""

from typing import Optional

from sqlalchemy.orm import Session

from app.models import EventoAuditoria


class TipoEvento:
    LOGIN = "LOGIN"
    ASISTENCIA_REGISTRO = "ASISTENCIA_REGISTRO"
    ASISTENCIA_MODIFICACION = "ASISTENCIA_MODIFICACION"
    ASISTENCIA_ELIMINACION = "ASISTENCIA_ELIMINACION"
    SCORE_MODIFICACION = "SCORE_MODIFICACION"


def registrar_evento(
    db: Session,
    tipo_evento: str,
    usuario_id: Optional[int] = None,
    partido_id: Optional[int] = None,
    equipo_id: Optional[int] = None,
    jugador_id: Optional[int] = None,
    descripcion: Optional[str] = None,
    detalle: Optional[dict] = None,
    ip: Optional[str] = None,
) -> Optional[EventoAuditoria]:
    """Crea un evento de auditoría. No hace commit (se persiste con la transacción actual)."""
    try:
        evento = EventoAuditoria(
            tipo_evento=tipo_evento,
            usuario_id=usuario_id,
            partido_id=partido_id,
            equipo_id=equipo_id,
            jugador_id=jugador_id,
            descripcion=descripcion,
            detalle=detalle,
            ip=ip,
        )
        db.add(evento)
        db.flush()
        return evento
    except Exception:
        # La auditoría nunca debe tumbar la operación de negocio
        return None
