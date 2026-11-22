from pydantic import BaseModel, Field, field_validator, model_validator


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


class AdrSection(BaseModel):
    """One section of the team's ADR format."""

    title: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="The section's `## ` heading, e.g. 'Decision'.",
    )
    purpose: str = Field(
        default="",
        max_length=500,
        description=(
            "What the section is for, used by the quality review to judge whether its "
            "content does its job. Left empty, the review judges it by its heading."
        ),
    )
    required: bool = Field(
        default=False,
        description="Whether the review reports an error when the section is missing or empty.",
    )

    @field_validator("title", "purpose")
    @classmethod
    def _strip(cls, value: str) -> str:
        """Trim before anything else looks at it.

        min_length alone lets "   " through, which then becomes a blank heading and,
        keyed by its trimmed title, collides with any other blank one.
        """
        return value.strip()

    @field_validator("title")
    @classmethod
    def _title_not_blank(cls, value: str) -> str:
        if not value:
            raise ValueError("A section title is required.")
        return value

    @field_validator("title")
    @classmethod
    def _title_leading_capital(cls, value: str) -> str:
        """Uppercase the first character so headings look consistent however they were typed.

        Only the first character: str.capitalize() lowercases the rest, which would turn
        "API Conventions" into "Api conventions". A title starting with a digit or symbol
        is left as it is, since upper() is a no-op there.
        """
        return value[:1].upper() + value[1:]


class UpdateAdrFormatRequest(BaseModel):
    # None deletes the saved format, going back to the default sections.
    sections: list[AdrSection] | None = Field(
        ...,
        description="The sections, in the order an ADR has them, or null to use the default.",
    )

    @model_validator(mode="after")
    def _no_duplicate_titles(self) -> "UpdateAdrFormatRequest":
        """Reject two sections whose titles differ only by case or surrounding space.

        The review matches an ADR's headings to sections ignoring case, and the create
        form keys a section's content by its lowercased title, so near-duplicates are
        indistinguishable downstream: one section's text silently lands in the other.
        The format page already blocks this, but the API is reachable without it.
        """
        if self.sections is None:
            return self
        seen: set[str] = set()
        for section in self.sections:
            key = section.title.lower()
            if key in seen:
                raise ValueError(f"Two sections are titled {section.title!r}.")
            seen.add(key)
        return self
