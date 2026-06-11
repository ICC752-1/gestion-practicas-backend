"""Modelo ORM de refresh tokens persistentes.

Este modulo define la entidad `RefreshToken`, usada para revocar y auditar
refresh tokens emitidos por el backend.
"""

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.database import Base


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class RefreshToken(Base):
    """Representa un refresh token persistido y revocable.

    La base de datos almacena el hash del token, no el token en texto plano.
    El campo `jti` permite identificar un refresh token especifico dentro del
    payload JWT.
    """

    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    jti: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=_utc_now,
        nullable=False,
    )

    user = relationship("User", back_populates="refresh_tokens")
