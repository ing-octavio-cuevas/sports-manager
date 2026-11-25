# Decisiones: GET /torneos/{torneo_id}/rol-activo

Estado: P1 respondido por el usuario. P2 a P5 son supuestos pendientes de confirmar (el usuario no los respondió; se usan las recomendaciones por indicación de la sesión padre). Endpoint de solo lectura, fácil de cambiar.

## Hallazgos (punto 1 y contexto)
- Ruta sin colisión: en app/routers/tournaments.py (prefijo /torneos) no existe `rol-activo`. Existen `/{torneo_id}/resumen`, `/{torneo_id}`, `/{torneo_id}/dashboard`, etc.
- Jornada.estatus: models.py:131 `Column(Boolean, default=True)`; schemas.py JornadaCreate default True; routers/jornadas.py:30 create_jornada hace `Jornada(**jornada.model_dump())` (nace True); update_jornada (jornadas.py ~65-82) solo copia lo que envía el cliente. Ningún filtro, resumen ni dashboard lo lee. El usuario decidió ignorarlo por completo.
- "Resultado cargado" en el código: `Partido.estatus == "Jugado"` (tournaments.py:365, 453, 774, 999; dashboard ~784 `all(p.estatus == "Jugado")`; partidos.py:165 asigna "Jugado" al registrar resultado; /resumen usa `!= "Jugado"` en ~704).
- TorneoUbicacion (models.py:49) no tiene columna `url`; tiene nombre, ubicacion, direccion. /resumen usa `ubic.ubicacion` como url de mapa.
- get_current_user (auth.py:32-50): 401 por token inválido/expirado o usuario inexistente/inactivo. Con HTTPBearer por defecto, la falta total de token puede dar 403 según versión de FastAPI: verificar al implementar y forzar 401 si hace falta.
- `_verificar_acceso_torneo` (tournaments.py:32-36) no sirve para este contrato (solo bloquea anfitrión no jugador). No reutilizar; no usar require_role, usar get_current_user.
- Jugador.usuario_id -> Usuario; Equipo.torneo_id, Equipo.estatus; Jugador.estatus. Partido.ubicacion_id, fecha_hora nullable; equipos local/visitante no nulos. Jornada.fecha es Date (JornadaResponse la declara datetime; usar `date` en el nuevo schema).

## P1. Qué jornadas se envían (CONFIRMADO por el usuario)
Se ignora Jornada.estatus (ni se lee ni se filtra). Una jornada se incluye si tiene al menos un partido sin resultado cargado. Si todos sus partidos ya tienen resultado, no se envía.
- "Resultado cargado" = `Partido.estatus == "Jugado"` (criterio del dashboard y /resumen). Sin resultado = estatus distinto de "Jugado", incluido NULL.
- Jornada sin ningún partido: NO se envía (supuesto del usuario/padre; coincide con el dashboard).
- El criterio se evalúa sobre todos los partidos de la jornada, sin filtrar por tipo.
- Orden de jornadas: numero ascendente.
- Cuidado de implementación: `estatus != "Jugado"` en SQL excluye NULL; tratar NULL como sin resultado (en Python `p.estatus != "Jugado"`, o `or_(estatus.is_(None), estatus != "Jugado")`).

## P2. Orden de partidos (SUPUESTO pendiente de confirmar)
fecha_hora asc, luego ubicacion_id asc, luego Partido.id asc; nulos (sin hora, sin cancha) al final.

## P3. Partidos dentro de la jornada incluida (SUPUESTO pendiente de confirmar)
Todos los partidos de la jornada, de cualquier tipo y estatus (incluidos "Jugado").

## P4. Acceso (SUPUESTO pendiente de confirmar)
- Errores en orden 401, 404 (torneo no existe), 403.
- No se exige Torneo.publicado.
- Árbitro sin inscripción y sin ser anfitrión: 403.
- Anfitrión: `usuario.anfitrion_id is not None and usuario.anfitrion_id == Torneo.anfitrion_id`.
- Inscrito: existe Jugador (usuario_id = usuario.id, estatus True) en Equipo con torneo_id = torneo y estatus True.
- Usuario con ambos: pasa si cumple cualquiera.

## P5. Nulos y formato (SUPUESTO pendiente de confirmar)
fecha de jornada (date) y fecha_hora salen null tal cual si son null. cancha null sin ubicacion_id; cancha.url = TorneoUbicacion.ubicacion; logo null sin logo. Sin "Desconocido": los equipos no admiten nulos.
