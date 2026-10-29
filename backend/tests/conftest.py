import os
import sys

# Ensure root workspace directory is in sys.path
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.main import app
from backend.database.database import Base, get_db

SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///./test_interview_ai.db"

engine = create_engine(SQLALCHEMY_TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def db_session():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture(scope="function")
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

@pytest.fixture(autouse=True)
def reset_ai_service_state():
    from backend.services.ai_service import AIService
    AIService._model_cooldowns.clear()
    AIService._model_daily_quota_info.clear()
    AIService._last_successful_model = None
    AIService._in_flight_tasks.clear()
    yield
    AIService._model_cooldowns.clear()
    AIService._model_daily_quota_info.clear()
    AIService._last_successful_model = None
    AIService._in_flight_tasks.clear()

