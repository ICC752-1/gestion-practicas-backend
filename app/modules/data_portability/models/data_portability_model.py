"""Modelo ORM para solicitudes de portabilidad de datos."""

from datetime import UTC, datetime
import enum

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ENUM as PGEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.database import Base


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class DataPortabilityStatusEnum(str, enum.Enum):
    """Estados de una solicitud de exportacion."""

    processing = "processing"
    completed = "completed"
    failed = "failed"


class DataPortabilityRequest(Base):
    """Auditoria funcional de una descarga de portabilidad."""

    __tablename__ = "data_portability_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    export_format: Mapped[str] = mapped_column(String(20), nullable=False)
    include_documents: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[DataPortabilityStatusEnum] = mapped_column(
        PGEnum(
            DataPortabilityStatusEnum,
            name="enumDataPortabilityStatus",
            values_callable=lambda x: [e.value for e in x],
            create_type=False,
        ),
        default=DataPortabilityStatusEnum.processing,
        nullable=False,
    )
    result_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user = relationship("User")
