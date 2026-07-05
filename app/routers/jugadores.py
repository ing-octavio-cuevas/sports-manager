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
    from app.models import Usuario
    from passlib.context import CryptContext

    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    equipo = db.query(Equipo).filter(Equipo.id == jugador.equipo_id).first()
    if not equipo:
        raise HTTPException(status_code=404, detail="Equipo no encontrado")

    # Si es jugador, solo puede crear en su propio equipo
    if ROL_JUGADOR in usuario.roles and ROL_ANFITRION not in usuario.roles:
        mis_jugadores = db.query(Jugador).filter(Jugador.usuario_id == usuario.id).all()
        mis_equipos = [j.equipo_id for j in mis_jugadores]
        if jugador.equipo_id not in mis_equipos:
            raise HTTPException(status_code=403, detail="Solo puedes agregar jugadores a tu propio equipo")

    # Validar que solo haya un capitán por equipo
    if jugador.es_capitan:
        capitan_existente = db.query(Jugador).filter(
            Jugador.equipo_id == jugador.equipo_id,
            Jugador.es_capitan == True,
        ).first()
        if capitan_existente:
            raise HTTPException(status_code=400, detail="Este equipo ya tiene un capitán asignado")

    data = jugador.model_dump()
    celular = data.pop("celular", None)
    email = data.pop("email", None)

    # Tratar numero 0 como null
    if data.get("numero") == 0:
        data["numero"] = None

    db_jugador = Jugador(**data)

    # Validar nombre duplicado en el mismo equipo
    existe = db.query(Jugador).filter(
        Jugador.equipo_id == jugador.equipo_id,
        Jugador.nombre == jugador.nombre,
    ).first()
    if existe:
        raise HTTPException(status_code=400, detail="Ya existe un jugador con ese nombre en este equipo")

    # Validar número duplicado en el mismo equipo
    if jugador.numero is not None:
        existe_numero = db.query(Jugador).filter(
            Jugador.equipo_id == jugador.equipo_id,
            Jugador.numero == jugador.numero,
        ).first()
        if existe_numero:
            raise HTTPException(status_code=400, detail="Ya existe un jugador con ese número en este equipo")

    db_jugador.codigo_qr = f"JUG-{uuid.uuid4().hex[:16].upper()}"
    db.add(db_jugador)
    db.flush()

    # Si es capitán, crear o vincular usuario
    if jugador.es_capitan and celular:
        usuario_existente = db.query(Usuario).filter(Usuario.celular == celular).first()
        if usuario_existente:
            # Verificar que no tenga otro jugador en el mismo torneo
            jugadores_del_usuario = db.query(Jugador).filter(Jugador.usuario_id == usuario_existente.id).all()
            for j in jugadores_del_usuario:
                equipo_j = db.query(Equipo).filter(Equipo.id == j.equipo_id).first()
                if equipo_j and equipo_j.torneo_id == equipo.torneo_id:
                    raise HTTPException(status_code=400, detail="Este usuario ya tiene un jugador en este torneo")
            # Agregar rol jugador y actualizar email si viene
            roles_actuales = set(usuario_existente.roles)
            roles_actuales.add("jugador")
            usuario_existente.rol = ",".join(roles_actuales)
            if email:
                usuario_existente.email = email
            db_jugador.usuario_id = usuario_existente.id
        else:
            # Crear usuario nuevo
            nuevo_usuario = Usuario(
                celular=celular,
                email=email,
                password_hash=pwd_context.hash("root"),
                nombre=jugador.nombre,
                rol="jugador",
                requiere_cambio_password=True,
            )
            db.add(nuevo_usuario)
            db.flush()
            db_jugador.usuario_id = nuevo_usuario.id
    elif jugador.es_capitan and not celular:
        raise HTTPException(status_code=400, detail="Se requiere celular para asignar capitán")

    db.commit()
    db.refresh(db_jugador)
    return db_jugador


