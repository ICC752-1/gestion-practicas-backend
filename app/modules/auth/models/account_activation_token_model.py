"""Modelo ORM para tokens de activacion de cuenta.

Los tokens se envian al usuario por correo como enlaces de un solo uso. La base
de datos almacena solo el hash para evitar que un volcado de datos permita
activar cuentas directamente.
"""

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.database import Base


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class AccountActivationToken(Base):
    """Representa un token revocable para definir la contraseña inicial."""

    __tablename__ = "account_activation_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=_utc_now,
        nullable=False,
    )

    user = relationship(
        "User",
        foreign_keys=[user_id],
        back_populates="activation_tokens",
    )
    created_by = relationship("User", foreign_keys=[created_by_id])
