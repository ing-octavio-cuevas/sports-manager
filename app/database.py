from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.config import DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    pool_size=10,          # Conexiones activas en el pool
    max_overflow=20,       # Conexiones extra si el pool se llena
    pool_pre_ping=True,    # Verifica que la conexión esté viva antes de usarla
    pool_recycle=3600,     # Recicla conexiones cada hora (evita timeouts de Postgres)
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """
    Dependency de FastAPI: una sesión por request.
    - Se crea al inicio del request
    - Se hace rollback si algo falla (evita transacciones colgadas)
    - Se cierra siempre al final
    """
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