@router.get("", response_model=list[JugadorResponse])
def list_jugadores(equipo_id: int = None, torneo_id: int = None, estatus: bool = None, db: Session = Depends(get_db), usuario=Depends(require_role(ROL_ANFITRION, ROL_JUGADOR))):
    """Listar jugadores. Filtrar por equipo_id opcionalmente. Si viene torneo_id, incluye % asistencia."""
    from sqlalchemy.orm import joinedload
    from sqlalchemy import or_
    from app.models import Asistencia

    query = db.query(Jugador).options(joinedload(Jugador.usuario))

    if equipo_id:
        query = query.filter(Jugador.equipo_id == equipo_id)
    else:
        # Sin equipo_id, filtrar según rol
        if ROL_ANFITRION in usuario.roles and usuario.anfitrion_id:
            torneos_ids = [t.id for t in db.query(Torneo).filter(Torneo.anfitrion_id == usuario.anfitrion_id).all()]
            equipos_ids = [e.id for e in db.query(Equipo).filter(Equipo.torneo_id.in_(torneos_ids)).all()]
            query = query.filter(Jugador.equipo_id.in_(equipos_ids))

    if estatus is not None:
        query = query.filter(Jugador.estatus == estatus)

    jugadores = query.all()

    # Si viene torneo_id, calcular porcentaje de asistencia
    if torneo_id and equipo_id:
        # Obtener fecha_inicio_asistencias del torneo
        torneo_obj = db.query(Torneo).filter(Torneo.id == torneo_id).first()

        query_partidos = db.query(Partido).filter(
            Partido.torneo_id == torneo_id,
            Partido.estatus == "Jugado",
            Partido.tipo == "Oficial",
            or_(
                Partido.equipo_local_id == equipo_id,
                Partido.equipo_visitante_id == equipo_id,
            ),
        )
        if torneo_obj and torneo_obj.fecha_inicio_asistencias:
            query_partidos = query_partidos.filter(Partido.fecha_hora >= torneo_obj.fecha_inicio_asistencias)

        partidos_oficiales = query_partidos.all()
        total_partidos = len(partidos_oficiales)
        partido_ids = [p.id for p in partidos_oficiales]

        resultado = []
        for j in jugadores:
            asistidos = db.query(Asistencia).filter(
                Asistencia.jugador_id == j.id,
                Asistencia.partido_id.in_(partido_ids),
            ).count() if partido_ids else 0
            porcentaje = round((asistidos / total_partidos) * 100, 1) if total_partidos > 0 else 0.0

            # Construir response con campos extra
            j_dict = {
                "id": j.id, "equipo_id": j.equipo_id, "nombre": j.nombre,
                "numero": j.numero, "posicion": j.posicion, "estatus": j.estatus,
                "es_capitan": j.es_capitan, "fecha_creacion": j.fecha_creacion,
                "foto": j.foto, "curp": j.curp, "codigo_qr": j.codigo_qr,
                "usuario_id": j.usuario_id, "celular": j.celular, "email": j.email,
                "partidos_asistidos": asistidos,
                "total_partidos": total_partidos,
                "porcentaje_asistencia": porcentaje,
            }
            resultado.append(j_dict)
        return resultado

    return jugadores


@router.get("/mi-capitan", response_model=JugadorResponse)
def get_mi_capitan(db: Session = Depends(get_db), usuario=Depends(require_role(ROL_JUGADOR))):
    """Obtener el jugador capitán del usuario logueado."""
    from sqlalchemy.orm import joinedload
    capitan = db.query(Jugador).options(joinedload(Jugador.usuario)).filter(
        Jugador.usuario_id == usuario.id,
        Jugador.es_capitan == True,
    ).first()
    if not capitan:
        raise HTTPException(status_code=404, detail="No tienes un jugador capitán vinculado")
    return capitan


