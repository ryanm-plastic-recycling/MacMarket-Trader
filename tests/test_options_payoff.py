from math import isfinite

from macmarket_trader.options.payoff import (
    OptionLegInput,
    analyze_iron_condor,
    analyze_option_structure,
    analyze_vertical_debit_spread,
    calculate_option_leg_payoff,
)


def _point_map(result):
    return {point.underlying_price: point.total_payoff for point in result.payoff_points}


def test_long_call_payoff_primitive_and_structure_summary() -> None:
    leg = OptionLegInput(action="buy", right="call", strike=100, premium=2.5)

    assert calculate_option_leg_payoff(leg, 90) == -250.0
    assert calculate_option_leg_payoff(leg, 105) == 250.0

    result = analyze_option_structure([leg], underlying_prices=[90, 100, 102.5, 105])

    assert result.structure_type == "long_call"
    assert result.net_debit == 2.5
    assert result.net_credit is None
    assert result.max_profit is None
    assert result.max_loss == 250.0
    assert result.breakevens == (102.5,)
    assert result.warnings == ("max_profit_unbounded",)
    assert _point_map(result)[102.5] == 0.0


def test_long_put_payoff_primitive_and_structure_summary() -> None:
    leg = OptionLegInput(action="buy", right="put", strike=100, premium=3)

    assert calculate_option_leg_payoff(leg, 120) == -300.0
    assert calculate_option_leg_payoff(leg, 95) == 200.0
    assert calculate_option_leg_payoff(leg, 0) == 9700.0

    result = analyze_option_structure([leg], underlying_prices=[0, 95, 97, 100, 120])

    assert result.structure_type == "long_put"
    assert result.net_debit == 3.0
    assert result.max_profit == 9700.0
    assert result.max_loss == 300.0
    assert result.breakevens == (97.0,)
    assert _point_map(result)[97.0] == 0.0


def test_short_option_primitive_math_exists_but_naked_short_structure_is_blocked() -> None:
    short_call = OptionLegInput(action="sell", right="call", strike=100, premium=2)
    short_put = OptionLegInput(action="sell", right="put", strike=100, premium=2)

    assert calculate_option_leg_payoff(short_call, 90) == 200.0
    assert calculate_option_leg_payoff(short_call, 105) == -300.0
    assert calculate_option_leg_payoff(short_put, 105) == 200.0
    assert calculate_option_leg_payoff(short_put, 95) == -300.0

    blocked = analyze_option_structure([short_call], underlying_prices=[90, 100, 110])
    assert blocked.is_blocked
    assert blocked.blocked_reason == "naked_short_option_not_supported"
    assert blocked.max_profit is None
    assert blocked.payoff_points == ()


def test_call_vertical_debit_spread_metrics_and_payoff_table() -> None:
    result = analyze_vertical_debit_spread(
        [
            OptionLegInput(action="buy", right="call", strike=100, premium=6),
            OptionLegInput(action="sell", right="call", strike=110, premium=2),
        ],
        underlying_prices=[95, 100, 104, 110, 115],
    )

    assert not result.is_blocked
    assert result.net_debit == 4.0
    assert result.net_credit is None
    assert result.max_loss == 400.0
    assert result.max_profit == 600.0
    assert result.breakevens == (104.0,)

    payoff_map = _point_map(result)
    assert payoff_map[95.0] == -400.0
    assert payoff_map[100.0] == -400.0
    assert payoff_map[104.0] == 0.0
    assert payoff_map[110.0] == 600.0
    assert payoff_map[115.0] == 600.0


def test_put_vertical_debit_spread_metrics_and_payoff_table() -> None:
    result = analyze_vertical_debit_spread(
        [
            OptionLegInput(action="buy", right="put", strike=110, premium=7),
            OptionLegInput(action="sell", right="put", strike=100, premium=3),
        ],
        underlying_prices=[95, 100, 106, 110, 115],
    )

    assert not result.is_blocked
    assert result.net_debit == 4.0
    assert result.max_loss == 400.0
    assert result.max_profit == 600.0
    assert result.breakevens == (106.0,)

    payoff_map = _point_map(result)
    assert payoff_map[115.0] == -400.0
    assert payoff_map[110.0] == -400.0
    assert payoff_map[106.0] == 0.0
    assert payoff_map[100.0] == 600.0
    assert payoff_map[95.0] == 600.0


