from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import List, Optional, Union
import secrets


class Settings(BaseSettings):
    PROJECT_NAME: str = "AUTOMIC Booking Backend"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # Database
    DATABASE_URL: str

    # Security
    SECRET_KEY: str = secrets.token_urlsafe(32)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALGORITHM: str = "HS256"

    # CORS
    BACKEND_CORS_ORIGINS: Union[str, List[str]] = []

    # Regex matched against the request Origin, checked in addition to the list
    # above. The default covers localhost during development and every
    # *.vercel.app deployment (production domain and preview builds alike), so
    # renaming the frontend project does not lock the API out.
    BACKEND_CORS_ORIGIN_REGEX: str = (
        r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"
        r"|^https://([a-zA-Z0-9-]+\.)*vercel\.app$"
    )

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v):
        if isinstance(v, str):
            return [i.strip() for i in v.split(",") if i.strip()]
        return v

    # First Super Admin (seed)
    FIRST_SUPER_ADMIN_EMAIL: str = "admin@automiq.com.br"
    FIRST_SUPER_ADMIN_PASSWORD: str = "AutomIQ@2024!"
    FIRST_SUPER_ADMIN_NAME: str = "Super Admin"

    # Timezone
    DEFAULT_TIMEZONE: str = "America/Sao_Paulo"

    # Uploads
    UPLOAD_STORAGE: str = "local"  # "local" or "r2"
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE_MB: int = 10

    # Cloudflare R2 (S3-compatible) — required when UPLOAD_STORAGE=r2
    R2_ACCOUNT_ID: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_BUCKET_NAME: str = ""
    R2_PUBLIC_URL: str = ""  # ex: https://pub-xxx.r2.dev or custom domain

    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_LOGIN_PER_MINUTE: int = 5

    # Webhooks
    WEBHOOKS_ENABLED: bool = False

    model_config = {"env_file": ".env", "case_sensitive": True, "extra": "ignore"}

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def max_upload_size_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024


settings = Settings()
