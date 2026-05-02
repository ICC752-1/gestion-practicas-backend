"""Repositorio de acceso a datos para usuarios.

Este módulo define `UserRepository`, encargado de encapsular consultas y
operaciones de persistencia relacionadas con la entidad `User` usando una sesión
asíncrona de SQLAlchemy.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.auth.models.user_model import User
from app.modules.auth.models.user_role_model import UserRole


class UserRepository:
    """Implementa operaciones de lectura y escritura sobre usuarios.

    Attributes:
        db: Sesión asíncrona (`AsyncSession`) utilizada para ejecutar consultas y
            confirmar transacciones.
    """

    def __init__(self, db: AsyncSession) -> None:
        """Inicializa el repositorio con una sesión de base de datos.

        Args:
            db: Sesión asíncrona de SQLAlchemy.
        """

        self.db = db
    
    async def get_user_by_email(self, email:str) -> User | None:
        """Obtiene un usuario por correo electrónico.

        La consulta incluye carga ansiosa de roles asociados (`User.roles`) y de
        la relación hacia `Role` a través de `UserRole`.

        Args:
            email: Correo electrónico a buscar.

        Returns:
            La entidad `User` si existe; `None` si no se encuentra.
        """

        query = select(User).where(User.email == email).options(selectinload(User.roles).selectinload(UserRole.role))
        result = await self.db.execute(query)
        
        return result.scalar_one_or_none()
    
    async def get_user_by_id(self, user_id:UUID) -> User | None:
        """Obtiene un usuario por su identificador.

        La consulta incluye carga ansiosa de roles asociados (`User.roles`) y de
        la relación hacia `Role` a través de `UserRole`.

        Args:
            user_id: Identificador UUID del usuario.

        Returns:
            La entidad `User` si existe; `None` si no se encuentra.
        """

        query = select(User).where(User.id == user_id).options(selectinload(User.roles).selectinload(UserRole.role))
        result = await self.db.execute(query)
        
        return result.scalar_one_or_none()
    
    async def create_user(self, user: User) -> User:
        """Persiste un usuario en la base de datos.

        Agrega la entidad a la sesión, confirma la transacción y refresca la
        instancia para asegurar que campos generados por la base de datos queden
        disponibles en el objeto.

        Args:
            user: Entidad `User` a crear.

        Returns:
            La misma entidad `User` persistida y refrescada.
        """

        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)

        return user