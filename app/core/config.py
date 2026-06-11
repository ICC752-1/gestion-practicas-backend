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

    # OAuth Google
    GOOGLE_OAUTH_CLIENT_ID: str = ""
    GOOGLE_OAUTH_CLIENT_SECRET: str = ""
    GOOGLE_OAUTH_REDIRECT_URI: str = ""
    GOOGLE_OAUTH_ALLOWED_DOMAIN: str = "ufromail.cl"
    FRONTEND_AUTH_SUCCESS_URL: str = "http://localhost:5173/dashboard"

    # Auth cookies
    AUTH_COOKIE_SECURE: bool = False
    AUTH_COOKIE_SAMESITE: str = "lax"
    AUTH_COOKIE_DOMAIN: str | None = None

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

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


config = Config()