@router.get("/mi-informacion")
def get_mi_informacion(db: Session = Depends(get_db), usuario=Depends(require_role(ROL_JUGADOR))):
    """
    Información del jugador logueado.
    Torneos a los que está inscrito, con sus partidos.
    """
    from app.schemas import JugadorInfoCompleta, TorneoInfoJugador
    from sqlalchemy import or_
    from sqlalchemy.orm import joinedload

    jugadores = db.query(Jugador).join(Equipo, Jugador.equipo_id == Equipo.id).filter(
        Jugador.usuario_id == usuario.id,
        Equipo.estatus == True,
    ).all()
    if not jugadores:
        raise HTTPException(status_code=404, detail="No tienes jugadores vinculados")

    torneos = []
    for jugador in jugadores:
        equipo = db.query(Equipo).filter(Equipo.id == jugador.equipo_id).first()
        torneo = db.query(Torneo).filter(Torneo.id == equipo.torneo_id).first()

        torneos.append(TorneoInfoJugador(
            torneo_id=torneo.id,
            torneo_nombre=torneo.nombre,
            torneo_logo=torneo.logo,
            torneo_reglamento=torneo.reglamento,
            torneo_publicado=torneo.publicado,
            torneo_periodo=torneo.periodo,
            torneo_categoria=torneo.categoria,
            equipo_id=equipo.id,
            equipo_nombre=equipo.nombre,
            jugador_id=jugador.id,
            es_capitan=jugador.es_capitan,
            permite_edicion_jugadores=equipo.permite_edicion_jugadores,
        ))

    return JugadorInfoCompleta(
        usuario_id=usuario.id,
        nombre=usuario.nombre,
        celular=usuario.celular,
        email=usuario.email,
        torneos=torneos,
    )


@router.get("/mi-informacion/partidos")
def get_mis_partidos_paginados(torneo_id: int, page: int = 1, limit: int = 6, buscar: str = None, db: Session = Depends(get_db), usuario=Depends(require_role(ROL_JUGADOR))):
    """Partidos paginados del jugador logueado en un torneo específico."""
    from app.schemas import PartidosPaginados
    from sqlalchemy import or_
    from sqlalchemy.orm import joinedload
    import math

    # Buscar jugador del usuario en ese torneo
    jugadores = db.query(Jugador).filter(Jugador.usuario_id == usuario.id).all()
    equipo_id = None
    for j in jugadores:
        equipo = db.query(Equipo).filter(Equipo.id == j.equipo_id).first()
        if equipo and equipo.torneo_id == torneo_id:
            equipo_id = equipo.id
            break

    if not equipo_id:
        return PartidosPaginados(partidos=[], total=0, page=page, pages=0)

    # Query paginada
    query = db.query(Partido).options(joinedload(Partido.arbitrajes), joinedload(Partido.jornada)).filter(
        or_(
            Partido.equipo_local_id == equipo_id,
            Partido.equipo_visitante_id == equipo_id,
        )
    )

    # Filtro de búsqueda por nombre del equipo contrario
    if buscar:
        # Obtener IDs de equipos que coinciden con la búsqueda
        equipos_match = db.query(Equipo.id).filter(Equipo.nombre.ilike(f"%{buscar}%")).all()
        equipos_match_ids = [e.id for e in equipos_match]
        if equipos_match_ids:
            query = query.filter(
                or_(
                    Partido.equipo_local_id.in_(equipos_match_ids),
                    Partido.equipo_visitante_id.in_(equipos_match_ids),
                )
            )
        else:
            return PartidosPaginados(partidos=[], total=0, page=page, pages=0)

    query = query.order_by(Partido.fecha_hora.desc())

    total = query.count()
    pages = math.ceil(total / limit) if limit > 0 else 0
    offset = (page - 1) * limit
    partidos = query.offset(offset).limit(limit).all()

    return PartidosPaginados(
        partidos=partidos,
        total=total,
        page=page,
        pages=pages,
    )


