import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from backend.config.settings import settings

logger = logging.getLogger("uvicorn.error")

Base = declarative_base()

def get_engine():
    db_url = settings.DATABASE_URL
    if db_url and db_url.startswith("postgresql"):
        try:
            # Set 3 second connect_timeout so fallback triggers fast if PostgreSQL server is inactive locally
            engine = create_engine(
                db_url,
                connect_args={"connect_timeout": 3},
                pool_pre_ping=True,
                pool_size=5,
                max_overflow=10
            )
            with engine.connect() as conn:
                pass
            logger.info(f"Connected to PostgreSQL database: {db_url}")
            return engine
        except Exception as e:
            logger.warning(f"PostgreSQL connection attempted but unavailable ({e}). Using SQLite database fallback.")
    
    # Fallback to local SQLite database for out-of-the-box operation
    sqlite_url = "sqlite:///./interview_ai.db"
    engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})
    logger.info("Using SQLite database fallback (interview_ai.db).")
    return engine

engine = get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
