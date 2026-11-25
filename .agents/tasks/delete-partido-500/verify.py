import sys, asyncio
sys.path.insert(0, r"c:\Users\seeli\Documents\Own\V-SportManager")
from types import SimpleNamespace
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
import app.main
from app.database import Base
from app import models
from app.routers import partidos as P
from app.config import ROL_ANFITRION
e = create_engine("sqlite://")
event.listen(e, "connect", lambda c, _: c.execute("PRAGMA foreign_keys=ON"))
Base.metadata.create_all(e)
S = sessionmaker(bind=e)
db = S()
print("FK ondelete:", [fk.ondelete for fk in models.EventoAuditoria.__table__.c.partido_id.foreign_keys])
for t in Base.metadata.sorted_tables: pass
# SQLite sin FKs de tablas ajenas: crear solo lo necesario
Base.metadata.drop_all(e); Base.metadata.create_all(e)
db.execute(text("PRAGMA foreign_keys=OFF"))
db.execute(text("INSERT INTO partido (id, torneo_id, jornada_id, equipo_local_id, equipo_visitante_id) VALUES (482,1,1,1,2)"))
for i in range(4):
    db.execute(text("INSERT INTO evento_auditoria (tipo_evento, partido_id) VALUES ('X', 482)"))
db.commit()
# 1) FK activa, sin SET NULL a nivel DB en SQLite? ON DELETE SET NULL tambien aplica, asi que probamos el UPDATE explicito
u = SimpleNamespace(roles=[ROL_ANFITRION], anfitrion_id=None)
P.delete_partido(482, db=db, usuario=u)
print("partido left:", db.execute(text("select count(*) from partido")).scalar())
print("audit rows:", db.execute(text("select count(*), count(partido_id) from evento_auditoria")).fetchone())
# 2) IntegrityError -> 409
db.execute(text("INSERT INTO partido (id, torneo_id, jornada_id, equipo_local_id, equipo_visitante_id) VALUES (483,1,1,1,2)"))
db.commit()
orig = db.commit
def boom(): raise IntegrityError("x", {}, Exception("fk"))
db.commit = boom
try:
    P.delete_partido(483, db=db, usuario=u); print("NO ERROR")
except HTTPException as ex:
    print("status", ex.status_code, ex.detail)
db.commit = orig
print("partido 483 still there:", db.execute(text("select count(*) from partido where id=483")).scalar())
# 3) 404
try: P.delete_partido(999, db=db, usuario=u)
except HTTPException as ex: print("404 check", ex.status_code)