def test_vertical_debit_spread_rejects_invalid_leg_ordering() -> None:
    blocked = analyze_vertical_debit_spread(
        [
            OptionLegInput(action="buy", right="call", strike=110, premium=6),
            OptionLegInput(action="sell", right="call", strike=100, premium=2),
        ]
    )

    assert blocked.is_blocked
    assert blocked.blocked_reason == "call_vertical_debit_requires_long_lower_strike"


def test_iron_condor_metrics_inside_body_and_beyond_wings() -> None:
    result = analyze_iron_condor(
        [
            OptionLegInput(action="buy", right="put", strike=90, premium=1),
            OptionLegInput(action="sell", right="put", strike=95, premium=3),
            OptionLegInput(action="sell", right="call", strike=105, premium=3),
            OptionLegInput(action="buy", right="call", strike=110, premium=1),
        ],
        underlying_prices=[85, 90, 95, 100, 103, 107, 110, 115],
    )

    assert not result.is_blocked
    assert result.net_credit == 4.0
    assert result.net_debit is None
    assert result.max_profit == 400.0
    assert result.max_loss == 100.0
    assert result.breakevens == (91.0, 109.0)
    assert result.warnings == ()

    payoff_map = _point_map(result)
    assert payoff_map[100.0] == 400.0
    assert payoff_map[103.0] == 400.0
    assert payoff_map[85.0] == -100.0
    assert payoff_map[115.0] == -100.0


def test_iron_condor_allows_unequal_wings_with_warning() -> None:
    result = analyze_iron_condor(
        [
            OptionLegInput(action="buy", right="put", strike=90, premium=1),
            OptionLegInput(action="sell", right="put", strike=95, premium=3),
            OptionLegInput(action="sell", right="call", strike=105, premium=3),
            OptionLegInput(action="buy", right="call", strike=112, premium=1),
        ],
        underlying_prices=[85, 95, 100, 105, 112],
    )

    assert not result.is_blocked
    assert result.warnings == ("unequal_wing_widths",)
    assert result.max_profit == 400.0
    assert result.max_loss == 300.0


def test_iron_condor_rejects_invalid_strike_ordering() -> None:
    blocked = analyze_iron_condor(
        [
            OptionLegInput(action="buy", right="put", strike=95, premium=1),
            OptionLegInput(action="sell", right="put", strike=90, premium=3),
            OptionLegInput(action="sell", right="call", strike=105, premium=3),
            OptionLegInput(action="buy", right="call", strike=110, premium=1),
        ]
    )

    assert blocked.is_blocked
    assert blocked.blocked_reason == "iron_condor_requires_ordered_strikes"


def test_invalid_inputs_block_cleanly() -> None:
    blocked = analyze_option_structure(
        [
            OptionLegInput(action="buy", right="call", strike=100, premium=-1),
        ],
        underlying_prices=[90, 100, 110],
    )
    assert blocked.is_blocked
    assert blocked.blocked_reason == "invalid_premium"

    zero_quantity = analyze_option_structure(
        [
            OptionLegInput(action="buy", right="put", strike=100, premium=1, quantity=0),
        ]
    )
    assert zero_quantity.blocked_reason == "invalid_quantity"

    zero_multiplier = analyze_vertical_debit_spread(
        [
            OptionLegInput(action="buy", right="call", strike=100, premium=4, multiplier=0),
            OptionLegInput(action="sell", right="call", strike=105, premium=1, multiplier=0),
        ]
    )
    assert zero_multiplier.blocked_reason == "invalid_multiplier"


def test_payoff_table_is_sorted_and_finite() -> None:
    result = analyze_vertical_debit_spread(
        [
            OptionLegInput(action="buy", right="call", strike=100, premium=5),
            OptionLegInput(action="sell", right="call", strike=110, premium=1),
        ],
        underlying_prices=[110, 95, 95, 104, 100],
    )

    assert not result.is_blocked
    prices = [point.underlying_price for point in result.payoff_points]
    assert prices == [95.0, 100.0, 104.0, 110.0]
    for point in result.payoff_points:
        assert isfinite(point.total_payoff)
        for leg_payoff in point.leg_payoffs:
            assert isfinite(leg_payoff.payoff)


def test_negative_breakeven_does_not_block_default_price_grid() -> None:
    result = analyze_option_structure(
        [OptionLegInput(action="buy", right="put", strike=1, premium=2)]
    )

    assert not result.is_blocked
    assert result.breakevens == (-1.0,)
    assert [point.underlying_price for point in result.payoff_points] == [0.0, 1.0, 2.0]
