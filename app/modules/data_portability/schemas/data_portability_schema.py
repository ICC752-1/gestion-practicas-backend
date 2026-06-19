"""Contratos para exportacion de datos personales."""

from typing import Literal

from pydantic import BaseModel

DataPortabilityFormat = Literal["json", "zip"]


class DataPortabilityAuditResponse(BaseModel):
    request_id: int
    status: str
    export_format: str
    include_documents: bool
    result_metadata: dict | None
