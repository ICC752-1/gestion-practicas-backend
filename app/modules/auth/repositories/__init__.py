# __init__.py

from app.modules.auth.repositories.role_repository import RoleRepository as RoleRepository
from app.modules.auth.repositories.user_repository import UserRepository as UserRepository
from app.modules.auth.repositories.user_role_repository import UserRoleRepository as UserRoleRepository

__all__ = [
    "RoleRepository",
    "UserRepository",
    "UserRoleRepository",
]
