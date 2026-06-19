from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import config
from app.core.logging.logging import setup_logging
from app.modules.admin.controllers.admin_controller import router as admin_router
from app.modules.admin.controllers.admin_report_controller import (
    router as admin_report_router,
)
from app.modules.auth.controllers.auth_controller import router as auth_router
from app.modules.auth.controllers.role_controller import router as roles_router
from app.modules.auth.controllers.user_controller import router as users_router
from app.modules.documents.controllers.document_controller import (
    router as documents_router,
)
from app.modules.data_portability.controllers.data_portability_controller import (
    router as data_portability_router,
)
from app.modules.notifications.controllers.notification_controller import (
    router as notifications_router,
)
from app.modules.presentation_letters.controllers.presentation_letter_controller import (
    router as presentation_letters_router,
)
from app.modules.scheduling.controllers.scheduling_controller import (
    router as scheduling_router,
)
from app.modules.supervisor_evaluations.controllers.supervisor_evaluation_controller import (
    router as supervisor_evaluations_router,
)
from app.modules.self_evaluations.controllers.self_evaluation_controller import (
    router as self_evaluations_router,
)
from app.modules.internships.controllers.induction_admin_controller import (
    router as induction_admin_router,
)
from app.modules.internships.controllers.internship_controller import (
    router as internships_router,
)

import logging

setup_logging()

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    logger.info("Application startup completed")
    yield
    logger.info("Application shutdown completed")


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(roles_router)
app.include_router(admin_router)
app.include_router(admin_report_router)
app.include_router(notifications_router)
app.include_router(internships_router)
app.include_router(induction_admin_router)
app.include_router(supervisor_evaluations_router)
app.include_router(self_evaluations_router)
app.include_router(documents_router)
app.include_router(scheduling_router)
app.include_router(data_portability_router)
app.include_router(presentation_letters_router)
