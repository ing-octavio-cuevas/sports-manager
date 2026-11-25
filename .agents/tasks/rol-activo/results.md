# Resultados: GET /torneos/{torneo_id}/rol-activo

## Cambios (sin commit)
- app/schemas.py: import `date`; modelos RolActivoCancha, RolActivoEquipo, RolActivoPartido, RolActivoJornada, RolActivoResponse (al final del archivo).
- app/routers/tournaments.py: imports (Jornada, Equipo, Jugador, get_current_user, HTTPAuthorizationCredentials, RolActivoResponse), dependencia `_usuario_rol_activo` y endpoint `get_rol_activo` (antes de /{torneo_id}/dashboard). Sin colision de rutas. Sin rate limit (las rutas autenticadas del archivo no lo usan).
- Sin .sql, sin migraciones, sin cambios de esquema, sin tocar .env.

## Decisiones aplicadas (decisions.md)
- Jornada.estatus se ignora. Se envia la jornada si tiene al menos un partido con estatus distinto de "Jugado" (NULL cuenta como pendiente). Jornada sin partidos no se envia. Esto difiere del contrato original ("estatus = false"), por decision confirmada del usuario.
- Jornadas por numero asc. Partidos por fecha_hora, ubicacion_id, id; nulos al final. Se envian todos los partidos de la jornada incluida (tambien los "Jugado").
- Orden de errores: 401, 404, 403. Acceso: anfitrion del torneo, o Jugador activo en Equipo activo del torneo. No se exige Torneo.publicado.
- Sin token: HTTPBearer de FastAPI 0.115 responde 403, asi que el endpoint usa una dependencia propia que responde 401 {"detail": "No autenticado"}; token invalido sigue en get_current_user (401).
- cancha.url = TorneoUbicacion.ubicacion. cancha.nombre puede ser null (la columna admite null).

## Verificacion ejecutada
- py_compile app/routers/tournaments.py app/schemas.py: OK.
- `import app.main`: OK.
- .agents/tasks/rol-activo/check_rol_activo.py (SQLite en memoria, llamada ASGI directa porque httpx no esta instalado): todos OK. Cubre sin token 401, token invalido 401, jugador con equipo activo 200, equipo inactivo 403, otro torneo 403, usuario sin jugador 403, anfitrion 200, otro anfitrion 403, torneo inexistente 404, torneo sin jornadas 200 con [], orden de jornadas (1,3; la 2 completa y la 4 vacia se omiten; estatus de jornada ignorado), orden de partidos (hora, cancha, sin cancha, sin hora al final), cancha null, logo null, fecha_hora null.

## No verificado sin PostgreSQL
- Orden de NULL en SQL: se fuerza con `IS NULL` explicito, pero no se probo en PostgreSQL.
- Rendimiento/consultas reales y tipos reales de columnas (SQLite es laxo).
- Despliegue en Docker/EC2.