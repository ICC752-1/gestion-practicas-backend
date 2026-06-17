from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    """Centraliza las variables de entorno de la aplicacion y sus
    valores por defecto; aca se define y gestiona esa configuracion."""

    # Base de datos
    POSTGRES_HOST: str = ""
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = ""
    POSTGRES_USER: str = ""
    POSTGRES_PASSWORD: str = ""

    # JWT
    JWT_SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Logging
    LOG_DIR: str = "logs"
    LOG_FILE_NAME: str = "gestion_practicas.jsonl"
    LOG_ERROR_FILE_NAME: str = "gestion_practicas_errors.jsonl"
    LOG_LEVEL: str = "INFO"
    LOG_MAX_BYTES: int = 10485760
    LOG_BACKUP_COUNT: int = 5

    # Documentos
    DOCUMENT_STORAGE_DIR: str = "storage/documents"
    DOCUMENT_MAX_BYTES: int = 10485760
    DOCUMENT_ALLOWED_EXTENSIONS: str = "pdf,docx,jpg,png,zip"
    DOCUMENT_RETENTION_DAYS: int = 0

    # Practicas
    STUDENT_CORRECTION_WINDOW_HOURS: int = 24
    # Alias legado para entornos locales creados antes del contrato Sprint 11.3.
    STUDENT_INTERNSHIP_EDIT_WINDOW_HOURS: int | None = None

    # notificaciones
    NOTIFICATION_MODE: str = "simulated"

    # correo electronico
    MAIL_USERNAME: str = "test@example.com"
    MAIL_PASSWORD: str = "password"
    MAIL_FROM: str = "test@example.com"
    MAIL_PORT: int = 1025
    MAIL_SERVER: str = "localhost"
    MAIL_STARTTLS: bool = False
    MAIL_SSL_TLS: bool = False

    # CORS
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Google OAuth
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_AUTH_URI: str = "https://accounts.google.com/o/oauth2/v2/auth"
    GOOGLE_TOKEN_URI: str = "https://oauth2.googleapis.com/token"
    GOOGLE_JWKS_URI: str = "https://www.googleapis.com/oauth2/v3/certs"
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/auth/google/callback"
    GOOGLE_ALLOWED_DOMAINS: str = "ufromail.cl,ufrontera.cl"
    GOOGLE_FRONTEND_SUCCESS_URL: str = "http://localhost:5173/auth/callback"
    GOOGLE_FRONTEND_ERROR_URL: str = "http://localhost:5173/auth/callback"
    GOOGLE_STATE_EXPIRE_MINUTES: int = 10
    GOOGLE_STATE_COOKIE_NAME: str = "google_oauth_state"
    GOOGLE_COOKIE_SECURE: bool = False
    REFRESH_TOKEN_COOKIE_NAME: str = "refresh_token"
    REFRESH_TOKEN_COOKIE_SECURE: bool = False

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def CORS_ALLOWED_ORIGINS(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.CORS_ORIGINS.split(",")
            if origin.strip()
        ]

    @property
    def DOCUMENT_ALLOWED_EXTENSION_SET(self) -> set[str]:
        return {
            extension.strip().lower().lstrip(".")
            for extension in self.DOCUMENT_ALLOWED_EXTENSIONS.split(",")
            if extension.strip()
        }

    @property
    def STUDENT_EFFECTIVE_CORRECTION_WINDOW_HOURS(self) -> int:
        return (
            self.STUDENT_INTERNSHIP_EDIT_WINDOW_HOURS
            if self.STUDENT_INTERNSHIP_EDIT_WINDOW_HOURS is not None
            else self.STUDENT_CORRECTION_WINDOW_HOURS
        )

    @property
    def GOOGLE_ALLOWED_DOMAIN_LIST(self) -> list[str]:
        return [
            domain.strip().lower()
            for domain in self.GOOGLE_ALLOWED_DOMAINS.split(",")
            if domain.strip()
        ]

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


config = Config()
