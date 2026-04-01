from macmarket_trader.indicators import compute_haco_states, compute_hacolt_direction


def test_haco_state_transitions_emit_flips() -> None:
    closes = [10, 11, 12, 13, 12, 11, 10, 11, 12]
    points = compute_haco_states(closes)
    flips = [p.flip for p in points if p.flip]
    assert "sell" in flips
    assert "buy" in flips


def test_hacolt_direction_logic() -> None:
    uptrend = compute_hacolt_direction([float(v) for v in range(1, 80)])
    assert uptrend[-1].direction == "up"

    downtrend = compute_hacolt_direction([float(v) for v in range(80, 1, -1)])
    assert downtrend[-1].direction == "down"
