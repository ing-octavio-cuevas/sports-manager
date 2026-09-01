from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
import math

from app.database import get_db
from app.models import EventoAuditoria, Usuario
from app.schemas import EventoAuditoriaResponse, EventosAuditoriaPaginados
from app.auth import require_role
from app.config import ROL_ANFITRION

router = APIRouter(prefix="/auditoria", tags=["Auditoría"])


@router.get("/eventos", response_model=EventosAuditoriaPaginados)
def list_eventos(
    tipo_evento: Optional[str] = None,
    usuario_id: Optional[int] = None,
    partido_id: Optional[int] = None,
    equipo_id: Optional[int] = None,
    page: int = 1,
    limit: int = 50,
    db: Session = Depends(get_db),
    usuario=Depends(require_role(ROL_ANFITRION)),
):
    """
    Listar eventos de auditoría con filtros opcionales.
    Filtros: tipo_evento, usuario_id, partido_id, equipo_id.
    Ordenados por fecha descendente. Paginado.
    """
    query = db.query(EventoAuditoria)

    if tipo_evento:
        query = query.filter(EventoAuditoria.tipo_evento == tipo_evento)
    if usuario_id:
        query = query.filter(EventoAuditoria.usuario_id == usuario_id)
    if partido_id:
        query = query.filter(EventoAuditoria.partido_id == partido_id)
    if equipo_id:
        query = query.filter(EventoAuditoria.equipo_id == equipo_id)

    total = query.count()
    pages = math.ceil(total / limit) if limit > 0 else 0
    offset = (page - 1) * limit

    eventos = query.order_by(EventoAuditoria.fecha.desc()).offset(offset).limit(limit).all()

    # Resolver nombre de usuario
    resultado = []
    for e in eventos:
        usuario_nombre = None
        if e.usuario_id:
            u = db.query(Usuario).filter(Usuario.id == e.usuario_id).first()
            usuario_nombre = u.nombre if u else None
        resultado.append(EventoAuditoriaResponse(
            id=e.id,
            tipo_evento=e.tipo_evento,
            usuario_id=e.usuario_id,
            usuario_nombre=usuario_nombre,
            partido_id=e.partido_id,
            equipo_id=e.equipo_id,
            jugador_id=e.jugador_id,
            descripcion=e.descripcion,
            detalle=e.detalle,
            ip=e.ip,
            fecha=e.fecha,
        ))

    return EventosAuditoriaPaginados(
        eventos=resultado,
        total=total,
        page=page,
        pages=pages,
    )
