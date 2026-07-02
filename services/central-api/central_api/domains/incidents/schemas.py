"""Strict request and response contracts for incident management."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from trackflow_incidents import Branch, IncidentCategory, IncidentOrigin, IncidentStatus


class APIModel(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True, str_strip_whitespace=True)


class IncidentCreate(APIModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=5, max_length=5000)
    category: IncidentCategory
    origin: IncidentOrigin
    branch: Branch


class IncidentStatusUpdate(APIModel):
    status: IncidentStatus


class IncidentRead(IncidentCreate):
    id: int
    status: IncidentStatus
    created_at: datetime
    updated_at: datetime
    created_by_user_uuid: str | None


class IncidentPage(APIModel):
    items: list[IncidentRead]
    total: int
    limit: int
    offset: int


class IncidentSummary(APIModel):
    total: int
    by_status: dict[str, int]
    by_category: dict[str, int]
    by_origin: dict[str, int]
    by_branch: dict[str, int]
