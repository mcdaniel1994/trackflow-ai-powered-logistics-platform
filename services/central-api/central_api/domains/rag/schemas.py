"""Request/response contracts for the RAG knowledge query endpoint.

The response carries only the model-generated answer string. Retrieved chunks, similarity
scores, and source metadata are never exposed to the client (they are logged server-side).
"""

from pydantic import BaseModel, ConfigDict, Field, field_validator


class APIModel(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class QueryRequest(APIModel):
    """A single natural-language question from the commercial team."""

    question: str = Field(min_length=1, max_length=1000)

    @field_validator("question")
    @classmethod
    def not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("question must not be blank")
        return stripped


class QueryResponse(APIModel):
    """The model-generated answer — never raw retrieval output."""

    answer: str
