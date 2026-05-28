from types import SimpleNamespace

from app.modules.auth.schemas.rol_schema import RoleUpdateRequest
from app.modules.auth.services.role_service import RoleService


class FakeRoleRepository:
    def __init__(self) -> None:
        self.updated_role = None

    async def update_role(self, role):
        self.updated_role = role
        return role

    async def list_roles(self):
        return []


class FakeUserRoleRepository:
    def __init__(self) -> None:
        self.assigned = None
        self.removed = None

    async def assign_role(self, user_role):
        self.assigned = user_role
        return user_role

    async def remove_role(self, user_role):
        self.removed = user_role

    async def list_roles_for_user(self, user_id: int):
        return []


async def test_update_role_updates_description() -> None:
    role = SimpleNamespace(id=1, description="Old")
    service = RoleService(
        role_repository=FakeRoleRepository(),
        user_role_repository=FakeUserRoleRepository(),
    )

    updated = await service.update_role(
        role,
        RoleUpdateRequest(description="New"),
    )

    assert updated.description == "New"


async def test_assign_role_creates_assignment() -> None:
    role = SimpleNamespace(id=7)
    user = SimpleNamespace(id=3)
    user_role_repository = FakeUserRoleRepository()
    service = RoleService(
        role_repository=FakeRoleRepository(),
        user_role_repository=user_role_repository,
    )

    assignment = await service.assign_role(user=user, role=role)

    assert assignment is user_role_repository.assigned
    assert assignment.user_id == 3
    assert assignment.role_id == 7


async def test_remove_role_delegates_to_repository() -> None:
    user_role = SimpleNamespace(user_id=3, role_id=7)
    user_role_repository = FakeUserRoleRepository()
    service = RoleService(
        role_repository=FakeRoleRepository(),
        user_role_repository=user_role_repository,
    )

    await service.remove_role(user_role)

    assert user_role_repository.removed is user_role
