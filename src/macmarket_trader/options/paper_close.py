"""Close-lifecycle helpers for paper options structures."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from macmarket_trader.domain.schemas import (
    OptionPaperCloseStructureRequest,
    OptionPaperCloseStructureResponse,
)

if TYPE_CHECKING:
    from macmarket_trader.storage.repositories import OptionPaperRepository


class OptionPaperCloseError(ValueError):
    """Raised when an options paper close request is invalid."""

    def __init__(self, reason: str, *, status_code: int = 409) -> None:
        super().__init__(reason)
        self.reason = reason
        self.status_code = status_code


def close_paper_option_structure(
    *,
    app_user_id: int,
    position_id: int,
    req: OptionPaperCloseStructureRequest,
    commission_per_contract: float,
    repository: "OptionPaperRepository",
) -> OptionPaperCloseStructureResponse:
    """Close a paper-only options structure without touching equity flows."""

    settlement_mode = (req.settlement_mode or "").strip().lower() or "manual_close"
    if settlement_mode not in {"manual_close", "expiration"}:
        raise OptionPaperCloseError("invalid_settlement_mode")
    if settlement_mode == "expiration":
        raise OptionPaperCloseError("expiration_settlement_not_yet_supported")
    if isinstance(commission_per_contract, bool):
        raise OptionPaperCloseError("invalid_commission_per_contract")
    try:
        normalized_commission = float(commission_per_contract)
    except (TypeError, ValueError) as exc:
        raise OptionPaperCloseError("invalid_commission_per_contract") from exc
    if not math.isfinite(normalized_commission) or normalized_commission < 0:
        raise OptionPaperCloseError("invalid_commission_per_contract")

    return repository.close_structure_manual(
        app_user_id=app_user_id,
        position_id=position_id,
        leg_closes=req.legs,
        commission_per_contract=round(normalized_commission, 10),
        notes=req.notes or "",
    )
