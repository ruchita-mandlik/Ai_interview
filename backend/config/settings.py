import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Explicitly load backend/.env file
env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))
if os.path.exists(env_path):
    load_dotenv(env_path, override=True)
else:
    load_dotenv(override=True)

class Settings(BaseSettings):
    PORT: int = 8000
    HOST: str = "0.0.0.0"
    ENV: str = "development"
    
    SECRET_KEY: str = "ai_interview_secret_jwt_key_2026_dev"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    
    DATABASE_URL: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/ai_interview_db"
    
    GENAI_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    GENAI_MODEL: str = "gemini-3.8-flash"
    GROQ_API_KEY: str = ""

    model_config = SettingsConfigDict(
        env_file=env_path if os.path.exists(env_path) else ".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
