from datetime import UTC, datetime, timedelta

from app.modules.auth.models.refresh_token_model import RefreshToken
from app.modules.auth.repositories.refresh_token_repository import RefreshTokenRepository


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class FakeResult:
    def __init__(self, value: list[RefreshToken] | None) -> None:
        self.value = value

    def scalars(self):
        return self

    def all(self) -> list[RefreshToken]:
        if self.value is None:
            return []
        return self.value


class FakeSession:
    def __init__(self, execute_result: list[RefreshToken] | None = None) -> None:
        self.commits = 0
        self.executed_query = None
        self.execute_result = execute_result

    async def commit(self) -> None:
        self.commits += 1

    async def execute(self, query):
        self.executed_query = query
        return FakeResult(self.execute_result)


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


async def test_revoke_active_tokens_for_user_revokes_matching_tokens() -> None:
    refresh_tokens = [_refresh_token(), _refresh_token()]
    db = FakeSession(execute_result=refresh_tokens)
    repository = RefreshTokenRepository(db)

    revoked_count = await repository.revoke_active_tokens_for_user(user_id=1)

    assert revoked_count == 2
    assert all(refresh_token.revoked_at is not None for refresh_token in refresh_tokens)
    assert db.commits == 1
