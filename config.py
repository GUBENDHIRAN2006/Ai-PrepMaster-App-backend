import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Settings:
    # -----------------------------------------------------------------------
    # Database — defaults to local SQLite, switches to Supabase PostgreSQL
    # when DATABASE_URL is set in .env
    # -----------------------------------------------------------------------
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "sqlite:///./interview_prep.db"   # fallback for local dev without Supabase
    )

    # JWT authentication configuration
    JWT_SECRET: str = os.getenv("JWT_SECRET", "super-secret-key-change-this-in-production")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))  # 24 hours

    # Administrator default credentials
    ADMIN_EMAIL: str = os.getenv("ADMIN_EMAIL", "admin@prepmaster.com")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "admin123")

    # CORS Allowed Origins
    ALLOWED_ORIGINS: str = os.getenv("ALLOWED_ORIGINS", "*")

    # OpenAI API Configuration
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

    # Supabase credentials (used for optional direct Supabase SDK calls from backend)
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")

settings = Settings()
