"""Static event taxonomy used by extraction and explainability layers."""

EVENT_TAGS: dict[str, list[str]] = {
    "earnings": ["guidance", "beat", "miss"],
    "macro": ["cpi", "jobs", "rates", "fed"],
    "corporate": ["m&a", "buyback", "restructure"],
}
