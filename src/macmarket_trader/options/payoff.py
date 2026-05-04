"""Pure options payoff math helpers for read-only replay previews."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Literal, cast

OptionAction = Literal["buy", "sell"]
OptionRight = Literal["call", "put"]
OptionStructureType = Literal[
    "long_call",
    "long_put",
    "vertical_debit_spread",
    "iron_condor",
    "custom_defined_risk",
]


class OptionPayoffValidationError(ValueError):
    """Raised when a payoff input is invalid or unsupported."""


@dataclass(frozen=True, slots=True)
class OptionLegInput:
    action: OptionAction
    right: OptionRight
    strike: float
    premium: float
    quantity: int = 1
    multiplier: int = 100
    label: str | None = None


@dataclass(frozen=True, slots=True)
class OptionLegPayoff:
    label: str
    payoff: float


@dataclass(frozen=True, slots=True)
class OptionPayoffPoint:
    underlying_price: float
    total_payoff: float
    leg_payoffs: tuple[OptionLegPayoff, ...]


@dataclass(frozen=True, slots=True)
class OptionPayoffResult:
    structure_type: OptionStructureType | None
    net_debit: float | None
    net_credit: float | None
    max_profit: float | None
    max_loss: float | None
    breakevens: tuple[float, ...]
    payoff_points: tuple[OptionPayoffPoint, ...]
    legs: tuple[OptionLegInput, ...]
    blocked_reason: str | None
    is_defined_risk: bool
    warnings: tuple[str, ...]

    @property
    def is_blocked(self) -> bool:
        return self.blocked_reason is not None


def calculate_option_leg_payoff(leg: OptionLegInput, underlying_price: float) -> float:
    """Return expiration payoff for one option leg."""

    normalized_leg = _normalize_leg(leg)
    price = _require_price(underlying_price, field_name="underlying_price")
    intrinsic = _intrinsic_value(
        right=normalized_leg.right,
        strike=normalized_leg.strike,
        underlying_price=price,
    )
    per_share_payoff = intrinsic - normalized_leg.premium
    if normalized_leg.action == "sell":
        per_share_payoff = normalized_leg.premium - intrinsic
    return _clean_number(per_share_payoff * normalized_leg.quantity * normalized_leg.multiplier)


def analyze_option_structure(
    legs: list[OptionLegInput] | tuple[OptionLegInput, ...],
    structure_type: OptionStructureType | None = None,
    underlying_prices: list[float] | tuple[float, ...] | None = None,
) -> OptionPayoffResult:
    """Analyze a supported options structure without persistence or routing."""

    try:
        normalized_legs = _normalize_legs(legs)
        resolved_structure_type = structure_type or _infer_structure_type(normalized_legs)

        if resolved_structure_type == "long_call":
            return _analyze_long_option(
                normalized_legs,
                structure_type=resolved_structure_type,
                expected_right="call",
                underlying_prices=underlying_prices,
            )
        if resolved_structure_type == "long_put":
            return _analyze_long_option(
                normalized_legs,
                structure_type=resolved_structure_type,
                expected_right="put",
                underlying_prices=underlying_prices,
            )
        if resolved_structure_type == "vertical_debit_spread":
            return analyze_vertical_debit_spread(normalized_legs, underlying_prices=underlying_prices)
        if resolved_structure_type == "iron_condor":
            return analyze_iron_condor(normalized_legs, underlying_prices=underlying_prices)
        if resolved_structure_type == "custom_defined_risk":
            return _blocked_result(
                structure_type=resolved_structure_type,
                legs=normalized_legs,
                blocked_reason="custom_defined_risk_not_yet_supported",
            )

        return _blocked_result(
            structure_type=resolved_structure_type,
            legs=normalized_legs,
            blocked_reason="unsupported_structure_type",
        )
    except OptionPayoffValidationError as exc:
        return _blocked_result(
            structure_type=structure_type,
            legs=tuple(legs),
            blocked_reason=str(exc),
        )


def analyze_vertical_debit_spread(
    legs: list[OptionLegInput] | tuple[OptionLegInput, ...],
    underlying_prices: list[float] | tuple[float, ...] | None = None,
) -> OptionPayoffResult:
    """Analyze a call or put vertical debit spread."""

    try:
        normalized_legs = _normalize_legs(legs)
        if len(normalized_legs) != 2:
            raise OptionPayoffValidationError("vertical_debit_spread_requires_two_legs")
        buy_legs = [leg for leg in normalized_legs if leg.action == "buy"]
        sell_legs = [leg for leg in normalized_legs if leg.action == "sell"]
        if len(buy_legs) != 1 or len(sell_legs) != 1:
            raise OptionPayoffValidationError(
                "vertical_debit_spread_requires_one_long_leg_and_one_short_leg"
            )
        long_leg = buy_legs[0]
        short_leg = sell_legs[0]
        if long_leg.right != short_leg.right:
            raise OptionPayoffValidationError("vertical_debit_spread_requires_matching_rights")
        quantity = _require_matching_quantity(normalized_legs)
        multiplier = _require_matching_multiplier(normalized_legs)
        right = long_leg.right

        if right == "call":
            if long_leg.strike >= short_leg.strike:
                raise OptionPayoffValidationError(
                    "call_vertical_debit_requires_long_lower_strike"
                )
            width = short_leg.strike - long_leg.strike
            breakevens = (_clean_number(long_leg.strike + long_leg.premium - short_leg.premium),)
        else:
            if long_leg.strike <= short_leg.strike:
                raise OptionPayoffValidationError(
                    "put_vertical_debit_requires_long_higher_strike"
                )
            width = long_leg.strike - short_leg.strike
            breakevens = (_clean_number(long_leg.strike - (long_leg.premium - short_leg.premium)),)

        net_debit = _clean_number(long_leg.premium - short_leg.premium)
        if net_debit <= 0:
            raise OptionPayoffValidationError("vertical_debit_requires_positive_net_debit")
        if net_debit > width:
            raise OptionPayoffValidationError("vertical_debit_debit_exceeds_width")

        max_loss = _clean_number(net_debit * quantity * multiplier)
        max_profit = _clean_number((width - net_debit) * quantity * multiplier)
        payoff_points = _build_payoff_points(
            normalized_legs,
            underlying_prices=underlying_prices,
            breakevens=breakevens,
        )
        return OptionPayoffResult(
            structure_type="vertical_debit_spread",
            net_debit=net_debit,
            net_credit=None,
            max_profit=max_profit,
            max_loss=max_loss,
            breakevens=breakevens,
            payoff_points=payoff_points,
            legs=normalized_legs,
            blocked_reason=None,
            is_defined_risk=True,
            warnings=(),
        )
    except OptionPayoffValidationError as exc:
        return _blocked_result(
            structure_type="vertical_debit_spread",
            legs=tuple(legs),
            blocked_reason=str(exc),
        )


def analyze_iron_condor(
    legs: list[OptionLegInput] | tuple[OptionLegInput, ...],
    underlying_prices: list[float] | tuple[float, ...] | None = None,
) -> OptionPayoffResult:
    """Analyze a defined-risk iron condor at expiration."""

    try:
        normalized_legs = _normalize_legs(legs)
        if len(normalized_legs) != 4:
            raise OptionPayoffValidationError("iron_condor_requires_four_legs")
        quantity = _require_matching_quantity(normalized_legs)
        multiplier = _require_matching_multiplier(normalized_legs)

        long_put = _match_single_leg(normalized_legs, action="buy", right="put", reason="iron_condor")
        short_put = _match_single_leg(normalized_legs, action="sell", right="put", reason="iron_condor")
        short_call = _match_single_leg(normalized_legs, action="sell", right="call", reason="iron_condor")
        long_call = _match_single_leg(normalized_legs, action="buy", right="call", reason="iron_condor")

        if not (long_put.strike < short_put.strike < short_call.strike < long_call.strike):
            raise OptionPayoffValidationError("iron_condor_requires_ordered_strikes")

        put_width = _clean_number(short_put.strike - long_put.strike)
        call_width = _clean_number(long_call.strike - short_call.strike)
        if put_width <= 0 or call_width <= 0:
            raise OptionPayoffValidationError("iron_condor_requires_positive_wing_widths")

        net_credit = _clean_number(
            short_put.premium
            + short_call.premium
            - long_put.premium
            - long_call.premium
        )
        if net_credit <= 0:
            raise OptionPayoffValidationError("iron_condor_requires_positive_net_credit")

        widest_wing = max(put_width, call_width)
        if net_credit >= widest_wing:
            raise OptionPayoffValidationError("iron_condor_credit_must_be_less_than_widest_wing")

        breakevens = (
            _clean_number(short_put.strike - net_credit),
            _clean_number(short_call.strike + net_credit),
        )
        warnings: tuple[str, ...] = ()
        if put_width != call_width:
            warnings = ("unequal_wing_widths",)

        payoff_points = _build_payoff_points(
            normalized_legs,
            underlying_prices=underlying_prices,
            breakevens=breakevens,
        )
        return OptionPayoffResult(
            structure_type="iron_condor",
            net_debit=None,
            net_credit=net_credit,
            max_profit=_clean_number(net_credit * quantity * multiplier),
            max_loss=_clean_number((widest_wing - net_credit) * quantity * multiplier),
            breakevens=breakevens,
            payoff_points=payoff_points,
            legs=normalized_legs,
            blocked_reason=None,
            is_defined_risk=True,
            warnings=warnings,
        )
    except OptionPayoffValidationError as exc:
        return _blocked_result(
            structure_type="iron_condor",
            legs=tuple(legs),
            blocked_reason=str(exc),
        )


def _analyze_long_option(
    legs: tuple[OptionLegInput, ...],
    *,
    structure_type: Literal["long_call", "long_put"],
    expected_right: OptionRight,
    underlying_prices: list[float] | tuple[float, ...] | None,
) -> OptionPayoffResult:
    if len(legs) != 1:
        raise OptionPayoffValidationError(f"{structure_type}_requires_one_leg")
    leg = legs[0]
    if leg.action != "buy" or leg.right != expected_right:
        raise OptionPayoffValidationError(f"{structure_type}_requires_one_long_{expected_right}_leg")

    breakeven = (
        _clean_number(leg.strike + leg.premium)
        if expected_right == "call"
        else _clean_number(leg.strike - leg.premium)
    )
    max_profit = None
    warnings: tuple[str, ...] = ()
    if expected_right == "call":
        warnings = ("max_profit_unbounded",)
    else:
        max_profit = _clean_number((leg.strike - leg.premium) * leg.quantity * leg.multiplier)

    payoff_points = _build_payoff_points(
        legs,
        underlying_prices=underlying_prices,
        breakevens=(breakeven,),
    )
    return OptionPayoffResult(
        structure_type=structure_type,
        net_debit=leg.premium,
        net_credit=None,
        max_profit=max_profit,
        max_loss=_clean_number(leg.premium * leg.quantity * leg.multiplier),
        breakevens=(breakeven,),
        payoff_points=payoff_points,
        legs=legs,
        blocked_reason=None,
        is_defined_risk=True,
        warnings=warnings,
    )


def _blocked_result(
    *,
    structure_type: OptionStructureType | None,
    legs: tuple[OptionLegInput, ...],
    blocked_reason: str,
) -> OptionPayoffResult:
    return OptionPayoffResult(
        structure_type=structure_type,
        net_debit=None,
        net_credit=None,
        max_profit=None,
        max_loss=None,
        breakevens=(),
        payoff_points=(),
        legs=legs,
        blocked_reason=blocked_reason,
        is_defined_risk=False,
        warnings=(),
    )


def _normalize_legs(
    legs: list[OptionLegInput] | tuple[OptionLegInput, ...],
) -> tuple[OptionLegInput, ...]:
    if not legs:
        raise OptionPayoffValidationError("legs_are_required")
    return tuple(_normalize_leg(leg) for leg in legs)


def _normalize_leg(leg: OptionLegInput) -> OptionLegInput:
    if leg.action not in {"buy", "sell"}:
        raise OptionPayoffValidationError("invalid_leg_action")
    if leg.right not in {"call", "put"}:
        raise OptionPayoffValidationError("invalid_leg_right")

    strike = _require_positive_number(leg.strike, field_name="strike")
    premium = _require_non_negative_number(leg.premium, field_name="premium")
    quantity = _require_positive_int(leg.quantity, field_name="quantity")
    multiplier = _require_positive_int(leg.multiplier, field_name="multiplier")

    label = leg.label.strip() if isinstance(leg.label, str) and leg.label.strip() else None
    return OptionLegInput(
        action=cast(OptionAction, leg.action),
        right=cast(OptionRight, leg.right),
        strike=strike,
        premium=premium,
        quantity=quantity,
        multiplier=multiplier,
        label=label,
    )


def _intrinsic_value(*, right: OptionRight, strike: float, underlying_price: float) -> float:
    if right == "call":
        return _clean_number(max(underlying_price - strike, 0.0))
    return _clean_number(max(strike - underlying_price, 0.0))


def _build_payoff_points(
    legs: tuple[OptionLegInput, ...],
    *,
    underlying_prices: list[float] | tuple[float, ...] | None,
    breakevens: tuple[float, ...],
) -> tuple[OptionPayoffPoint, ...]:
    price_grid = _normalize_underlying_prices(
        underlying_prices if underlying_prices is not None else _default_underlying_prices(legs, breakevens)
    )
    points: list[OptionPayoffPoint] = []
    for price in price_grid:
        leg_payoffs = tuple(
            OptionLegPayoff(
                label=_leg_label(leg, index),
                payoff=calculate_option_leg_payoff(leg, price),
            )
            for index, leg in enumerate(legs, start=1)
        )
        total_payoff = _clean_number(sum(item.payoff for item in leg_payoffs))
        points.append(
            OptionPayoffPoint(
                underlying_price=price,
                total_payoff=total_payoff,
                leg_payoffs=leg_payoffs,
            )
        )
    return tuple(points)


def _normalize_underlying_prices(
    underlying_prices: list[float] | tuple[float, ...],
) -> tuple[float, ...]:
    if not underlying_prices:
        raise OptionPayoffValidationError("underlying_prices_are_required")
    normalized = {_require_price(price, field_name="underlying_price") for price in underlying_prices}
    return tuple(sorted(normalized))


def _default_underlying_prices(
    legs: tuple[OptionLegInput, ...],
    breakevens: tuple[float, ...],
) -> tuple[float, ...]:
    strikes = sorted(leg.strike for leg in legs)
    minimum_strike = strikes[0]
    maximum_strike = strikes[-1]
    span = max(maximum_strike - minimum_strike, 1.0)
    candidates = [
        0.0,
        max(minimum_strike - span, 0.0),
        *strikes,
        *(value for value in breakevens if value >= 0),
        maximum_strike + span,
    ]
    normalized = {_require_price(value, field_name="underlying_price") for value in candidates}
    return tuple(sorted(normalized))


def _infer_structure_type(legs: tuple[OptionLegInput, ...]) -> OptionStructureType:
    if len(legs) == 1:
        leg = legs[0]
        if leg.action == "sell":
            raise OptionPayoffValidationError("naked_short_option_not_supported")
        if leg.right == "call":
            return "long_call"
        return "long_put"
    if len(legs) == 2:
        return "vertical_debit_spread"
    if len(legs) == 4:
        return "iron_condor"
    raise OptionPayoffValidationError("unsupported_structure_type")


def _match_single_leg(
    legs: tuple[OptionLegInput, ...],
    *,
    action: OptionAction,
    right: OptionRight,
    reason: str,
) -> OptionLegInput:
    matches = [leg for leg in legs if leg.action == action and leg.right == right]
    if len(matches) != 1:
        raise OptionPayoffValidationError(
            f"{reason}_requires_one_{action}_{right}_leg"
        )
    return matches[0]


def _require_matching_quantity(legs: tuple[OptionLegInput, ...]) -> int:
    quantities = {leg.quantity for leg in legs}
    if len(quantities) != 1:
        raise OptionPayoffValidationError("structure_requires_matching_quantities")
    return next(iter(quantities))


def _require_matching_multiplier(legs: tuple[OptionLegInput, ...]) -> int:
    multipliers = {leg.multiplier for leg in legs}
    if len(multipliers) != 1:
        raise OptionPayoffValidationError("structure_requires_matching_multipliers")
    return next(iter(multipliers))


def _leg_label(leg: OptionLegInput, index: int) -> str:
    if leg.label:
        return leg.label
    return f"Leg {index}: {leg.action} {leg.right} {leg.strike:g}"


def _require_price(value: float, *, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise OptionPayoffValidationError(f"invalid_{field_name}")
    numeric = float(value)
    if not isfinite(numeric) or numeric < 0:
        raise OptionPayoffValidationError(f"invalid_{field_name}")
    return _clean_number(numeric)


def _require_positive_number(value: float, *, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise OptionPayoffValidationError(f"invalid_{field_name}")
    numeric = float(value)
    if not isfinite(numeric) or numeric <= 0:
        raise OptionPayoffValidationError(f"invalid_{field_name}")
    return _clean_number(numeric)


def _require_non_negative_number(value: float, *, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise OptionPayoffValidationError(f"invalid_{field_name}")
    numeric = float(value)
    if not isfinite(numeric) or numeric < 0:
        raise OptionPayoffValidationError(f"invalid_{field_name}")
    return _clean_number(numeric)


def _require_positive_int(value: int, *, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise OptionPayoffValidationError(f"invalid_{field_name}")
    return value


def _clean_number(value: float, *, digits: int = 10) -> float:
    numeric = float(value)
    if not isfinite(numeric):
        raise OptionPayoffValidationError("non_finite_numeric_output")
    rounded = round(numeric, digits)
    if abs(rounded) < 10 ** (-digits):
        return 0.0
    return rounded
