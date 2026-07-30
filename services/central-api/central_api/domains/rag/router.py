"""Authenticated HTTP boundary for the RAG knowledge base.

A single POST endpoint. It requires an authenticated Back Office session (and CSRF for cookie
auth, since it triggers paid provider calls), delegates to RagService, and returns only the
generated answer string.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from trackflow_auth import AuthenticatedPrincipal  # type: ignore[import-untyped]

from ...core.config import Settings, get_settings
from ...core.dependencies import write_principal
from .schemas import QueryRequest, QueryResponse
from .service import RagService

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


def rag_service(settings: Annotated[Settings, Depends(get_settings)]) -> RagService:
    return RagService(settings)


@router.post("/query", response_model=QueryResponse)
def query_knowledge_base(
    payload: QueryRequest,
    _principal: Annotated[AuthenticatedPrincipal, Depends(write_principal)],
    service: Annotated[RagService, Depends(rag_service)],
) -> QueryResponse:
    return QueryResponse(answer=service.answer(payload.question))
