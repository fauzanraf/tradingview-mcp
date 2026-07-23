"""Tests for get_current_signal — network-free via monkeypatching _fetch_ohlcv,
since (unlike the rest of the backtest suite, which calls _run_* directly)
this exercises the public function that hits the network boundary.
"""
import tradingview_mcp.core.services.backtest_service as bs
from tradingview_mcp.core.services.backtest_service import get_current_signal


def _candle(day: int, close: float) -> dict:
    return {
        "date": f"2026-01-{day:02d}",
        "open": close, "high": close, "low": close, "close": close,
        "volume": 100,
    }


def _oscillating_then_drop_closes() -> list[float]:
    """30 gently oscillating candles (smoothed RSI baseline, well above the
    oversold=40 threshold throughout — verified directly against calc_rsi),
    then one sharp 10-point drop on the final candle that pulls RSI(14) down
    to ~30 — below oversold=40, triggering an entry exactly on the last
    candle. 31 candles total, clearing get_current_signal's 30-bar minimum.
    The drop lands on close=98.0.
    """
    closes = [100.0]
    for i in range(29):
        closes.append(closes[-1] + (1 if i % 2 == 0 else -0.5))
    closes.append(closes[-1] - 10)
    return closes


def test_buy_today_when_entry_lands_on_last_candle(monkeypatch):
    closes = _oscillating_then_drop_closes()
    candles = [_candle(i + 1, c) for i, c in enumerate(closes)]
    monkeypatch.setattr(bs, "_fetch_ohlcv", lambda symbol, period, interval: candles)

    result = get_current_signal("TESTSYM", "rsi", period="1y", interval="1d")

    assert result["status"] == "BUY_TODAY"
    assert result["symbol"] == "TESTSYM"
    assert result["strategy"] == "rsi"
    assert result["last_date"] == candles[-1]["date"]
    assert result["entry_price"] == 98.0


def test_flat_when_no_position_open(monkeypatch):
    candles = [_candle(i + 1, 50.0) for i in range(30)]
    monkeypatch.setattr(bs, "_fetch_ohlcv", lambda symbol, period, interval: candles)

    result = get_current_signal("TESTSYM", "rsi", period="1y", interval="1d")

    assert result["status"] == "FLAT"


def test_holding_when_position_opened_before_last_candle(monkeypatch):
    # Same series as test_buy_today_when_entry_lands_on_last_candle (entry
    # triggers on what was the last candle there, close=98.0), but with two
    # more candles (95.0, 95.0) appended after it. RSI(14) stays well below
    # the overbought=60 exit threshold through both, so the position stays
    # open and unexited -> still HOLDING, just no longer opened on THIS last
    # candle (verified directly against _run_rsi).
    closes = _oscillating_then_drop_closes() + [95.0, 95.0]
    candles = [_candle(i + 1, c) for i, c in enumerate(closes)]
    monkeypatch.setattr(bs, "_fetch_ohlcv", lambda symbol, period, interval: candles)

    result = get_current_signal("TESTSYM", "rsi", period="1y", interval="1d")

    # The defining property of HOLDING: a position is open, but it was NOT
    # opened on the last candle (that's what distinguishes it from BUY_TODAY).
    assert result["status"] == "HOLDING"
    assert result["entry_date"] != result["last_date"]
    assert result["entry_date"] == candles[-3]["date"]
    assert result["entry_price"] == 98.0
    assert "unrealized_pct" in result


def test_unknown_strategy_returns_error():
    result = get_current_signal("TESTSYM", "not_a_real_strategy")
    assert "error" in result


def test_invalid_period_returns_error():
    result = get_current_signal("TESTSYM", "rsi", period="10y")
    assert "error" in result