@router.get("/{jugador_id}", response_model=JugadorResponse)
def get_jugador(jugador_id: int, db: Session = Depends(get_db), usuario=Depends(require_role(ROL_ANFITRION, ROL_JUGADOR))):
    """Obtener un jugador por ID."""
    jugador = db.query(Jugador).filter(Jugador.id == jugador_id).first()
    if not jugador:
        raise HTTPException(status_code=404, detail="Jugador no encontrado")
    # Filtro anfitrión
    if ROL_ANFITRION in usuario.roles and usuario.anfitrion_id:
        equipo = db.query(Equipo).filter(Equipo.id == jugador.equipo_id).first()
        if equipo:
            torneo = db.query(Torneo).filter(Torneo.id == equipo.torneo_id).first()
            if not torneo or torneo.anfitrion_id != usuario.anfitrion_id:
                raise HTTPException(status_code=403, detail="No tienes acceso a este recurso")
    return jugador


@router.put("/{jugador_id}", response_model=JugadorResponse)
def update_jugador(jugador_id: int, jugador_data: JugadorUpdate, db: Session = Depends(get_db), usuario=Depends(require_role(ROL_ANFITRION, ROL_JUGADOR))):
    """Actualizar un jugador. Solo se actualizan los campos enviados."""
    from app.models import Usuario
    from passlib.context import CryptContext

    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    jugador = db.query(Jugador).filter(Jugador.id == jugador_id).first()
    if not jugador:
        raise HTTPException(status_code=404, detail="Jugador no encontrado")

    # Si es jugador, solo puede editar jugadores de su propio equipo
    if ROL_JUGADOR in usuario.roles and ROL_ANFITRION not in usuario.roles:
        mis_jugadores = db.query(Jugador).filter(Jugador.usuario_id == usuario.id).all()
        mis_equipos = [j.equipo_id for j in mis_jugadores]
        if jugador.equipo_id not in mis_equipos:
            raise HTTPException(status_code=403, detail="Solo puedes editar jugadores de tu propio equipo")

    update_data = jugador_data.model_dump(exclude_unset=True)
    celular = update_data.pop("celular", None)
    email = update_data.pop("email", None)

    # Si viene es_capitan=false, ignorar celular y email
    if "es_capitan" in update_data and update_data["es_capitan"] is False:
        celular = None
        email = None

    # Numero solo se puede asignar si actualmente es null o es el mismo valor
    # A menos que el equipo tenga permite_edicion_jugadores activado
    if "numero" in update_data:
        if update_data["numero"] == 0:
            update_data["numero"] = None
        elif update_data["numero"] is not None:
            equipo_jugador = db.query(Equipo).filter(Equipo.id == jugador.equipo_id).first()
            puede_editar = equipo_jugador.permite_edicion_jugadores if equipo_jugador else False

            if not puede_editar and jugador.numero is not None and update_data["numero"] != jugador.numero:
                raise HTTPException(status_code=400, detail="El número de jugador no se puede modificar una vez asignado")
            # Validar que no exista otro con ese número en el equipo
            existe_numero = db.query(Jugador).filter(
                Jugador.equipo_id == jugador.equipo_id,
                Jugador.numero == update_data["numero"],
                Jugador.id != jugador_id,
            ).first()
            if existe_numero:
                raise HTTPException(status_code=400, detail="Ya existe un jugador con ese número en este equipo")

    # Si marcan como capitán, validar que no haya otro
    if "es_capitan" in update_data and update_data["es_capitan"] is True and not jugador.es_capitan:
        capitan_existente = db.query(Jugador).filter(
            Jugador.equipo_id == jugador.equipo_id,
            Jugador.es_capitan == True,
            Jugador.id != jugador_id,
        ).first()
        if capitan_existente:
            raise HTTPException(status_code=400, detail="Este equipo ya tiene un capitán asignado")

        if not celular:
            raise HTTPException(status_code=400, detail="Se requiere celular para asignar capitán")

        usuario_existente = db.query(Usuario).filter(Usuario.celular == celular).first()
        if usuario_existente:
            # Verificar que no tenga otro jugador en el mismo torneo
            equipo_actual = db.query(Equipo).filter(Equipo.id == jugador.equipo_id).first()
            jugadores_del_usuario = db.query(Jugador).filter(Jugador.usuario_id == usuario_existente.id).all()
            for j in jugadores_del_usuario:
                equipo_j = db.query(Equipo).filter(Equipo.id == j.equipo_id).first()
                if equipo_j and equipo_j.torneo_id == equipo_actual.torneo_id:
                    raise HTTPException(status_code=400, detail="Este usuario ya tiene un jugador en este torneo")
            # Agregar rol jugador si no lo tiene y actualizar email
            roles_actuales = set(usuario_existente.roles)
            roles_actuales.add("jugador")
            usuario_existente.rol = ",".join(roles_actuales)
            if email:
                usuario_existente.email = email
            jugador.usuario_id = usuario_existente.id
        else:
            # Crear usuario nuevo con password temporal
            nuevo_usuario = Usuario(
                celular=celular,
                email=email,
                password_hash=pwd_context.hash("root"),
                nombre=jugador.nombre,
                rol="jugador",
                requiere_cambio_password=True,
            )
            db.add(nuevo_usuario)
            db.flush()
            jugador.usuario_id = nuevo_usuario.id

    # Si deja de ser capitán, quitar rol jugador o eliminar usuario
    if "es_capitan" in update_data and update_data["es_capitan"] is False and jugador.es_capitan:
        if jugador.usuario_id:
            usuario_jugador = db.query(Usuario).filter(Usuario.id == jugador.usuario_id).first()
            if usuario_jugador:
                roles_actuales = set(usuario_jugador.roles)
                roles_actuales.discard("jugador")
                if roles_actuales:
                    usuario_jugador.rol = ",".join(roles_actuales)
                else:
                    db.delete(usuario_jugador)
            jugador.usuario_id = None

    # Si viene email o celular y el jugador ya tiene usuario, actualizar
    if jugador.usuario_id:
        usuario_jugador = db.query(Usuario).filter(Usuario.id == jugador.usuario_id).first()
        if usuario_jugador:
            if email:
                usuario_jugador.email = email
            if celular:
                usuario_jugador.celular = celular

    for field, value in update_data.items():
        setattr(jugador, field, value)
    db.commit()
    db.refresh(jugador)
    return jugador


