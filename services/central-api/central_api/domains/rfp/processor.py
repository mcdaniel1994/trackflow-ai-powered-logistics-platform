"""Resumable RFP stage runner used by the independent Celery consumer."""

from pipelines.rag import RagConfig  # type: ignore[import-untyped]
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

from ...core.config import Settings
from ...db.session import get_engine
from ..rag.config import build_rag_config
from .approval import start_ticket_approval
from .config import build_rfp_config, is_rfp_generation_configured
from .errors import DeterministicRfpProcessingError, RetryableRfpProcessingError
from .generation import run_generation_for_ticket
from .intake import run_intake_for_ticket
from .repository import RfpRepository


def _status(ticket_id: str) -> str:
    try:
        with Session(get_engine()) as session:
            ticket = RfpRepository(session).get(ticket_id)
            if ticket is None:
                raise DeterministicRfpProcessingError("RFP ticket not found")
            return ticket.status
    except SQLAlchemyError as exc:
        raise RetryableRfpProcessingError("RFP state lookup failed") from exc


def process_rfp_ticket(ticket_id: str, settings: Settings) -> str:
    """Resume from durable ticket state and return the resulting safe status."""
    config = build_rfp_config(settings)
    generation_enabled = is_rfp_generation_configured(settings)
    rag_config: RagConfig | None = build_rag_config(settings) if generation_enabled else None

    for _ in range(4):
        status = _status(ticket_id)
        if status == "analyzing":
            run_intake_for_ticket(ticket_id, config, env=settings.app_env, chain=False, raise_errors=True)
        elif status == "drafting" and rag_config is not None:
            run_generation_for_ticket(
                ticket_id,
                rag_config,
                config.max_iterations,
                env=settings.app_env,
                raise_errors=True,
            )
        elif status == "under_evaluation" and rag_config is not None:
            start_ticket_approval(
                ticket_id,
                settings,
                rag_config,
                config.max_iterations,
                env=settings.app_env,
                raise_errors=True,
            )
        else:
            return status
    return _status(ticket_id)
