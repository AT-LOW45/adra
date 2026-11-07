from typing import Literal, TypedDict
from pydantic import BaseModel, Field

Severity = Literal["warning", "error"]


class SectionSpec(TypedDict):
    """One ADR section's definition. `purpose` is LLM-facing guidance for the semantic
    pass; `required` drives the structural checks. This is the single source of truth
    both review passes read from, instead of each hardcoding its own section list."""

    title: str
    purpose: str
    required: bool


class ReviewResultSchema(BaseModel):
    severity: Severity = Field(
        description="'error' for issues that undermine the ADR or would mislead code generation; 'warning' for advisory concerns."
    )
    section: str = Field(
        description="The ADR section the finding relates to (e.g. 'Decision'), or 'document' for whole-document issues."
    )
    message: str = Field(description="One concise, actionable sentence describing the issue.")


class ReviewOutputSchema(BaseModel):
    """Container so the LLM can return a list via with_structured_output."""

    findings: list[ReviewResultSchema] = Field(
        description="All issues found. Empty list if the ADR is sound."
    )


class ReviewResponseSchema(BaseModel):
    """API response: the findings plus whether the semantic (LLM) pass actually ran.

    Separate from ReviewOutputSchema (which the LLM fills) so `llm_ok` isn't something
    the model is asked to produce."""

    findings: list[ReviewResultSchema]
    llm_ok: bool = Field(
        default=True,
        description="False when the semantic (LLM) pass errored — findings are structural-only.",
    )


class SearchPreviewRequest(BaseModel):
    """A coding task to run through retrieval, as an agent would phrase it."""

    query: str = Field(
        ...,
        min_length=1,
        description="The coding task to test, e.g. 'add an endpoint to list zones'.",
    )
    retrieval_threshold: float | None = Field(
        default=None,
        ge=0,
        le=1,
        description=(
            "Evaluate at this threshold instead of the saved one, so a value can be "
            "tried before it is saved. None uses the threshold agents currently get."
        ),
    )
