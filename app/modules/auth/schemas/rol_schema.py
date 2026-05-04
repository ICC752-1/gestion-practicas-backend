"""Schemas Pydantic para roles y asignaciones.

Este módulo define modelos de entrada y salida relacionados con la creación,
actualización, consulta y asignación de roles.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RoleCreateRequest(BaseModel):
    """Payload de solicitud para crear un rol.

    Attributes:
        name: Nombre del rol.
            Restricciones: longitud mínima 2 y máxima 100 caracteres.
        description: Descripción del rol.
            Restricciones: longitud máxima 255 caracteres.
    """

    name: str = Field(
        min_length=2,
        max_length=100,
    )

    description: str | None = Field(
        default=None,
        max_length=255,
    )


class RoleUpdateRequest(BaseModel):
    """Payload de solicitud para actualizar un rol.

    Attributes:
        description: Nueva descripción del rol.
            Restricciones: longitud máxima 255 caracteres.
    """

    description: str | None = Field(
        default=None,
        max_length=255,
    )


class RoleResponse(BaseModel):
    """Modelo de respuesta con información de un rol.

    Configurado con `from_attributes=True` para permitir la creación del schema
    a partir de instancias ORM.

    Attributes:
        id: Identificador entero del rol.
        name: Nombre del rol.
        description: Descripción del rol (opcional).
        created_at: Marca temporal de creación/última actualización del rol.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    created_at: datetime


class AssignRoleRequest(BaseModel):
    """Payload de solicitud para asignar un rol a un usuario.

    Attributes:
        role_id: Identificador entero del rol a asignar.
    """

    role_id: int


class UserRoleResponse(BaseModel):
    """Modelo de respuesta para roles asociados a un usuario.

    Configurado con `from_attributes=True` para permitir la creación del schema
    a partir de instancias ORM.

    Attributes:
        id: Identificador entero del rol.
        name: Nombre del rol.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str