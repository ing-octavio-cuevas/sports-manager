# Review rol-activo

Verdict: APPROVED. No blockers.

- Route /torneos/{torneo_id}/rol-activo is unique; /{torneo_id} matches one segment only.
- Error order 401, 404, 403. Missing token gives 401 via custom dependency, invalid token via get_current_user.
- Access: host (usuario.anfitrion_id == torneo.anfitrion_id) or active Jugador in active Equipo of the torneo, matches decisions.md.
- Jornadas: Jornada.estatus ignored, included if any partido estatus != 'Jugado' (NULL counted), ordered by numero, per confirmed decision (differs from original contract text by user choice).
- Partidos ordered by fecha_hora, ubicacion_id, id with NULLs last. Nulls for cancha/logo/fecha handled. Empty gives jornadas [].
- No .sql, migration, .env, partidos.py or models.py changes belong to this task.
- Verification evidence in results.md covers all status codes, ordering and nulls. PostgreSQL NULL ordering untested but forced explicitly with IS NULL; not a blocker.
