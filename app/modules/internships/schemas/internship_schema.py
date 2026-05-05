"""Schemas for internship requests and responses."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Modality = Literal["Presencial", "Remoto", "Hibrido"]


class InternshipCreateRequest(BaseModel):
    """Payload used by students to create an internship record."""

    org_name: str = Field(min_length=1, max_length=255)
    sector: str = Field(min_length=1, max_length=255)
    address: str = Field(min_length=1, max_length=255)
    city: str = Field(min_length=1, max_length=255)
    org_phone: str | None = Field(default=None, max_length=255)
    web: str | None = Field(default=None, max_length=255)
    start_date: date
    end_date: date
    schedule: str = Field(min_length=1, max_length=255)
    days: str = Field(min_length=1, max_length=255)
    modality: Modality
    internship_address: str = Field(min_length=1, max_length=255)
    act_description: str = Field(min_length=1, max_length=255)
    ben_description: str = Field(min_length=1, max_length=255)
    amount: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_date_range(self) -> "InternshipCreateRequest":
        if self.end_date < self.start_date:
            raise ValueError("end_date must be greater than or equal to start_date")

        return self


class CurrentStateResponse(BaseModel):
    """Response schema for an internship workflow state."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str


class InternshipResponse(BaseModel):
    """Response schema for internship records."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    org_name: str
    sector: str
    address: str
    city: str
    org_phone: str | None
    web: str | None
    start_date: date
    end_date: date
    schedule: str
    days: str
    modality: Modality
    internship_address: str
    act_description: str
    ben_description: str
    amount: int | None
    upload_date: datetime
    status_id: int | None
    user_id: int | None
