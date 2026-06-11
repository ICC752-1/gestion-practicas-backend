"""Repositorio de acceso a datos para refresh tokens persistentes."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models.refresh_token_model import RefreshToken


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class RefreshTokenRepository:
    """Implementa operaciones de persistencia sobre refresh tokens."""

    def __init__(self, db: AsyncSession) -> None:
        """Inicializa el repositorio con una sesion de base de datos."""

        self.db = db

    async def create_refresh_token(self, refresh_token: RefreshToken) -> RefreshToken:
        """Persiste un refresh token revocable en la base de datos."""

        self.db.add(refresh_token)
        await self.db.commit()
        await self.db.refresh(refresh_token)

        return refresh_token

    async def get_refresh_token_by_jti(self, jti: str) -> RefreshToken | None:
        """Obtiene un refresh token persistido por su identificador JWT."""

        query = select(RefreshToken).where(RefreshToken.jti == jti)
        result = await self.db.execute(query)

        return result.scalar_one_or_none()

    async def revoke_refresh_token(self, refresh_token: RefreshToken) -> RefreshToken:
        """Marca un refresh token como revocado."""

        refresh_token.revoked_at = _utc_now()
        await self.db.commit()
        await self.db.refresh(refresh_token)

        return refresh_token

    def is_refresh_token_valid(self, refresh_token: RefreshToken) -> bool:
        """Indica si un refresh token persistido sigue usable."""

        return refresh_token.revoked_at is None and refresh_token.expires_at > _utc_now()
