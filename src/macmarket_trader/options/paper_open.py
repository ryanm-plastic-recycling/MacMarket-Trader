"""Open-lifecycle helpers for paper options structures."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from macmarket_trader.domain.schemas import OptionPaperOpenStructureResponse, OptionPaperStructureInput
from macmarket_trader.options.paper_contracts import OptionPaperContractError

if TYPE_CHECKING:
    from macmarket_trader.storage.repositories import OptionPaperRepository


def _validated_commission_per_contract(value: float) -> float:
    if isinstance(value, bool):
        raise OptionPaperContractError("invalid_commission_per_contract")
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise OptionPaperContractError("invalid_commission_per_contract") from exc
    if not math.isfinite(numeric) or numeric < 0:
        raise OptionPaperContractError("invalid_commission_per_contract")
    return round(numeric, 10)


def open_paper_option_structure(
    *,
    app_user_id: int,
    structure: OptionPaperStructureInput,
    commission_per_contract: float,
    repository: "OptionPaperRepository",
) -> OptionPaperOpenStructureResponse:
    """Open a paper-only options structure without touching equity flows."""

    return repository.open_structure(
        app_user_id=app_user_id,
        structure=structure,
        commission_per_contract=_validated_commission_per_contract(commission_per_contract),
    )
