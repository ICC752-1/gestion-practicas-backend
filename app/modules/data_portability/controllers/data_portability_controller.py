"""Rutas HTTP para portabilidad de datos del estudiante."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import config
from app.core.database.database import get_db
from app.modules.auth.dependencies.auth_dependency import get_current_user
from app.modules.auth.models.user_model import User
from app.modules.data_portability.repositories.data_portability_repository import (
    DataPortabilityRepository,
)
from app.modules.data_portability.services.data_portability_service import (
    DataPortabilityService,
)

router = APIRouter(prefix="/data-portability", tags=["Data portability"])


@router.get("/me/export")
async def export_my_data(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    export_format: Annotated[
        Literal["json", "pdf", "zip"],
        Query(alias="format"),
    ] = "zip",
    include_documents: bool = True,
) -> Response:
    service = DataPortabilityService(
        repository=DataPortabilityRepository(db),
        app_config=config,
    )
    export = await service.export_my_data(
        actor=current_user,
        export_format=export_format,
        include_documents=include_documents,
    )
    return Response(
        content=export.content,
        media_type=export.media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{export.filename}"',
        },
    )
