from pydantic import BaseModel, Field


class UpdateSettingsRequest(BaseModel):
    # Relevance scores are cosine similarities of normalized embeddings, so 0..1.
    # None clears the saved value and falls back to RETRIEVAL_THRESHOLD / the default.
    retrieval_threshold: float | None = Field(
        ...,
        ge=0,
        le=1,
        description="Minimum score for an ADR to be returned, or null to use the default.",
    )
