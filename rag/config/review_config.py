from schema.knowledgebase_schema import SectionSpec

# The default ADR format, used until a team saves its own (service/settings_service.py,
# adr_format()). The review checks consume whatever catalog they're handed, so they don't
# change when a saved format replaces this.
DEFAULT_SECTIONS: list[SectionSpec] = [
    {"title": "Status", "required": True, "purpose": "one of Proposed / Accepted / Deprecated / Superseded."},
    {"title": "Scope", "required": True, "purpose": "names a real system or component boundary."},
    {"title": "Context", "required": False, "purpose": "describes the actual situation or problem that motivated the decision."},
    {"title": "Decision", "required": True, "purpose": "states a concrete decision — what was chosen (ideally why)."},
    {"title": "Consequences", "required": False, "purpose": "describes real outcomes or trade-offs."},
]

# An ADR longer than this (whitespace-separated words) earns an advisory "consider trimming".
MAX_WORDS = 1500
