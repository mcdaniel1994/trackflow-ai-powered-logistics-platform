"""Strict public request/response contracts; no operational identity or trace data."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Exchange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=1000)
    answer: str = Field(min_length=1, max_length=4000)


class SupportQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=1000)
    language: Literal["en", "es"]
    policy_country: Literal["US", "ES"] | None = None
    recent_context: list[Exchange] = Field(default_factory=list, max_length=3)

    @field_validator("question")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Enter a question")
        return value.strip()

    @model_validator(mode="after")
    def bounded_context(self) -> "SupportQuery":
        if sum(len(item.question) + len(item.answer) for item in self.recent_context) > 6000:
            raise ValueError("Recent context is too long")
        return self


class SupportAnswer(BaseModel):
    answer: str = Field(min_length=1, max_length=4000)
    outcome: Literal["answered", "clarify", "contact", "rejected", "no_context"]
    contact_path: Literal["/#contact"] = "/#contact"
