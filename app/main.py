from fastapi import FastAPI
from app.modules.auth.controllers.auth_controller import router as auth_router
from app.modules.internships.controllers.internship_controller import (
    router as internships_router,
)

app = FastAPI()

app.include_router(auth_router)
app.include_router(internships_router)
