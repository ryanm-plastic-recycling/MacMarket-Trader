"""Open-lifecycle helpers for paper options structures."""

from __future__ import annotations

from typing import TYPE_CHECKING

from macmarket_trader.domain.schemas import OptionPaperOpenStructureResponse, OptionPaperStructureInput

if TYPE_CHECKING:
    from macmarket_trader.storage.repositories import OptionPaperRepository


def open_paper_option_structure(
    *,
    app_user_id: int,
    structure: OptionPaperStructureInput,
    repository: "OptionPaperRepository",
) -> OptionPaperOpenStructureResponse:
    """Open a paper-only options structure without touching equity flows."""

    return repository.open_structure(app_user_id=app_user_id, structure=structure)
