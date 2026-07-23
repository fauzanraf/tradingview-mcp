"""Regression tests: strategy engines must surface a still-open trailing
position instead of silently discarding it (needed for signal-alert /
get_current_signal, which asks "what's the state right now").

Network-free: call the private `_run_*` functions directly with synthetic
candles, same pattern as test_donchian_backtest.py.
"""
from tradingview_mcp.core.services.backtest_service import _run_rsi


def _candle(day: int, close: float) -> dict:
    return {
        "date": f"2026-01-{day:02d}",
        "open": close,
        "high": close,
        "low": close,
        "close": close,
        "volume": 100,
    }


def _oscillating_then_drop_closes() -> list[float]:
    """21 candles gently oscillating (builds a smoothed RSI baseline around
    66-70, verified by hand against calc_rsi), then one sharp 10-point drop
    on the final candle that pulls RSI(14) down to ~32.5 — below the
    oversold=40 threshold, triggering an entry exactly on the last candle.
    """
    closes = [100.0]
    for i in range(20):
        closes.append(closes[-1] + (1 if i % 2 == 0 else -0.5))
    closes.append(closes[-1] - 10)
    return closes


def test_rsi_open_position_is_surfaced_not_dropped():
    closes = _oscillating_then_drop_closes()
    candles = [_candle(i + 1, c) for i, c in enumerate(closes)]

    trades = _run_rsi(candles, oversold=40, overbought=60, period=14)

    assert len(trades) == 1, f"expected exactly one open position, got {trades}"
    t = trades[0]
    assert t["strategy"] == "rsi"
    assert t["exit_date"] is None
    assert t["exit_price"] is None
    assert t["entry_date"] == candles[-1]["date"]
    assert t["entry_price"] == 95.0


def test_rsi_no_trades_yields_empty_list_still():
    # Flat prices never cross the RSI thresholds -> no open position, no crash.
    candles = [_candle(i + 1, 50.0) for i in range(20)]
    assert _run_rsi(candles, oversold=40, overbought=60, period=14) == []
