# Verification (no commit made)
Ran with venv python:
- py_compile app/routers/partidos.py app/models.py: OK
- import app.main: OK
- .agents/tasks/delete-partido-500/verify.py (in-memory SQLite, FKs on): delete of partido 482 with 4 audit rows -> partido deleted, 4 audit rows kept with partido_id NULL; commit raising IntegrityError -> 409 + rollback, partido kept; unknown id -> 404.

Added scripts/migration_evento_auditoria_partido_set_null.sql (BEGIN/COMMIT, DO block that drops every FK evento_auditoria.partido_id -> partido found in pg_constraint, then adds evento_auditoria_partido_id_fkey ON DELETE SET NULL; header comment has the inspection query). Re-running it drops and recreates the same constraint, so it is idempotent.

Not verified (needs PostgreSQL): the SQL script was never executed or syntax-checked (DO block, format %I, pg_attribute join), the real production constraint name and delete rule, and PG FK behavior. SQLite also honors ON DELETE SET NULL from the model, so the explicit UPDATE in the handler was not isolated from it in this test.
