# __init__.py

from app.modules.auth.controllers.auth_controller import router as auth_router
from app.modules.auth.controllers.role_controller import router as roles_router
from app.modules.auth.controllers.user_controller import router as users_router

__all__ = [
    "auth_router",
    "roles_router",
    "users_router",
]
