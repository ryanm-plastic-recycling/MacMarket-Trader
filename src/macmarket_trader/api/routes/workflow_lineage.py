from __future__ import annotations

from typing import Any


def extract_recommendation_strategy(payload: dict[str, Any] | None) -> str | None:
    data = payload or {}
    workflow = data.get("workflow") if isinstance(data.get("workflow"), dict) else {}
    ranking = workflow.get("ranking_provenance") if isinstance(workflow.get("ranking_provenance"), dict) else {}

    for value in (
        workflow.get("source_strategy"),
        ranking.get("strategy"),
        data.get("strategy"),
        data.get("setup_type"),
    ):
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def extract_recommendation_key_levels(payload: dict[str, Any] | None) -> dict[str, Any]:
    data = payload or {}
    entry = data.get("entry") if isinstance(data.get("entry"), dict) else None
    invalidation = data.get("invalidation") if isinstance(data.get("invalidation"), dict) else None
    targets = data.get("targets") if isinstance(data.get("targets"), dict) else None
    return {
        "entry": entry,
        "invalidation": invalidation,
        "targets": targets,
    }
