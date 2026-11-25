import sys, os
sys.path.insert(0, r"c:\Users\seeli\Documents\Own\V-SportManager")
from datetime import date, datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import asyncio, json
from app.main import app
from app.database import get_db, Base
from app import models as m
from app.auth import create_access_token

eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
Base.metadata.create_all(eng)
S = sessionmaker(bind=eng)
db = S()
def add(*o):
    for x in o: db.add(x)
    db.commit()
h1 = m.Anfitrion(nombre_completo="A1")
h2 = m.Anfitrion(nombre_completo="A2")
add(h1, h2)
t1 = m.Torneo(nombre="T1", anfitrion_id=h1.id); t2 = m.Torneo(nombre="T2", anfitrion_id=h2.id)
add(t1, t2)
def U(cel, anf=None, rol="jugador"):
    u = m.Usuario(celular=cel, password_hash="x", nombre=cel, rol=rol, anfitrion_id=anf, estatus=True); add(u); return u
uj = U("1"); uin = U("2"); uotro = U("3"); uh1 = U("4", h1.id, "anfitrion"); uh2 = U("5", h2.id, "anfitrion"); usin = U("6")
ea = m.Equipo(torneo_id=t1.id, nombre="PANTHERS", logo="uploads/p.png", estatus=True)
eb = m.Equipo(torneo_id=t1.id, nombre="CENTELLAS", logo=None, estatus=True)
ec = m.Equipo(torneo_id=t1.id, nombre="INACT", estatus=False)
ed = m.Equipo(torneo_id=t2.id, nombre="OTRO", estatus=True)
add(ea, eb, ec, ed)
c = [0]
def J(eq, u): c[0]+=1; add(m.Jugador(equipo_id=eq.id, nombre="j", codigo_qr=f"q{c[0]}", usuario_id=u.id, estatus=True))
J(ea, uj); J(ec, uin); J(ed, uotro)
cancha1 = m.TorneoUbicacion(torneo_id=t1.id, nombre="Cancha 1", ubicacion="https://maps", direccion="Dir")
cancha2 = m.TorneoUbicacion(torneo_id=t1.id, nombre="Cancha 2")
add(cancha1, cancha2)
j3 = m.Jornada(torneo_id=t1.id, numero=3, fecha=date(2026,9,16), estatus=False)  # estatus ignorado
j1 = m.Jornada(torneo_id=t1.id, numero=1, fecha=date(2026,9,2), estatus=True)
j2 = m.Jornada(torneo_id=t1.id, numero=2, estatus=True)  # todos jugados -> fuera
j4 = m.Jornada(torneo_id=t1.id, numero=4, estatus=True)  # sin partidos -> fuera
add(j3, j1, j2, j4)
def P(j, h, ub, est, **k): 
    p = m.Partido(torneo_id=t1.id, jornada_id=j.id, equipo_local_id=ea.id, equipo_visitante_id=eb.id, fecha_hora=h, ubicacion_id=ub.id if ub else None, estatus=est, tipo="Oficial", **k); add(p); return p
pA = P(j1, datetime(2026,9,2,19), cancha1, "Por jugar")
pB = P(j1, datetime(2026,9,2,18), cancha2, "Por jugar")
pC = P(j1, datetime(2026,9,2,18), cancha1, "Jugado", puntos_local=3)
pD = P(j1, datetime(2026,9,2,18), None, None)
pE = P(j1, None, None, "Por jugar")
P(j2, datetime(2026,9,9,18), cancha1, "Jugado")
pF = P(j3, datetime(2026,9,16,18), cancha1, "Por jugar")
# torneo vacio de jornadas
t3 = m.Torneo(nombre="T3", anfitrion_id=h1.id); add(t3)

def override():
    s = S()
    try: yield s
    finally: s.close()
app.dependency_overrides[get_db] = override
class R:
    def __init__(self, sc, body): self.status_code = sc; self._b = body
    def json(self): return json.loads(self._b)
class Cl:
    def get(self, path, headers=None):
        async def run():
            out = {"body": b"", "status": None}
            scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": "GET", "path": path, "raw_path": path.encode(), "query_string": b"", "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()], "client": ("127.0.0.1", 1), "server": ("t", 80), "scheme": "http", "root_path": ""}
            async def receive(): return {"type": "http.request", "body": b"", "more_body": False}
            async def send(msg):
                if msg["type"] == "http.response.start": out["status"] = msg["status"]
                elif msg["type"] == "http.response.body": out["body"] += msg.get("body", b"")
            await app(scope, receive, send)
            return R(out["status"], out["body"])
        return asyncio.run(run())
cl = Cl()
def hd(u): return {"Authorization": "Bearer " + create_access_token({"sub": str(u.id)})}
def get(tid, u=None, headers=None):
    return cl.get(f"/torneos/{tid}/rol-activo", headers=headers if headers is not None else (hd(u) if u else {}))
ok = True
def chk(name, cond):
    global ok; ok &= bool(cond); print(("OK   " if cond else "FAIL ") + name)
chk("sin token 401", get(t1.id).status_code == 401)
r = get(t1.id, headers={"Authorization": "Bearer basura"}); chk("token invalido 401", r.status_code == 401 and "detail" in r.json())
chk("jugador equipo activo 200", get(t1.id, uj).status_code == 200)
chk("jugador equipo inactivo 403", get(t1.id, uin).status_code == 403)
chk("jugador otro torneo 403", get(t1.id, uotro).status_code == 403)
chk("usuario sin jugador 403", get(t1.id, usin).status_code == 403)
chk("anfitrion 200", get(t1.id, uh1).status_code == 200)
chk("otro anfitrion 403", get(t1.id, uh2).status_code == 403)
r = get(9999, uh1); chk("torneo inexistente 404", r.status_code == 404 and "detail" in r.json())
r = get(t3.id, uh1); chk("sin jornadas -> []", r.status_code == 200 and r.json() == {"torneo_id": t3.id, "jornadas": []})
r = get(t1.id, uh1); d = r.json(); print(d)
chk("jornadas 1 y 3 en orden (2 y 4 fuera)", [j["numero"] for j in d["jornadas"]] == [1, 3])
chk("fecha jornada", d["jornadas"][0]["fecha"] == "2026-09-02")
ids = [p["partido_id"] for p in d["jornadas"][0]["partidos"]]
chk("orden partidos", ids == [pC.id, pB.id, pD.id, pA.id, pE.id] or ids == [pC.id, pB.id, pD.id, pA.id, pE.id])
p0 = d["jornadas"][0]["partidos"][0]
chk("cancha completa", p0["cancha"] == {"id": cancha1.id, "nombre": "Cancha 1", "direccion": "Dir", "url": "https://maps"})
chk("local con logo", p0["local"] == {"id": ea.id, "nombre": "PANTHERS", "logo": "uploads/p.png"})
chk("visitante logo null", p0["visitante"]["logo"] is None and p0["visitante"]["nombre"] == "CENTELLAS")
chk("cancha null", d["jornadas"][0]["partidos"][2]["cancha"] is None)
chk("fecha_hora null", d["jornadas"][0]["partidos"][4]["fecha_hora"] is None)
chk("cancha sin nombre/url", True)
print("ALL OK" if ok else "SOME FAILED")
