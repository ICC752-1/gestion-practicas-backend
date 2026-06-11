from datetime import UTC, datetime, timedelta

from app.modules.auth.models.refresh_token_model import RefreshToken
from app.modules.auth.repositories.refresh_token_repository import RefreshTokenRepository


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class FakeResult:
    def __init__(self, value: RefreshToken | None) -> None:
        self.value = value

    def scalar_one_or_none(self) -> RefreshToken | None:
        return self.value


class FakeSession:
    def __init__(self, execute_result: RefreshToken | None = None) -> None:
        self.added = None
        self.commits = 0
        self.refreshed = None
        self.executed_query = None
        self.execute_result = execute_result

    def add(self, value: RefreshToken) -> None:
        self.added = value

    async def commit(self) -> None:
        self.commits += 1

    async def refresh(self, value: RefreshToken) -> None:
        self.refreshed = value

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


async def test_create_refresh_token_persists_and_refreshes_entity() -> None:
    db = FakeSession()
    repository = RefreshTokenRepository(db)
    refresh_token = _refresh_token()

    result = await repository.create_refresh_token(refresh_token)

    assert result is refresh_token
    assert db.added is refresh_token
    assert db.commits == 1
    assert db.refreshed is refresh_token


async def test_get_refresh_token_by_jti_returns_matching_entity() -> None:
    refresh_token = _refresh_token()
    db = FakeSession(execute_result=refresh_token)
    repository = RefreshTokenRepository(db)

    result = await repository.get_refresh_token_by_jti("token-id")

    assert result is refresh_token
    assert db.executed_query is not None


async def test_revoke_refresh_token_sets_revoked_at() -> None:
    db = FakeSession()
    repository = RefreshTokenRepository(db)
    refresh_token = _refresh_token()

    result = await repository.revoke_refresh_token(refresh_token)

    assert result is refresh_token
    assert refresh_token.revoked_at is not None
    assert db.commits == 1
    assert db.refreshed is refresh_token


def test_is_refresh_token_valid_returns_true_for_active_unexpired_token() -> None:
    repository = RefreshTokenRepository(FakeSession())
    refresh_token = _refresh_token()

    assert repository.is_refresh_token_valid(refresh_token) is True


def test_is_refresh_token_valid_returns_false_for_revoked_token() -> None:
    repository = RefreshTokenRepository(FakeSession())
    refresh_token = _refresh_token(revoked_at=_utc_now())

    assert repository.is_refresh_token_valid(refresh_token) is False


def test_is_refresh_token_valid_returns_false_for_expired_token() -> None:
    repository = RefreshTokenRepository(FakeSession())
    refresh_token = _refresh_token(expires_at=_utc_now() - timedelta(seconds=1))

    assert repository.is_refresh_token_valid(refresh_token) is False
