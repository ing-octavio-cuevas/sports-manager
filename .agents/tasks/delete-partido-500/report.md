# DELETE /partidos/482 returns 500: investigation

## Summary

Most likely cause (hypothesis, strongly supported by the code): `evento_auditoria.partido_id` is a foreign key to `partido.id` with no `ondelete`, and partido 482 has audit rows. The handler runs `db.delete(partido); db.commit()`. PostgreSQL rejects the delete with a foreign key violation. The error surfaces as an unhandled `sqlalchemy.exc.IntegrityError` (wrapping `psycopg2.errors.ForeignKeyViolation`), which FastAPI returns as 500.

The audit rows come from `registrar_evento(..., partido_id=...)` calls in `app/routers/partidos.py` (lines ~168 and ~275, score changes on PUT and on resultados-bulk) and `app/routers/asistencias.py`. So any partido that had its result edited, or had attendance activity, is likely to fail on delete.

Only the server logs or the database can confirm this (see "What needs the server or DB").

## Evidence

### The handler (confirmed from code)
`app/routers/partidos.py:293-310`, `delete_partido`:
1. Requires role anfitrion (`require_role(ROL_ANFITRION)`).
2. Loads the Partido, 404 if missing.
3. If the user is anfitrion without the jugador role and has `anfitrion_id`, it checks `torneo.anfitrion_id` and returns 403 on mismatch.
4. Blocks with 400 if any `Asistencia` exists for the partido.
5. `db.delete(partido)` then `db.commit()`.

There is no try/except and no `db.rollback()`. Any DB error propagates. `app/main.py` registers only a `RateLimitExceeded` handler, so no global handler turns `IntegrityError` into a 4xx.

### Foreign keys to `partido` (confirmed from `app/models.py`)

| Table | FK definition | ORM relationship from Partido | Outcome on delete |
|---|---|---|---|
| `partido_arbitraje` | `ondelete="CASCADE"` (line 178) | `arbitrajes`, `cascade="all, delete-orphan"` (line 167) | OK. The ORM deletes the children itself, so it works even if the DB lacks CASCADE. |
| `partido_set` | `ondelete="CASCADE"` (line 194) | `sets`, `cascade="all, delete-orphan"` (line 168) | OK, same reason. |
| `asistencia` | `ondelete="CASCADE"` (line 213) | none on Partido (`Asistencia.partido` has no backref) | Handler returns 400 first if any exist, so it never blocks with a 500. If the DB lacks CASCADE, there is still no 500 because of the 400 guard. |
| `evento_auditoria` | `ForeignKey("partido.id")`, nullable, no `ondelete` (line 236) | none | **Blocks.** Default is NO ACTION/RESTRICT. SQLAlchemy does not null the column because there is no relationship. The DELETE fails with a foreign key violation if any row has `partido_id = 482`. |

No other model column references `partido.id` (grep of `app/models.py`). `RecordatorioAsistencia`-style tables reference `jugador`, not `partido`.

### Real DB constraints (partly unknown)
`Base.metadata.create_all` is commented out (`app/main.py:27`). The `scripts/` folder (`scripts_prod.sql`, `script_test.sql`, `migration_recordatorio_asistencia.sql`) contains no `evento_auditoria` DDL and no FK definitions for `partido` that my search found. The production constraints therefore cannot be confirmed from the repo and may differ from the models (hypothesis).

### Failures independent of foreign keys (confirmed: none found)
- Imports are present: `Partido`, `Torneo`, `HTTPException`, `require_role`, `ROL_ANFITRION`, `ROL_JUGADOR` (lines 1-9); `Asistencia` is imported inside the function.
- The ownership check is guarded and returns 403, not 500.
- The handler does no audit logging after the delete, so audit code cannot fail here. `registrar_evento` swallows its own exceptions, but it is not called in the delete path.
- Side note: the file has mojibake in comments (encoding), which is harmless.

## Conclusions and recommendations

1. Confirmed from code: the handler has no error handling, and `evento_auditoria.partido_id` has no `ondelete`. This is the only FK in the models that can raise an `IntegrityError` on this delete.
2. Smallest code fix: before `db.delete(partido)`, null out the audit references so history is kept:
   ```python
   from app.models import EventoAuditoria
   db.query(EventoAuditoria).filter(EventoAuditoria.partido_id == partido_id).update(
       {EventoAuditoria.partido_id: None}, synchronize_session=False)
   ```
   Also wrap commit in try/except `IntegrityError`, call `db.rollback()`, and raise a 409 with a clear message, so unexpected constraints do not give a 500.
3. Durable fix (model plus SQL): set `ondelete="SET NULL"` on `EventoAuditoria.partido_id`, and run on the database (constraint name may differ; check first):
   ```sql
   SELECT conname FROM pg_constraint
   WHERE conrelid = 'evento_auditoria'::regclass AND contype = 'f';
   ALTER TABLE evento_auditoria DROP CONSTRAINT evento_auditoria_partido_id_fkey;
   ALTER TABLE evento_auditoria
     ADD CONSTRAINT evento_auditoria_partido_id_fkey
     FOREIGN KEY (partido_id) REFERENCES partido(id) ON DELETE SET NULL;
   ```
   Add the same statements to `scripts/`. Without the SQL, the model change alone does nothing, because the schema is not created from the models.
4. Immediate workaround without deploying: `UPDATE evento_auditoria SET partido_id = NULL WHERE partido_id = 482;` then retry the DELETE.

## What needs the server or DB (not confirmable here)
- The server log traceback for the request. Expect `sqlalchemy.exc.IntegrityError ... ForeignKeyViolation ... violates foreign key constraint "<name>" on table "evento_auditoria"`. If it names a different table (for example `partido_arbitraje`, `partido_set` or `asistencia`), the production schema lacks the cascade the models assume, or some other table references `partido`.
- `SELECT count(*) FROM evento_auditoria WHERE partido_id = 482;`
- The actual FKs: `SELECT conrelid::regclass, conname, confdeltype FROM pg_constraint WHERE confrelid = 'partido'::regclass;` (`a` = NO ACTION, `c` = CASCADE, `n` = SET NULL).
- Whether other triggers or tables outside the repo reference `partido`.
