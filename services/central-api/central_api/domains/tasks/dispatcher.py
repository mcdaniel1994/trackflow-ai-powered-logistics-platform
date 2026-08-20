"""Producer-side helpers that keep Celery details out of the RFP service."""

from .celery_tasks import process_rfp_task


def enqueue_rfp_processing(ticket_id: str) -> None:
    """Publish only the durable ticket identifier and reuse it as the task ID."""
    process_rfp_task.apply_async(args=[ticket_id], task_id=ticket_id, queue="rfp")
