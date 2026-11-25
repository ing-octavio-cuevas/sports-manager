# Review: delete-partido-500

Verdict: APPROVED. No blockers.

- partidos.py: 404/403/400 checks keep their order. The UPDATE to NULL and the delete share one transaction. IntegrityError on commit triggers rollback and a Spanish 409. Only the task hunks changed in the two .py files.
- models.py: ondelete=SET NULL on EventoAuditoria.partido_id, as agreed.
- SQL: BEGIN/COMMIT. The DO block finds the FK through pg_constraint/pg_attribute, drops it with format %I, and re-adds it with ON DELETE SET NULL. A second run drops and recreates it, so it is idempotent. The header has the inspection query. Read-only check, since PG was not available.
- Verification: the coder's record covers compile, import and an SQLite behavior test. The PG execution gap is disclosed.
- Scope: the .agents/ directory is untracked task material. No other task files touched.
