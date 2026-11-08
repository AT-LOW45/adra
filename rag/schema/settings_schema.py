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


class CalibrateRequest(BaseModel):
    """Two sets of coding tasks: ones the ADRs cover, and ones they deliberately don't.

    Scores alone can't say where the threshold belongs — only the person who wrote the
    ADRs knows which side a task should fall on. That labelling is the whole method.
    """

    genuine: list[str] = Field(
        ...,
        min_length=1,
        description="Coding tasks an ADR covers. These should be retrieved.",
    )
    unrelated: list[str] = Field(
        ...,
        min_length=1,
        description=(
            "Coding tasks no ADR covers. These should return nothing. They must be "
            "realistic coding tasks, not off-topic text: an agent never asks for a "
            "cookie recipe, but it does ask for a CSV parser. Off-topic text scores "
            "far lower and suggests a threshold that lets real tasks through."
        ),
    )
