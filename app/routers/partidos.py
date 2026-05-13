from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Partido, PartidoArbitraje
from app.schemas import PartidoCreate, PartidoUpdate, PartidoResponse
from app.auth import require_role
from app.config import ROL_ANFITRION, ROL_JUGADOR

router = APIRouter(prefix="/partidos", tags=["Partidos"])


@router.post("", response_model=PartidoResponse, status_code=201)
def create_partido(partido: PartidoCreate, db: Session = Depends(get_db), usuario=Depends(require_role(ROL_ANFITRION))):
    """Crear un nuevo partido con sus registros de arbitraje para cada equipo."""
    if partido.equipo_local_id == partido.equipo_visitante_id:
        raise HTTPException(status_code=400, detail="Un equipo no puede jugar contra sí mismo")
    db_partido = Partido(**partido.model_dump())
    db.add(db_partido)
    db.flush()  # Obtener el id del partido sin hacer commit

    # Crear arbitraje para equipo local y visitante
    for equipo_id in [partido.equipo_local_id, partido.equipo_visitante_id]:
        arbitraje = PartidoArbitraje(partido_id=db_partido.id, equipo_id=equipo_id)
        db.add(arbitraje)

    db.commit()
    db.refresh(db_partido)
    return db_partido


@router.get("", response_model=list[PartidoResponse])
def list_partidos(
    torneo_id: int = None,
    jornada_id: int = None,
    db: Session = Depends(get_db),
    usuario=Depends(require_role(ROL_ANFITRION)),
):
    """Listar partidos. Filtrar por torneo_id y/o jornada_id."""
    query = db.query(Partido)
    if torneo_id:
        query = query.filter(Partido.torneo_id == torneo_id)
    if jornada_id:
        query = query.filter(Partido.jornada_id == jornada_id)
    return query.all()


@router.get("/{partido_id}", response_model=PartidoResponse)
def get_partido(partido_id: int, db: Session = Depends(get_db), usuario=Depends(require_role(ROL_ANFITRION))):
    """Obtener un partido por ID."""
    partido = db.query(Partido).filter(Partido.id == partido_id).first()
    if not partido:
        raise HTTPException(status_code=404, detail="Partido no encontrado")
    return partido


@router.put("/{partido_id}", response_model=PartidoResponse)
def update_partido(partido_id: int, partido_data: PartidoUpdate, db: Session = Depends(get_db), usuario=Depends(require_role(ROL_ANFITRION))):
    """Actualizar un partido. Solo se actualizan los campos enviados."""
    partido = db.query(Partido).filter(Partido.id == partido_id).first()
    if not partido:
        raise HTTPException(status_code=404, detail="Partido no encontrado")
    data = partido_data.model_dump(exclude_unset=True)
    # Validar que no juegue contra sí mismo si se cambian equipos
    local = data.get("equipo_local_id", partido.equipo_local_id)
    visitante = data.get("equipo_visitante_id", partido.equipo_visitante_id)
    if local == visitante:
        raise HTTPException(status_code=400, detail="Un equipo no puede jugar contra sí mismo")
    for field, value in data.items():
        setattr(partido, field, value)
    db.commit()
    db.refresh(partido)
    return partido


@router.delete("/{partido_id}", status_code=204)
def delete_partido(partido_id: int, db: Session = Depends(get_db), usuario=Depends(require_role(ROL_ANFITRION))):
    """Eliminar un partido."""
    partido = db.query(Partido).filter(Partido.id == partido_id).first()
    if not partido:
        raise HTTPException(status_code=404, detail="Partido no encontrado")
    db.delete(partido)
    db.commit()


# ─── Combinaciones pendientes ────────────────────────────────

from itertools import combinations
from app.models import Equipo, Torneo
from app.schemas import CombinacionPartido


