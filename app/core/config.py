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

    # correo electronico
    MAIL_USERNAME: str = "test@example.com"
    MAIL_PASSWORD: str = "password"
    MAIL_FROM: str = "test@example.com"
    MAIL_PORT: int = 1025
    MAIL_SERVER: str = "localhost"
    MAIL_STARTTLS: bool = False
    MAIL_SSL_TLS: bool = False

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


config = Config()
