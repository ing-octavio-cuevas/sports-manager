"""
Modelos SQLAlchemy basados en los scripts SQL proporcionados.
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Date, ForeignKey, Numeric, UniqueConstraint, CheckConstraint, func
from sqlalchemy.orm import relationship

from app.database import Base


class Anfitrion(Base):
    __tablename__ = "anfitrion"

    id = Column(Integer, primary_key=True, index=True)
    nombre_completo = Column(String(500), nullable=False)
    estatus = Column(Boolean, default=True)

    # Relación inversa
    torneos = relationship("Torneo", back_populates="anfitrion")


class Torneo(Base):
    __tablename__ = "torneo"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(500), nullable=False)
    reglamento = Column(String(500), nullable=True)
    logo = Column(String(500), nullable=True)
    fecha_creacion = Column(DateTime, server_default=func.now())
    publicado = Column(Boolean, default=True)
    periodo = Column(String(500), nullable=True)
    categoria = Column(String(500), nullable=True)
    anfitrion_id = Column(Integer, ForeignKey("anfitrion.id"), nullable=False)
    numero_vueltas = Column(Integer, default=2)

    # Relaciones
    anfitrion = relationship("Anfitrion", back_populates="torneos")
    ubicaciones = relationship("TorneoUbicacion", back_populates="torneo")
    equipos = relationship("Equipo", back_populates="torneo", cascade="all, delete-orphan")
    jornadas = relationship("Jornada", back_populates="torneo")
    partidos = relationship("Partido", back_populates="torneo")


class TorneoUbicacion(Base):
    __tablename__ = "torneo_ubicaciones"

    id = Column(Integer, primary_key=True, index=True)
    torneo_id = Column(Integer, ForeignKey("torneo.id"), nullable=False)
    nombre = Column(String(500), nullable=True)
    ubicacion = Column(String(500), nullable=True)
    direccion = Column(String(500), nullable=True)

    # Relación inversa
    torneo = relationship("Torneo", back_populates="ubicaciones")


class Equipo(Base):
    __tablename__ = "equipo"

    id = Column(Integer, primary_key=True, index=True)
    torneo_id = Column(Integer, ForeignKey("torneo.id", ondelete="CASCADE"), nullable=False)
    nombre = Column(String(500), nullable=False)
    logo = Column(String(500), nullable=True)
    fecha_creacion = Column(DateTime, server_default=func.now())
    estatus = Column(Boolean, default=True)
    inscripcion_pagada = Column(Boolean, default=False)
    monto_pagado = Column(Numeric(10, 2), nullable=True)
    fecha_pago_inscripcion = Column(DateTime, nullable=True)

    # Relación
    torneo = relationship("Torneo", back_populates="equipos")
    jugadores = relationship("Jugador", back_populates="equipo")


class Jugador(Base):
    __tablename__ = "jugador"

    id = Column(Integer, primary_key=True, index=True)
    equipo_id = Column(Integer, ForeignKey("equipo.id"), nullable=False)
    nombre = Column(String(255), nullable=False)
    numero = Column(Integer, nullable=True)
    posicion = Column(String(100), nullable=True)
    estatus = Column(Boolean, default=True)
    es_capitan = Column(Boolean, default=False)
    fecha_creacion = Column(DateTime, server_default=func.now())
    foto = Column(String(500), nullable=True)
    curp = Column(String(18), nullable=True)
    codigo_qr = Column(String(100), nullable=False, unique=True)
    usuario_id = Column(Integer, ForeignKey("usuario.id"), nullable=True)

    # Relación
    equipo = relationship("Equipo", back_populates="jugadores")
    usuario = relationship("Usuario", back_populates="jugadores")

    @property
    def email(self):
        return self.usuario.email if self.usuario else None


class Jornada(Base):
    __tablename__ = "jornada"
    __table_args__ = (
        UniqueConstraint("torneo_id", "numero", name="uq_jornada"),
    )

    id = Column(Integer, primary_key=True, index=True)
    torneo_id = Column(Integer, ForeignKey("torneo.id"), nullable=False)
    numero = Column(Integer, nullable=False)
    fecha = Column(Date, nullable=True)
    estatus = Column(Boolean, default=True)

    # Relación
    torneo = relationship("Torneo", back_populates="jornadas")
    partidos = relationship("Partido", back_populates="jornada")


class Partido(Base):
    __tablename__ = "partido"
    __table_args__ = (
        CheckConstraint("equipo_local_id <> equipo_visitante_id", name="chk_equipos_distintos"),
    )

    id = Column(Integer, primary_key=True, index=True)
    torneo_id = Column(Integer, ForeignKey("torneo.id"), nullable=False)
    jornada_id = Column(Integer, ForeignKey("jornada.id"), nullable=False)
    equipo_local_id = Column(Integer, ForeignKey("equipo.id"), nullable=False)
    equipo_visitante_id = Column(Integer, ForeignKey("equipo.id"), nullable=False)
    puntos_local = Column(Integer, default=0)
    puntos_visitante = Column(Integer, default=0)
    ubicacion_id = Column(Integer, ForeignKey("torneo_ubicaciones.id"), nullable=True)
    estatus = Column(String(50), nullable=True)
    tipo = Column(String(50), nullable=True)
    observaciones = Column(String(500), nullable=True)

    # Relaciones
    torneo = relationship("Torneo", back_populates="partidos")
    jornada = relationship("Jornada", back_populates="partidos")
    equipo_local = relationship("Equipo", foreign_keys=[equipo_local_id])
    equipo_visitante = relationship("Equipo", foreign_keys=[equipo_visitante_id])
    ubicacion = relationship("TorneoUbicacion")
    arbitrajes = relationship("PartidoArbitraje", back_populates="partido", cascade="all, delete-orphan")
    sets = relationship("PartidoSet", back_populates="partido", cascade="all, delete-orphan")


class PartidoArbitraje(Base):
    __tablename__ = "partido_arbitraje"
    __table_args__ = (
        UniqueConstraint("partido_id", "equipo_id", name="uq_partido_equipo_arbitraje"),
    )

    id = Column(Integer, primary_key=True, index=True)
    partido_id = Column(Integer, ForeignKey("partido.id", ondelete="CASCADE"), nullable=False)
    equipo_id = Column(Integer, ForeignKey("equipo.id", ondelete="CASCADE"), nullable=False)
    pagado = Column(Boolean, default=False)
    monto = Column(Numeric(10, 2), nullable=True)
    fecha_pago = Column(DateTime, nullable=True)
    observaciones = Column(String(500), nullable=True)

    # Relaciones
    partido = relationship("Partido", back_populates="arbitrajes")
    equipo = relationship("Equipo")


class PartidoSet(Base):
    __tablename__ = "partido_set"

    id = Column(Integer, primary_key=True, index=True)
    partido_id = Column(Integer, ForeignKey("partido.id", ondelete="CASCADE"), nullable=False)
    numero_set = Column(Integer, nullable=False)
    marcador_local = Column(Integer, default=0)
    marcador_visitante = Column(Integer, default=0)
    puntos_local = Column(Integer, default=0)
    puntos_visitante = Column(Integer, default=0)

    # Relación
    partido = relationship("Partido", back_populates="sets")



class Asistencia(Base):
    __tablename__ = "asistencia"
    __table_args__ = (
        UniqueConstraint("partido_id", "jugador_id", name="uq_asistencia_partido_jugador"),
    )

    id = Column(Integer, primary_key=True, index=True)
    partido_id = Column(Integer, ForeignKey("partido.id", ondelete="CASCADE"), nullable=False)
    jugador_id = Column(Integer, ForeignKey("jugador.id"), nullable=False)
    registrado_por = Column(Integer, ForeignKey("jugador.id"), nullable=False)  # ID del capitán que registra
    metodo = Column(String(50), nullable=False)  # "qr", "manual"
    hora_registro = Column(DateTime, server_default=func.now())

    # Relaciones
    partido = relationship("Partido")
    jugador = relationship("Jugador", foreign_keys=[jugador_id])
    capitan = relationship("Jugador", foreign_keys=[registrado_por])


class Usuario(Base):
    __tablename__ = "usuario"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    nombre = Column(String(255), nullable=False)
    rol = Column(String(200), nullable=False)  # Roles separados por coma: "admin,arbitro,capitan"

    @property
    def roles(self):
        return self.rol.split(",") if self.rol else []

    @roles.setter
    def roles(self, value):
        self.rol = ",".join(value) if value else ""
    estatus = Column(Boolean, default=True)
    anfitrion_id = Column(Integer, ForeignKey("anfitrion.id"), nullable=True)
    fecha_creacion = Column(DateTime, server_default=func.now())

    # Relaciones
    jugadores = relationship("Jugador", back_populates="usuario")
    anfitrion = relationship("Anfitrion")
