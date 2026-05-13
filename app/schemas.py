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
    foto: Optional[str] = None
    curp: Optional[str] = None


class JugadorUpdate(BaseModel):
    nombre: Optional[str] = None
    numero: Optional[int] = None
    posicion: Optional[str] = None
    estatus: Optional[bool] = None
    es_capitan: Optional[bool] = None
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
    estatus: Optional[str]
    tipo: Optional[str]
    observaciones: Optional[str]
    sets: list["PartidoSetResponse"] = []

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

class PosicionEquipo(BaseModel):
    equipo_id: int
    equipo_nombre: str
    pj: int = 0   # Partidos jugados
    pg: int = 0   # Partidos ganados
    pp: int = 0   # Partidos perdidos
    sg: int = 0   # Sets ganados
    sp: int = 0   # Sets perdidos
    pts: int = 0  # Puntos


# ─── Asistencia ──────────────────────────────────────────────

class AsistenciaCreate(BaseModel):
    partido_id: int
    jugador_ids: list[int]
    registrado_por: int  # ID del capitán


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
    jornada_id: int
    equipo_local_id: int
    equipo_visitante_id: int
    estatus: Optional[str]
    tipo: Optional[str]
    ubicacion_id: Optional[int]

    model_config = {"from_attributes": True}


# ─── Usuario ─────────────────────────────────────────────────

class UsuarioCreate(BaseModel):
    email: str
    password: str
    nombre: str
    roles: list[str]  # ["anfitrion", "arbitro", "jugador"]
    jugador_id: Optional[int] = None  # ID del jugador a vincular (si es rol jugador)
    anfitrion_id: Optional[int] = None


class UsuarioUpdate(BaseModel):
    email: Optional[str] = None
    nombre: Optional[str] = None
    roles: Optional[list[str]] = None
    estatus: Optional[bool] = None
    anfitrion_id: Optional[int] = None


class UsuarioResponse(BaseModel):
    id: int
    email: str
    nombre: str
    roles: list[str]
    estatus: bool
    anfitrion_id: Optional[int]
    fecha_creacion: Optional[datetime]

    model_config = {"from_attributes": True}


class CambiarPassword(BaseModel):
    password_actual: str
    password_nueva: str


# ─── Auth ────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    usuario: UsuarioResponse


# ─── Información completa del jugador (vista portal) ─────────

class PartidoInfoJugador(BaseModel):
    id: int
    jornada_id: int
    equipo_local_id: int
    equipo_visitante_id: int
    puntos_local: int
    puntos_visitante: int
    ubicacion_id: Optional[int]
    estatus: Optional[str]
    tipo: Optional[str]

    model_config = {"from_attributes": True}


class TorneoInfoJugador(BaseModel):
    torneo_id: int
    torneo_nombre: str
    equipo_id: int
    equipo_nombre: str
    jugador_id: int
    es_capitan: bool
    partidos: list[PartidoInfoJugador] = []


class JugadorInfoCompleta(BaseModel):
    usuario_id: int
    nombre: str
    email: str
    torneos: list[TorneoInfoJugador] = []
