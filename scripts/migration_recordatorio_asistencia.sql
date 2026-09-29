-- Migración: tabla para anti-duplicados de recordatorios de asistencia por WhatsApp.
-- Un capitán recibe como máximo un recordatorio por día (agrupa todos sus partidos pendientes).
-- Ejecutar una sola vez en la base de datos (prod y test).

CREATE TABLE IF NOT EXISTS recordatorio_asistencia (
    id            SERIAL PRIMARY KEY,
    capitan_id    INTEGER NOT NULL REFERENCES jugador(id),
    fecha_dia     DATE NOT NULL,                            -- día local (UTC-6) del recordatorio
    celular       VARCHAR(20),
    num_partidos  INTEGER,                                  -- cuántos partidos pendientes se recordaron
    estado        VARCHAR(20) NOT NULL DEFAULT 'enviado',   -- 'enviado' | 'error'
    detalle       VARCHAR(1000),
    fecha_envio   TIMESTAMP DEFAULT now(),
    CONSTRAINT uq_recordatorio_capitan_dia UNIQUE (capitan_id, fecha_dia)
);

CREATE INDEX IF NOT EXISTS ix_recordatorio_asistencia_capitan_id ON recordatorio_asistencia (capitan_id);
CREATE INDEX IF NOT EXISTS ix_recordatorio_asistencia_fecha_dia ON recordatorio_asistencia (fecha_dia);
