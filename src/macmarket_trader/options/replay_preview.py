"""Read-only options replay preview contract helpers."""

from __future__ import annotations

from typing import Literal, cast

from macmarket_trader.domain.schemas import (
    OptionReplayPreviewLeg,
    OptionReplayPreviewLegPayoff,
    OptionReplayPreviewLegRequest,
    OptionReplayPreviewPoint,
    OptionReplayPreviewRequest,
    OptionReplayPreviewResponse,
)
from macmarket_trader.options.payoff import (
    OptionAction,
    OptionLegInput,
    OptionRight,
    OptionStructureType,
    analyze_option_structure,
)

SUPPORTED_STRUCTURE_TYPES = {
    "long_call",
    "long_put",
    "vertical_debit_spread",
    "iron_condor",
    "custom_defined_risk",
}

DEFAULT_CAVEATS = [
    "Options research only.",
    "Paper-only replay preview.",
    "Not execution support.",
]


def build_options_replay_preview(req: OptionReplayPreviewRequest) -> OptionReplayPreviewResponse:
    structure_type = _normalize_structure_type(req.structure_type)
    if not structure_type:
        return _blocked_response(
            structure_type=None,
            legs=_serialize_request_legs(req.legs),
            underlying_symbol=_normalize_symbol(req.underlying_symbol),
            expiration=req.expiration,
            blocked_reason="structure_type_required",
            notes=req.notes,
            source=_normalize_optional_text(req.source),
            workflow_source=_normalize_optional_text(req.workflow_source),
        )

    if structure_type not in SUPPORTED_STRUCTURE_TYPES:
        return _blocked_response(
            structure_type=structure_type,
            legs=_serialize_request_legs(req.legs),
            underlying_symbol=_normalize_symbol(req.underlying_symbol),
            expiration=req.expiration,
            blocked_reason="unsupported_structure_type",
            status="unsupported",
            notes=req.notes,
            source=_normalize_optional_text(req.source),
            workflow_source=_normalize_optional_text(req.workflow_source),
        )

    normalized_legs, leg_error = _build_leg_inputs(req.legs)
    if leg_error is not None:
        return _blocked_response(
            structure_type=structure_type,
            legs=_serialize_request_legs(req.legs),
            underlying_symbol=_normalize_symbol(req.underlying_symbol),
            expiration=req.expiration,
            blocked_reason=leg_error,
            notes=req.notes,
            source=_normalize_optional_text(req.source),
            workflow_source=_normalize_optional_text(req.workflow_source),
        )

    if len(normalized_legs) == 1 and normalized_legs[0].action == "sell":
        return _blocked_response(
            structure_type=structure_type,
            legs=_serialize_normalized_legs(normalized_legs),
            underlying_symbol=_normalize_symbol(req.underlying_symbol),
            expiration=req.expiration,
            blocked_reason="naked_short_option_not_supported",
            notes=req.notes,
            source=_normalize_optional_text(req.source),
            workflow_source=_normalize_optional_text(req.workflow_source),
        )

    underlying_prices, price_error = _build_underlying_prices(req.underlying_prices)
    if price_error is not None:
        return _blocked_response(
            structure_type=structure_type,
            legs=_serialize_normalized_legs(normalized_legs),
            underlying_symbol=_normalize_symbol(req.underlying_symbol),
            expiration=req.expiration,
            blocked_reason=price_error,
            notes=req.notes,
            source=_normalize_optional_text(req.source),
            workflow_source=_normalize_optional_text(req.workflow_source),
        )

    result = analyze_option_structure(
        normalized_legs,
        structure_type=cast(OptionStructureType, structure_type),
        underlying_prices=underlying_prices,
    )
    status = "ready"
    if result.blocked_reason == "unsupported_structure_type" or result.blocked_reason == "custom_defined_risk_not_yet_supported":
        status = "unsupported"
    elif result.is_blocked:
        status = "blocked"

    return OptionReplayPreviewResponse(
        execution_enabled=False,
        persistence_enabled=False,
        market_mode="options",
        preview_type="expiration_payoff",
        status=status,
        structure_type=result.structure_type,
        underlying_symbol=_normalize_symbol(req.underlying_symbol),
        expiration=req.expiration,
        replay_run_id=None,
        recommendation_id=None,
        order_id=None,
        is_defined_risk=result.is_defined_risk,
        net_debit=result.net_debit,
        net_credit=result.net_credit,
        max_profit=result.max_profit,
        max_loss=result.max_loss,
        breakevens=list(result.breakevens),
        payoff_points=[
            OptionReplayPreviewPoint(
                underlying_price=point.underlying_price,
                total_payoff=point.total_payoff,
                leg_payoffs=[
                    OptionReplayPreviewLegPayoff(label=leg_payoff.label, payoff=leg_payoff.payoff)
                    for leg_payoff in point.leg_payoffs
                ],
            )
            for point in result.payoff_points
        ],
        legs=_serialize_normalized_legs(result.legs),
        warnings=list(result.warnings),
        caveats=list(DEFAULT_CAVEATS),
        blocked_reason=result.blocked_reason,
        operator_disclaimer="Options research only. Paper-only preview. Not execution support.",
        notes=[note for note in req.notes if note.strip()],
        source=_normalize_optional_text(req.source),
        workflow_source=_normalize_optional_text(req.workflow_source),
    )


