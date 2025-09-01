"""
Configuration settings for the application
"""

import os
from typing import List
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """Application settings"""
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./wedding_seating.db")
    USE_FIREBASE: bool = os.getenv("USE_FIREBASE", "false").lower() in ("1", "true", "yes")
    FIREBASE_CREDENTIALS_JSON: str | None = os.getenv("FIREBASE_CREDENTIALS_JSON")
    FIREBASE_CREDENTIALS_FILE: str | None = os.getenv("FIREBASE_CREDENTIALS_FILE")
    FIREBASE_CREDENTIALS_B64: str | None = os.getenv("FIREBASE_CREDENTIALS_B64")
    
    # Security
    ADMIN_TOKEN: str = os.getenv("ADMIN_TOKEN", "admin_token_123")
    
    # Application
    BASE_URL: str = os.getenv("BASE_URL", "http://localhost:8000")
    
    # CORS
    ALLOW_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5000",
        "http://localhost:8000",
        "https://*.replit.dev",
        "https://*.repl.co"
    ]
    
    # File limits
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10MB
    
    # Rate limiting
    RATE_LIMIT_PER_MINUTE: int = 30
    
    class Config:
        env_file = ".env"

settings = Settings()
