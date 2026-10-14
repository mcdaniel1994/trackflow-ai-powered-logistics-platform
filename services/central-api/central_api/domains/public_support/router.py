"""Fixed service-authenticated public policy endpoint, never a public internal API proxy."""

import asyncio
import logging
import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from ...core.config import Settings, get_settings
from .limits import AdmissionLimit, SupportAdmission
from .schemas import SupportAnswer, SupportQuery
from .service import answer_public_question

logger = logging.getLogger(__name__)
router = APIRouter(tags=["public-support"])


def gateway_settings(request: Request, settings: Annotated[Settings, Depends(get_settings)]) -> Settings:
    expected = settings.website_gateway_secret.get_secret_value()
    if not expected or not secrets.compare_digest(
        request.headers.get("x-website-gateway-secret", "").encode(), expected.encode()
    ):
        raise HTTPException(403, "Not authorized")
    if not settings.public_support_enabled or not settings.openai_api_key or not settings.deepseek_api_key:
        raise HTTPException(503, "Public support is unavailable")
    return settings


@router.post("/public-support/query", response_model=SupportAnswer)
async def query_public_support(
    payload: SupportQuery,
    request: Request,
    settings: Annotated[Settings, Depends(gateway_settings)],
) -> SupportAnswer:
    admission: SupportAdmission = request.app.state.public_support_admission
    try:
        admission.acquire()
    except AdmissionLimit as exc:
        raise HTTPException(
            429, "Public support is busy. Please try again later.", headers={"Retry-After": "60"}
        ) from exc

    def run() -> SupportAnswer:
        try:
            return answer_public_question(payload, settings)
        finally:
            # Keep capacity reserved after a deadline until the bounded I/O really ends.
            admission.release()

    worker = asyncio.create_task(asyncio.to_thread(run))
    # Consume a late exception without exposing provider detail or orphan-task warnings.
    worker.add_done_callback(lambda task: task.exception() if not task.cancelled() else None)
    try:
        return await asyncio.wait_for(asyncio.shield(worker), timeout=30.0)
    except TimeoutError as exc:
        logger.warning("public_support.query outcome=timeout")
        raise HTTPException(504, "Public support timed out. Please try again later.") from exc
    except Exception as exc:
        logger.warning("public_support.query outcome=dependency_failure error_type=%s", type(exc).__name__)
        raise HTTPException(503, "Public support is temporarily unavailable") from exc