@router.delete("/{jugador_id}", status_code=204)
def delete_jugador(jugador_id: int, db: Session = Depends(get_db), usuario=Depends(require_role(ROL_ANFITRION, ROL_JUGADOR))):
    """Elimina el jugador si no tiene asistencias, sino soft delete."""
    from app.models import Asistencia

    jugador = db.query(Jugador).filter(Jugador.id == jugador_id).first()
    if not jugador:
        raise HTTPException(status_code=404, detail="Jugador no encontrado")

    tiene_asistencias = db.query(Asistencia).filter(Asistencia.jugador_id == jugador_id).first()
    if tiene_asistencias:
        from datetime import datetime
        jugador.estatus = False
        jugador.fecha_baja = datetime.utcnow()
        db.commit()
    else:
        # Eliminar foto de S3 si existe
        if jugador.foto and S3_URL_BASE and S3_URL_BASE in jugador.foto:
            import boto3
            from app.config import S3_BUCKET, S3_REGION
            try:
                s3 = boto3.client("s3", region_name=S3_REGION)
                old_key = jugador.foto.replace(f"{S3_URL_BASE}/", "")
                s3.delete_object(Bucket=S3_BUCKET, Key=old_key)
            except Exception:
                pass
        db.delete(jugador)
        db.commit()


# ─── Upload de foto ──────────────────────────────────────────

import boto3
from app.config import S3_BUCKET, S3_REGION, S3_URL_BASE


@router.post("/{jugador_id}/foto", response_model=JugadorResponse)
def upload_foto(jugador_id: int, foto: UploadFile = File(...), db: Session = Depends(get_db), usuario=Depends(require_role(ROL_ANFITRION, ROL_JUGADOR))):
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
