"""Close-lifecycle helpers for paper options structures."""

from __future__ import annotations

import math
from datetime import timezone, datetime
from typing import TYPE_CHECKING

from macmarket_trader.domain.schemas import (
    OptionPaperCloseLegInput,
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


def _validated_settlement_price(value: float) -> float:
    if isinstance(value, bool):
        raise OptionPaperCloseError("invalid_underlying_settlement_price", status_code=400)
    try:
        normalized = float(value)
    except (TypeError, ValueError) as exc:
        raise OptionPaperCloseError("invalid_underlying_settlement_price", status_code=400) from exc
    if not math.isfinite(normalized) or normalized <= 0:
        raise OptionPaperCloseError("invalid_underlying_settlement_price", status_code=400)
    return round(normalized, 10)


def _expiration_intrinsic_value(*, right: str, strike: float, underlying_price: float) -> float:
    normalized_right = str(right or "").strip().lower()
    if normalized_right == "call":
        return round(max(underlying_price - float(strike), 0.0), 10)
    if normalized_right == "put":
        return round(max(float(strike) - underlying_price, 0.0), 10)
    raise OptionPaperCloseError("invalid_option_right")


def settle_paper_option_expiration(
    *,
    app_user_id: int,
    position_id: int,
    confirmation: str,
    underlying_settlement_price: float,
    commission_per_contract: float,
    repository: "OptionPaperRepository",
    notes: str = "",
) -> OptionPaperCloseStructureResponse:
    """Manually settle an expired paper-only options structure from intrinsic values."""

    if str(confirmation or "").strip() != "SETTLE":
        raise OptionPaperCloseError("settlement_confirmation_required", status_code=400)
    settlement_price = _validated_settlement_price(underlying_settlement_price)
    position = repository.get_position(position_id=position_id, app_user_id=app_user_id)
    if position is None:
        raise OptionPaperCloseError("option_position_not_found", status_code=404)
    if position.status != "open":
        raise OptionPaperCloseError("option_position_not_open")
    if position.expiration is None:
        raise OptionPaperCloseError("expiration_date_required_for_settlement")
    if position.expiration >= datetime.now(timezone.utc).date():
        raise OptionPaperCloseError("option_position_not_expired")
    if not position.legs:
        raise OptionPaperCloseError("option_position_legs_not_found")
    if isinstance(commission_per_contract, bool):
        raise OptionPaperCloseError("invalid_commission_per_contract")
    try:
        normalized_commission = float(commission_per_contract)
    except (TypeError, ValueError) as exc:
        raise OptionPaperCloseError("invalid_commission_per_contract") from exc
    if not math.isfinite(normalized_commission) or normalized_commission < 0:
        raise OptionPaperCloseError("invalid_commission_per_contract")

    leg_closes = [
        OptionPaperCloseLegInput(
            position_leg_id=leg.id,
            exit_premium=_expiration_intrinsic_value(
                right=leg.right,
                strike=leg.strike,
                underlying_price=settlement_price,
            ),
        )
        for leg in position.legs
    ]
    settlement_notes = (
        f"paper-only expiration settlement at underlying={settlement_price}. "
        "No broker action, exercise, assignment, roll, or live order."
    )
    if notes:
        settlement_notes = f"{settlement_notes} {notes}"
    return repository.close_structure_manual(
        app_user_id=app_user_id,
        position_id=position_id,
        leg_closes=leg_closes,
        commission_per_contract=round(normalized_commission, 10),
        notes=settlement_notes,
        settlement_mode="expiration",
    )
