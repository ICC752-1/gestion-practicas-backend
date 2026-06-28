from types import SimpleNamespace

from app.modules.auth.schemas.user_schema import UserCreateRequest, UserUpdateRequest
from app.modules.auth.services.user_service import UserService


class FakeUserRepository:
    def __init__(self) -> None:
        self.created_user = None
        self.updated_user = None
        self.list_params = None

    async def create_user(self, user):
        self.created_user = user
        user.id = 1
        return user

    async def update_user(self, user):
        self.updated_user = user
        return user

    async def list_users(self, **kwargs):
        self.list_params = kwargs
        return []


class FakePasswordService:
    def hash_password(self, password: str) -> str:
        return f"hashed-{password}"


def _valid_create_payload() -> UserCreateRequest:
    return UserCreateRequest(
        email="user@example.com",
        password="my-secret-password",
        first_name="Ana",
        last_name="Perez",
        rut="12.345.678-5",
        admission_year=2023,
        phone="912345678",
        sup_phone="+56 9 8765 4321",
    )


async def test_create_user_normalizes_rut_and_phones() -> None:
    repository = FakeUserRepository()
    service = UserService(
        user_repository=repository,
        password_service=FakePasswordService(),
    )

    user = await service.create_user(_valid_create_payload())

    assert repository.created_user is user
    assert user.rut == "12345678-5"
    assert user.admission_year == 2023
    assert user.phone == "+56912345678"
    assert user.sup_phone == "+56987654321"
    assert user.password_hash == "hashed-my-secret-password"
    assert user.must_change_password is True
    assert user.is_verified is False


async def test_create_user_generates_internal_password_when_missing(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "app.modules.auth.services.user_service.secrets.token_urlsafe",
        lambda length: "generated-internal-password",
    )
    repository = FakeUserRepository()
    service = UserService(
        user_repository=repository,
        password_service=FakePasswordService(),
    )
    payload = UserCreateRequest(
        email="user@example.com",
        first_name="Ana",
        last_name="Perez",
        rut="12.345.678-5",
    )

    user = await service.create_user(payload)

    assert repository.created_user is user
    assert user.password_hash == "hashed-generated-internal-password"
    assert user.must_change_password is True
    assert user.is_verified is False


async def test_update_user_normalizes_fields() -> None:
    repository = FakeUserRepository()
    service = UserService(
        user_repository=repository,
        password_service=FakePasswordService(),
    )

    user = SimpleNamespace(
        id=1,
        rut="1-9",
        admission_year=None,
        phone=None,
        sup_phone=None,
        first_name="Ana",
    )

    payload = UserUpdateRequest(
        rut="12.345.678-5",
        admission_year=2024,
        phone="912345678",
        sup_phone="+56 9 8765 4321",
        first_name="Carla",
    )

    updated = await service.update_user(user, payload)

    assert repository.updated_user is updated
    assert updated.rut == "12345678-5"
    assert updated.admission_year == 2024
    assert updated.phone == "+56912345678"
    assert updated.sup_phone == "+56987654321"
    assert updated.first_name == "Carla"


async def test_list_users_forwards_sorting_params() -> None:
    repository = FakeUserRepository()
    service = UserService(
        user_repository=repository,
        password_service=FakePasswordService(),
    )

    await service.list_users(sort_by="email", sort_dir="asc", limit=10, offset=20)

    assert repository.list_params["sort_by"] == "email"
    assert repository.list_params["sort_dir"] == "asc"
    assert repository.list_params["limit"] == 10
    assert repository.list_params["offset"] == 20
