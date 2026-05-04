# __init__.py

# Export de modelos para que sqlalchemy no reclame.
from app.modules.auth.models.role_model import Role as Role
from app.modules.auth.models.user_model import User as User
from app.modules.auth.models.user_role_model import UserRole as UserRole

__all__ = [
    "Role",
    "User",
    "UserRole",
]