def _build_leg_inputs(
    legs: list[OptionReplayPreviewLegRequest],
) -> tuple[tuple[OptionLegInput, ...], str | None]:
    if not legs:
        return (), "legs_are_required"

    normalized_legs: list[OptionLegInput] = []
    for leg in legs:
        action = _normalize_keyword(leg.action)
        if action is None:
            return (), "invalid_leg_action"
        right = _normalize_keyword(leg.right)
        if right is None:
            return (), "invalid_leg_right"

        strike = _coerce_float(leg.strike)
        if strike is None:
            return (), "invalid_strike"
        premium = _coerce_float(leg.premium)
        if premium is None:
            return (), "invalid_premium"

        quantity = _coerce_int(leg.quantity, default=1)
        if quantity is None:
            return (), "invalid_quantity"
        multiplier = _coerce_int(leg.multiplier, default=100)
        if multiplier is None:
            return (), "invalid_multiplier"

        normalized_legs.append(
            OptionLegInput(
                action=cast(OptionAction, action),
                right=cast(OptionRight, right),
                strike=strike,
                premium=premium,
                quantity=quantity,
                multiplier=multiplier,
                label=_normalize_optional_text(leg.label),
            )
        )
    return tuple(normalized_legs), None


def _build_underlying_prices(values: list[object] | None) -> tuple[list[float] | None, str | None]:
    if values is None or len(values) == 0:
        return None, None

    normalized: list[float] = []
    for value in values:
        numeric = _coerce_float(value)
        if numeric is None or numeric < 0:
            return None, "invalid_underlying_price"
        normalized.append(numeric)
    return normalized, None


def _serialize_request_legs(legs: list[OptionReplayPreviewLegRequest]) -> list[OptionReplayPreviewLeg]:
    return [
        OptionReplayPreviewLeg(
            action=_normalize_keyword(leg.action),
            right=_normalize_keyword(leg.right),
            strike=_coerce_float(leg.strike),
            premium=_coerce_float(leg.premium),
            quantity=_coerce_int(leg.quantity),
            multiplier=_coerce_int(leg.multiplier),
            label=_normalize_optional_text(leg.label),
        )
        for leg in legs
    ]


def _serialize_normalized_legs(legs: tuple[OptionLegInput, ...]) -> list[OptionReplayPreviewLeg]:
    return [
        OptionReplayPreviewLeg(
            action=leg.action,
            right=leg.right,
            strike=leg.strike,
            premium=leg.premium,
            quantity=leg.quantity,
            multiplier=leg.multiplier,
            label=leg.label,
        )
        for leg in legs
    ]


def _blocked_response(
    *,
    structure_type: str | None,
    legs: list[OptionReplayPreviewLeg],
    underlying_symbol: str | None,
    expiration,
    blocked_reason: str,
    status: str = "blocked",
    notes: list[str],
    source: str | None,
    workflow_source: str | None,
) -> OptionReplayPreviewResponse:
    return OptionReplayPreviewResponse(
        execution_enabled=False,
        persistence_enabled=False,
        market_mode="options",
        preview_type="expiration_payoff",
        status=cast(Literal["ready", "blocked", "unsupported"], status),
        structure_type=structure_type,
        underlying_symbol=underlying_symbol,
        expiration=expiration,
        replay_run_id=None,
        recommendation_id=None,
        order_id=None,
        is_defined_risk=False,
        net_debit=None,
        net_credit=None,
        max_profit=None,
        max_loss=None,
        breakevens=[],
        payoff_points=[],
        legs=legs,
        warnings=[],
        caveats=list(DEFAULT_CAVEATS),
        blocked_reason=blocked_reason,
        operator_disclaimer="Options research only. Paper-only preview. Not execution support.",
        notes=[note for note in notes if note.strip()],
        source=source,
        workflow_source=workflow_source,
    )


def _normalize_structure_type(value: str | None) -> str | None:
    normalized = _normalize_keyword(value)
    return normalized.replace(" ", "_") if normalized else None


def _normalize_keyword(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    return normalized or None


def _normalize_optional_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _normalize_symbol(value: object) -> str | None:
    normalized = _normalize_optional_text(value)
    return normalized.upper() if normalized else None


def _coerce_float(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return None
    return None


def _coerce_int(value: object, *, default: int | None = None) -> int | None:
    if value is None:
        return default
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if value.is_integer():
            return int(value)
        return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return default
        try:
            numeric = float(text)
        except ValueError:
            return None
        if numeric.is_integer():
            return int(numeric)
    return None
