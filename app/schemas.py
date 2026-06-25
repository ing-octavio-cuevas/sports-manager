"""
Schemas Pydantic para validación de entrada/salida.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


# ─── Anfitrion ───────────────────────────────────────────────

class AnfitrionCreate(BaseModel):
    nombre_completo: str
    estatus: Optional[bool] = True


class AnfitrionResponse(BaseModel):
    id: int
    nombre_completo: str
    estatus: bool

    model_config = {"from_attributes": True}


# ─── Torneo Ubicaciones ─────────────────────────────────────

class TorneoUbicacionCreate(BaseModel):
    nombre: Optional[str] = None
    ubicacion: Optional[str] = None
    direccion: Optional[str] = None


class TorneoUbicacionUpdate(BaseModel):
    nombre: Optional[str] = None
    ubicacion: Optional[str] = None
    direccion: Optional[str] = None


class TorneoUbicacionResponse(BaseModel):
    id: int
    torneo_id: int
    nombre: Optional[str]
    ubicacion: Optional[str]
    direccion: Optional[str]

    model_config = {"from_attributes": True}


# ─── Torneo ──────────────────────────────────────────────────

class TorneoCreate(BaseModel):
    nombre: str
    reglamento: Optional[str] = None
    logo: Optional[str] = None
    publicado: Optional[bool] = True
    periodo: Optional[str] = None
    categoria: Optional[str] = None
    anfitrion_id: int
    numero_vueltas: Optional[int] = 2


class TorneoUpdate(BaseModel):
    nombre: Optional[str] = None
    reglamento: Optional[str] = None
    logo: Optional[str] = None
    publicado: Optional[bool] = None
    periodo: Optional[str] = None
    categoria: Optional[str] = None
    anfitrion_id: Optional[int] = None
    numero_vueltas: Optional[int] = None


class TorneoResponse(BaseModel):
    id: int
    nombre: str
    reglamento: Optional[str]
    logo: Optional[str]
    fecha_creacion: Optional[datetime]
    publicado: bool
    periodo: Optional[str]
    categoria: Optional[str]
    anfitrion_id: int
    numero_vueltas: Optional[int]
    anfitrion: AnfitrionResponse
    ubicaciones: list[TorneoUbicacionResponse] = []

    model_config = {"from_attributes": True}


# ─── Equipo ──────────────────────────────────────────────────

class EquipoCreate(BaseModel):
    torneo_id: int
    nombre: str
    logo: Optional[str] = None
    estatus: Optional[bool] = True
    inscripcion_pagada: Optional[bool] = False
    monto_pagado: Optional[float] = None
    fecha_pago_inscripcion: Optional[datetime] = None


class EquipoUpdate(BaseModel):
    nombre: Optional[str] = None
    logo: Optional[str] = None
    estatus: Optional[bool] = None
    inscripcion_pagada: Optional[bool] = None
    monto_pagado: Optional[float] = None
    fecha_pago_inscripcion: Optional[datetime] = None


class EquipoResponse(BaseModel):
    id: int
    torneo_id: int
    nombre: str
    logo: Optional[str]
    fecha_creacion: Optional[datetime]
    estatus: bool
    inscripcion_pagada: bool
    monto_pagado: Optional[float]
    fecha_pago_inscripcion: Optional[datetime]

    model_config = {"from_attributes": True}


# ─── Jugador ─────────────────────────────────────────────────

class JugadorCreate(BaseModel):
    equipo_id: int
    nombre: str
    numero: Optional[int] = None
    posicion: Optional[str] = None
    estatus: Optional[bool] = True
    es_capitan: Optional[bool] = False
    celular: Optional[str] = None
    email: Optional[str] = None
    foto: Optional[str] = None
    curp: Optional[str] = None


class JugadorUpdate(BaseModel):
    nombre: Optional[str] = None
    numero: Optional[int] = None
    posicion: Optional[str] = None
    estatus: Optional[bool] = None
    es_capitan: Optional[bool] = None
    celular: Optional[str] = None
    email: Optional[str] = None
    foto: Optional[str] = None
    curp: Optional[str] = None


class JugadorResponse(BaseModel):
    id: int
    equipo_id: int
    nombre: str
    numero: Optional[int]
    posicion: Optional[str]
    estatus: bool
    es_capitan: bool
    fecha_creacion: Optional[datetime]
    foto: Optional[str]
    curp: Optional[str]
    codigo_qr: str
    usuario_id: Optional[int] = None
    celular: Optional[str] = None
    email: Optional[str] = None

    model_config = {"from_attributes": True}


# ─── Jornada ─────────────────────────────────────────────────

class JornadaCreate(BaseModel):
    torneo_id: int
    numero: int
    fecha: Optional[datetime] = None
    estatus: Optional[bool] = True


class JornadaUpdate(BaseModel):
    numero: Optional[int] = None
    fecha: Optional[datetime] = None
    estatus: Optional[bool] = None


class JornadaResponse(BaseModel):
    id: int
    torneo_id: int
    numero: int
    fecha: Optional[datetime]
    estatus: bool

    model_config = {"from_attributes": True}


# ─── Partido ─────────────────────────────────────────────────

class PartidoSetCreate(BaseModel):
    numero_set: int
    marcador_local: Optional[int] = 0
    marcador_visitante: Optional[int] = 0
    puntos_local: Optional[int] = 0
    puntos_visitante: Optional[int] = 0


class PartidoSetUpdate(BaseModel):
    marcador_local: Optional[int] = None
    marcador_visitante: Optional[int] = None
    puntos_local: Optional[int] = None
    puntos_visitante: Optional[int] = None


class PartidoSetResponse(BaseModel):
    id: int
    partido_id: int
    numero_set: int
    marcador_local: int
    marcador_visitante: int
    puntos_local: int
    puntos_visitante: int

    model_config = {"from_attributes": True}


class PartidoCreate(BaseModel):
    torneo_id: int
    jornada_id: int
    equipo_local_id: int
    equipo_visitante_id: int
    puntos_local: Optional[int] = 0
    puntos_visitante: Optional[int] = 0
    ubicacion_id: Optional[int] = None
    fecha_hora: Optional[datetime] = None
    estatus: Optional[str] = None
    tipo: Optional[str] = None
    observaciones: Optional[str] = None


class PartidoUpdate(BaseModel):
    jornada_id: Optional[int] = None
    equipo_local_id: Optional[int] = None
    equipo_visitante_id: Optional[int] = None
    puntos_local: Optional[int] = None
    puntos_visitante: Optional[int] = None
    ubicacion_id: Optional[int] = None
    fecha_hora: Optional[datetime] = None
    estatus: Optional[str] = None
    tipo: Optional[str] = None
    observaciones: Optional[str] = None


class PartidoResponse(BaseModel):
    id: int
    torneo_id: int
    jornada_id: int
    equipo_local_id: int
    equipo_visitante_id: int
    puntos_local: int
    puntos_visitante: int
    ubicacion_id: Optional[int]
    fecha_hora: Optional[datetime]
    estatus: Optional[str]
    tipo: Optional[str]
    observaciones: Optional[str]
    sets: list["PartidoSetResponse"] = []
    arbitrajes: list["PartidoArbitrajeResponse"] = []

    model_config = {"from_attributes": True}


# ─── Partido Arbitraje ───────────────────────────────────────

class PartidoArbitrajeCreate(BaseModel):
    partido_id: int
    equipo_id: int
    pagado: Optional[bool] = False
    monto: Optional[float] = None
    fecha_pago: Optional[datetime] = None
    observaciones: Optional[str] = None


class PartidoArbitrajeUpdate(BaseModel):
    pagado: Optional[bool] = None
    monto: Optional[float] = None
    fecha_pago: Optional[datetime] = None
    observaciones: Optional[str] = None


class PartidoArbitrajeResponse(BaseModel):
    id: int
    partido_id: int
    equipo_id: int
    pagado: bool
    monto: Optional[float]
    fecha_pago: Optional[datetime]
    observaciones: Optional[str]

    model_config = {"from_attributes": True}


# ─── Combinaciones de partidos pendientes ────────────────────

class CombinacionPartido(BaseModel):
    equipo_local_id: int
    equipo_local_nombre: str
    equipo_visitante_id: int
    equipo_visitante_nombre: str


# ─── Tabla de posiciones ─────────────────────────────────────

class AdeudoEquipo(BaseModel):
    partido_id: int
    rival: str
    monto: Optional[float]
    fecha_partido: Optional[datetime]


class PosicionEquipo(BaseModel):
    equipo_id: int
    equipo_nombre: str
    equipo_logo: Optional[str] = None
    pj: int = 0   # Partidos jugados
    pg: int = 0   # Partidos ganados
    pp: int = 0   # Partidos perdidos
    sg: int = 0   # Sets ganados
    sp: int = 0   # Sets perdidos
    pts: int = 0  # Puntos
    inscripcion_pagada: bool = False
    monto_pagado: Optional[float] = None
    adeudos: list[AdeudoEquipo] = []


# ─── Asistencia ──────────────────────────────────────────────

class AsistenciaCreate(BaseModel):
    partido_id: int
    jugador_ids: list[int]


class AsistenciaResponse(BaseModel):
    id: int
    partido_id: int
    jugador_id: int
    registrado_por: int
    metodo: str
    hora_registro: Optional[datetime]
    jugador_nombre: Optional[str] = None
    jugador_numero: Optional[int] = None
    jugador_foto: Optional[str] = None

    model_config = {"from_attributes": True}


class PartidoCapitanResponse(BaseModel):
    """Partidos disponibles para que el capitán registre asistencia."""
    id: int
    torneo_id: int
    torneo_nombre: Optional[str] = None
    jornada_id: int
    jornada_numero: Optional[int] = None
    jornada_fecha: Optional[datetime] = None
    equipo_local_id: int
    equipo_visitante_id: int
    estatus: Optional[str]
    tipo: Optional[str]
    ubicacion_id: Optional[int]
    ubicacion_nombre: Optional[str] = None
    ubicacion_direccion: Optional[str] = None
    ubicacion_url: Optional[str] = None
    fecha_hora: Optional[datetime]
    es_hoy: bool = False
    caducado: bool = False
    asistencia_registrada: bool = False

    model_config = {"from_attributes": True}


# ─── Usuario ─────────────────────────────────────────────────

class UsuarioCreate(BaseModel):
    celular: str
    email: Optional[str] = None
    password: str
    nombre: str
    roles: list[str]
    jugador_id: Optional[int] = None
    anfitrion_id: Optional[int] = None


class UsuarioUpdate(BaseModel):
    celular: Optional[str] = None
    email: Optional[str] = None
    nombre: Optional[str] = None
    roles: Optional[list[str]] = None
    estatus: Optional[bool] = None
    anfitrion_id: Optional[int] = None


class UsuarioResponse(BaseModel):
    id: int
    celular: str
    email: Optional[str]
    nombre: str
    roles: list[str]
    estatus: bool
    requiere_cambio_password: bool
    anfitrion_id: Optional[int]
    fecha_creacion: Optional[datetime]

    model_config = {"from_attributes": True}


class CambiarPassword(BaseModel):
    password_actual: str
    password_nueva: str


# ─── Auth ────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    celular: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    usuario: UsuarioResponse


# ─── Información completa del jugador (vista portal) ─────────

class PartidoArbitrajeInfo(BaseModel):
    id: int
    partido_id: int
    equipo_id: int
    pagado: bool
    monto: Optional[float]
    fecha_pago: Optional[datetime]
    observaciones: Optional[str]

    model_config = {"from_attributes": True}


class PartidoInfoJugador(BaseModel):
    id: int
    jornada_id: int
    equipo_local_id: int
    equipo_visitante_id: int
    puntos_local: int
    puntos_visitante: int
    ubicacion_id: Optional[int]
    fecha_hora: Optional[datetime]
    estatus: Optional[str]
    tipo: Optional[str]
    arbitrajes: list[PartidoArbitrajeInfo] = []

    model_config = {"from_attributes": True}


class TorneoInfoJugador(BaseModel):
    torneo_id: int
    torneo_nombre: str
    torneo_logo: Optional[str] = None
    torneo_reglamento: Optional[str] = None
    torneo_publicado: bool = True
    equipo_id: int
    equipo_nombre: str
    jugador_id: int
    es_capitan: bool
    partidos: list[PartidoInfoJugador] = []


class JugadorInfoCompleta(BaseModel):
    usuario_id: int
    nombre: str
    celular: str
    email: Optional[str] = None
    torneos: list[TorneoInfoJugador] = []


# ─── Estado de asistencia de un partido ──────────────────────

class EstadoAsistenciaPartido(BaseModel):
    partido_id: int
    equipo_local_id: int
    equipo_visitante_id: int
    asistencia_local_completada: bool
    asistencia_visitante_completada: bool
    registrado_por_local: Optional[int] = None
    registrado_por_visitante: Optional[int] = None


# ─── Resumen de asistencia por equipo ────────────────────────

class AsistenciaResumenJugador(BaseModel):
    jugador_id: int
    jugador_nombre: str
    jugador_numero: Optional[int]
    es_capitan: bool
    partidos_asistidos: int
    total_partidos: int
    porcentaje_asistencia: float


class AsistenciaResumenEquipo(BaseModel):
    equipo_id: int
    equipo_nombre: str
    torneo_id: int
    total_partidos: int
    jugadores: list[AsistenciaResumenJugador] = []


# ─── Resumen completo de torneo ──────────────────────────────

class TorneoResumenInfo(BaseModel):
    id: int
    nombre: str
    periodo: Optional[str]
    categoria: Optional[str]
    logo: Optional[str]


class JugadorAsistenciaInfo(BaseModel):
    jugador_id: int
    nombre: str
    numero: Optional[int]
    foto: Optional[str]
    hora_registro: Optional[datetime] = None
    manual: bool = False


class AsistenciaResumenPartido(BaseModel):
    partido_id: int
    jornada_numero: Optional[int] = None
    fecha: Optional[datetime]
    rival: str
    jugadores_presentes: list[JugadorAsistenciaInfo] = []
    total_jugadores: int


class EquipoResumenCompleto(BaseModel):
    id: int
    nombre: str
    logo: Optional[str]
    jugadores: list[JugadorResponse] = []
    ultimas_asistencias: list[AsistenciaResumenPartido] = []


class TorneoResumenCompleto(BaseModel):
    torneo: TorneoResumenInfo
    tabla_posiciones: list[PosicionEquipo] = []
    equipos: list[EquipoResumenCompleto] = []


# ─── Asistencia manual por anfitrión ────────────────────────

class AsistenciaManualCreate(BaseModel):
    partido_id: int
    equipo_id: int
    jugador_ids: list[int]
