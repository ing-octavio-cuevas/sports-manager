from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from app.database import engine, Base
from app.routers import tournaments, anfitriones, equipos, jugadores, jornadas, partidos, partido_arbitraje, partido_sets, asistencias, usuarios, auth

# Crear las tablas en la BD al iniciar (si no existen)
# Base.metadata.create_all(bind=engine)

# Crear carpeta de uploads si no existe
os.makedirs("uploads", exist_ok=True)

app = FastAPI(title="Torneos API", version="0.1.0")

# CORS — permite que tu front local consuma la API sin problemas
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://tornealo-sports.com",
        "https://d2rjzmmh7o8p9e.cloudfront.net/login",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registrar routers
app.include_router(anfitriones.router)
app.include_router(tournaments.router)
app.include_router(equipos.router)
app.include_router(jugadores.router)
app.include_router(jornadas.router)
app.include_router(partidos.router)
app.include_router(partido_arbitraje.router)
app.include_router(partido_sets.router)
app.include_router(asistencias.router)
app.include_router(usuarios.router)
app.include_router(auth.router)

# Servir archivos estáticos (fotos)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
# Mensaje de prueba 2