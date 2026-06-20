"""Repositorio de tokens de activacion de cuenta."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.auth.models.account_activation_token_model import (
    AccountActivationToken,
)


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class AccountActivationTokenRepository:
    """Persistencia y validacion de tokens de activacion de cuenta."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_token(
        self,
        activation_token: AccountActivationToken,
    ) -> AccountActivationToken:
        """Persiste un token de activacion."""

        self.db.add(activation_token)
        await self.db.commit()
        await self.db.refresh(activation_token)

        return activation_token

    async def get_token_by_hash(
        self,
        token_hash: str,
    ) -> AccountActivationToken | None:
        """Obtiene un token por hash, cargando el usuario asociado."""

        query = (
            select(AccountActivationToken)
            .where(AccountActivationToken.token_hash == token_hash)
            .options(selectinload(AccountActivationToken.user))
        )
        result = await self.db.execute(query)

        return result.scalar_one_or_none()

    async def revoke_active_tokens_for_user(self, user_id: int) -> int:
        """Revoca tokens pendientes para un usuario antes de emitir uno nuevo."""

        now = _utc_now()
        query = select(AccountActivationToken).where(
            AccountActivationToken.user_id == user_id,
            AccountActivationToken.used_at.is_(None),
            AccountActivationToken.revoked_at.is_(None),
            AccountActivationToken.expires_at > now,
        )
        result = await self.db.execute(query)
        activation_tokens = list(result.scalars().all())

        for activation_token in activation_tokens:
            activation_token.revoked_at = now

        await self.db.commit()

        return len(activation_tokens)

    async def mark_token_used(
        self,
        activation_token: AccountActivationToken,
    ) -> AccountActivationToken:
        """Marca un token como usado."""

        activation_token.used_at = _utc_now()
        await self.db.commit()
        await self.db.refresh(activation_token)

        return activation_token

    async def consume_token_for_user(
        self,
        activation_token: AccountActivationToken,
        user,
    ) -> AccountActivationToken:
        """Confirma en una transaccion el uso del token y cambios del usuario."""

        activation_token.used_at = _utc_now()
        await self.db.commit()
        await self.db.refresh(activation_token)
        await self.db.refresh(user)

        return activation_token

    def is_token_valid(self, activation_token: AccountActivationToken) -> bool:
        """Indica si el token aun puede usarse."""

        now = _utc_now()
        return (
            activation_token.used_at is None
            and activation_token.revoked_at is None
            and activation_token.expires_at > now
        )
