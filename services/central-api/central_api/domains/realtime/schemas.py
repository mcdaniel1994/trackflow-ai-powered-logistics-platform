"""Transport-neutral contracts shared by real-time publishers and subscribers."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RealtimeEvent(BaseModel):
    """One process-local event published to a topic."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: int = Field(gt=0)
    event: str = Field(min_length=1, max_length=96)
    data: dict[str, object]


class RfpTicketCreatedEvent(BaseModel):
    """Model-free notification emitted after the initial RFP ticket commit."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ticket_id: str
    rfp_id: str
    client_name: str | None
    client_country: str | None
    services_requested: list[str]
    status: Literal["analyzing"]
    created_at: datetime
