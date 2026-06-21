# __init__.py

# Export de modelos para que sqlalchemy no reclame.
from app.modules.auth.models.account_activation_token_model import (
    AccountActivationToken as AccountActivationToken,
)
from app.modules.auth.models.role_model import Role as Role
from app.modules.auth.models.refresh_token_model import RefreshToken as RefreshToken
from app.modules.auth.models.user_model import User as User
from app.modules.auth.models.user_role_model import UserRole as UserRole

__all__ = [
    "AccountActivationToken",
    "Role",
    "RefreshToken",
    "User",
    "UserRole",
]
