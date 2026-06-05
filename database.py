from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from config import settings

# ─── Determine database type ────────────────────────────────────────────────
is_sqlite = settings.DATABASE_URL.startswith("sqlite")

if is_sqlite:
    # SQLite — local dev fallback (single-threaded, no pool needed)
    engine = create_engine(
        settings.DATABASE_URL,
        connect_args={"check_same_thread": False},
    )
else:
    # PostgreSQL / Supabase — production database
    # pool_pre_ping: checks connection health before using it (prevents stale connections)
    # pool_recycle:  recycles connections every 5 min (avoids Supabase idle timeout)
    # pool_size:     keep 5 persistent connections ready
    # max_overflow:  allow 10 extra connections during traffic spikes
    engine = create_engine(
        settings.DATABASE_URL,
        pool_pre_ping=True,
        pool_recycle=300,
        pool_size=5,
        max_overflow=10,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency — yields a DB session and guarantees cleanup."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