@router.get("/torneo/{torneo_id}/combinaciones-pendientes", response_model=list[CombinacionPartido])
def get_combinaciones_pendientes(torneo_id: int, vueltas: int = 2, db: Session = Depends(get_db), usuario=Depends(require_role(ROL_ANFITRION))):
    """
    Obtener todas las combinaciones de partidos pendientes para un torneo.

    - vueltas: número de veces que cada par de equipos debe enfrentarse (default 2).
    - A 1 vuelta: A vs B cuenta como 1 enfrentamiento (sin importar quién fue local).
    - A 2 vueltas: A vs B debe jugarse 2 veces (ida y vuelta).
    - Descuenta los partidos ya existentes.
    """
    # Verificar torneo
    torneo = db.query(Torneo).filter(Torneo.id == torneo_id).first()
    if not torneo:
        raise HTTPException(status_code=404, detail="Torneo no encontrado")

    # Obtener equipos activos del torneo
    equipos = db.query(Equipo).filter(
        Equipo.torneo_id == torneo_id,
        Equipo.estatus == True,
    ).all()

    if len(equipos) < 2:
        return []

    # Obtener partidos ya creados en este torneo (solo tipo Oficial)
    partidos_existentes = db.query(Partido).filter(
        Partido.torneo_id == torneo_id,
        Partido.tipo == "Oficial",
    ).all()

    # Contar enfrentamientos entre cada par (sin importar quién fue local/visitante)
    conteo = {}
    for p in partidos_existentes:
        # Normalizar el par: siempre el menor id primero
        key = (min(p.equipo_local_id, p.equipo_visitante_id), max(p.equipo_local_id, p.equipo_visitante_id))
        conteo[key] = conteo.get(key, 0) + 1

    # Generar combinaciones pendientes
    pendientes = []
    for equipo_a, equipo_b in combinations(equipos, 2):
        key = (min(equipo_a.id, equipo_b.id), max(equipo_a.id, equipo_b.id))
        veces_jugado = conteo.get(key, 0)
        veces_pendientes = vueltas - veces_jugado
        for _ in range(veces_pendientes):
            pendientes.append(CombinacionPartido(
                equipo_local_id=equipo_a.id,
                equipo_local_nombre=equipo_a.nombre,
                equipo_visitante_id=equipo_b.id,
                equipo_visitante_nombre=equipo_b.nombre,
            ))

    return pendientes


# ─── Tabla de posiciones ─────────────────────────────────────

from app.models import PartidoSet
from app.schemas import PosicionEquipo


@router.get("/torneo/{torneo_id}/tabla-posiciones", response_model=list[PosicionEquipo])
def get_tabla_posiciones(torneo_id: int, db: Session = Depends(get_db), usuario=Depends(require_role(ROL_ANFITRION, ROL_JUGADOR))):
    """
    Tabla de posiciones de un torneo.
    Solo considera partidos con estatus 'Jugado'.
    PJ, PG, PP, SG, SP, Pts.
    Puntos se toman del campo puntos_local/puntos_visitante de cada partido.
    """
    torneo = db.query(Torneo).filter(Torneo.id == torneo_id).first()
    if not torneo:
        raise HTTPException(status_code=404, detail="Torneo no encontrado")

    # Equipos del torneo
    equipos = db.query(Equipo).filter(Equipo.torneo_id == torneo_id).all()
    if not equipos:
        return []

    # Partidos jugados del torneo
    partidos = db.query(Partido).filter(
        Partido.torneo_id == torneo_id,
        Partido.estatus == "Jugado",
    ).all()

    # Inicializar stats por equipo
    stats = {}
    for equipo in equipos:
        stats[equipo.id] = {
            "equipo_id": equipo.id,
            "equipo_nombre": equipo.nombre,
            "pj": 0,
            "pg": 0,
            "pp": 0,
            "sg": 0,
            "sp": 0,
            "pts": 0,
        }

    for partido in partidos:
        local_id = partido.equipo_local_id
        visitante_id = partido.equipo_visitante_id

        if local_id not in stats or visitante_id not in stats:
            continue

        # Partidos jugados
        stats[local_id]["pj"] += 1
        stats[visitante_id]["pj"] += 1

        # Puntos (del campo en partido)
        stats[local_id]["pts"] += partido.puntos_local or 0
        stats[visitante_id]["pts"] += partido.puntos_visitante or 0

        # Sets del partido
        sets = db.query(PartidoSet).filter(PartidoSet.partido_id == partido.id).all()
        sets_local = 0
        sets_visitante = 0
        for s in sets:
            if s.marcador_local > s.marcador_visitante:
                sets_local += 1
            elif s.marcador_visitante > s.marcador_local:
                sets_visitante += 1

        stats[local_id]["sg"] += sets_local
        stats[local_id]["sp"] += sets_visitante
        stats[visitante_id]["sg"] += sets_visitante
        stats[visitante_id]["sp"] += sets_local

        # Ganador/perdedor (por sets ganados)
        if sets_local > sets_visitante:
            stats[local_id]["pg"] += 1
            stats[visitante_id]["pp"] += 1
        elif sets_visitante > sets_local:
            stats[visitante_id]["pg"] += 1
            stats[local_id]["pp"] += 1

    # Ordenar por puntos desc, luego por sets ganados desc
    tabla = sorted(stats.values(), key=lambda x: (-x["pts"], -x["sg"]))
    return [PosicionEquipo(**row) for row in tabla]
