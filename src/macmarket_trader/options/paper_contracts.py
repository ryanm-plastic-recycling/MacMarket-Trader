"""Internal options paper-persistence contract helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from macmarket_trader.domain.schemas import OptionPaperLegInput, OptionPaperStructureInput
from macmarket_trader.options.payoff import OptionLegInput, analyze_option_structure


class OptionPaperContractError(ValueError):
    """Raised when an options paper structure is invalid for persistence."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True, slots=True)
class PreparedOptionPaperStructure:
    structure_type: str
    underlying_symbol: str
    expiration: date
    legs: tuple[OptionPaperLegInput, ...]
    net_debit: float | None
    net_credit: float | None
    max_profit: float | None
    max_loss: float | None
    breakevens: tuple[float, ...]
    warnings: tuple[str, ...]


def prepare_option_paper_structure(
    structure: OptionPaperStructureInput,
) -> PreparedOptionPaperStructure:
    """Normalize and validate a supported options structure for persistence."""

    market_mode = getattr(structure.market_mode, "value", structure.market_mode)
    if market_mode != "options":
        raise OptionPaperContractError("options_market_mode_required")

    underlying_symbol = structure.underlying_symbol.strip().upper()
    if not underlying_symbol:
        raise OptionPaperContractError("underlying_symbol_required")
    if not structure.legs:
        raise OptionPaperContractError("legs_are_required")

    normalized_legs = tuple(
        OptionPaperLegInput(
            action=leg.action,
            right=leg.right,
            strike=leg.strike,
            expiration=leg.expiration,
            premium=leg.premium,
            quantity=leg.quantity,
            multiplier=leg.multiplier,
            label=leg.label.strip() if isinstance(leg.label, str) and leg.label.strip() else None,
        )
        for leg in structure.legs
    )

    if len(normalized_legs) == 1 and normalized_legs[0].action == "sell":
        raise OptionPaperContractError("naked_short_option_not_supported")

    expirations = {leg.expiration for leg in normalized_legs}
    if structure.expiration is not None:
        if any(leg_expiration != structure.expiration for leg_expiration in expirations):
            raise OptionPaperContractError("structure_expiration_mismatch")
        resolved_expiration = structure.expiration
    else:
        if len(expirations) != 1:
            raise OptionPaperContractError("multi_expiration_structures_not_supported")
        resolved_expiration = next(iter(expirations))

    payoff_result = analyze_option_structure(
        [
            OptionLegInput(
                action=leg.action,
                right=leg.right,
                strike=leg.strike,
                premium=leg.premium,
                quantity=leg.quantity,
                multiplier=leg.multiplier,
                label=leg.label,
            )
            for leg in normalized_legs
        ],
        structure_type=structure.structure_type,
    )
    if payoff_result.is_blocked:
        raise OptionPaperContractError(payoff_result.blocked_reason or "invalid_option_structure")
    if not payoff_result.is_defined_risk:
        raise OptionPaperContractError("defined_risk_structure_required")

    return PreparedOptionPaperStructure(
        structure_type=structure.structure_type,
        underlying_symbol=underlying_symbol,
        expiration=resolved_expiration,
        legs=normalized_legs,
        net_debit=payoff_result.net_debit,
        net_credit=payoff_result.net_credit,
        max_profit=payoff_result.max_profit,
        max_loss=payoff_result.max_loss,
        breakevens=tuple(payoff_result.breakevens),
        warnings=tuple(payoff_result.warnings),
    )
