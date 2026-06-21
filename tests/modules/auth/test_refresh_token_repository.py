from datetime import UTC, datetime, timedelta

from app.modules.auth.models.refresh_token_model import RefreshToken
from app.modules.auth.repositories.refresh_token_repository import RefreshTokenRepository


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _refresh_token(
    expires_at: datetime | None = None,
    revoked_at: datetime | None = None,
) -> RefreshToken:
    return RefreshToken(
        user_id=1,
        jti="token-id",
        token_hash="hashed-token",
        expires_at=expires_at or _utc_now() + timedelta(days=1),
        revoked_at=revoked_at,
    )


def test_is_refresh_token_valid_returns_true_for_active_unexpired_token() -> None:
    repository = RefreshTokenRepository(db=None)
    refresh_token = _refresh_token()

    assert repository.is_refresh_token_valid(refresh_token) is True


def test_is_refresh_token_valid_returns_false_for_revoked_token() -> None:
    repository = RefreshTokenRepository(db=None)
    refresh_token = _refresh_token(revoked_at=_utc_now())

    assert repository.is_refresh_token_valid(refresh_token) is False


def test_is_refresh_token_valid_returns_false_for_expired_token() -> None:
    repository = RefreshTokenRepository(db=None)
    refresh_token = _refresh_token(expires_at=_utc_now() - timedelta(seconds=1))

    assert repository.is_refresh_token_valid(refresh_token) is False
