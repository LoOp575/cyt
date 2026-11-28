"""Daily Base Volume anomaly engine for Pump Radar V2.

The evaluated candle must be closed. Daily RVOL compares the latest closed
candle with the mean of the seven immediately preceding closed candles.
Weekly RVOL compares the latest seven closed candles with the seven before
that. This module is pure computation and never fetches market data.
"""
from __future__ import annotations

from statistics import mean
from typing import Any

MIN_HISTORY = 15
THRESHOLDS = {
    "increasing": 1.5,
    "anomaly": 2.0,
    "strong": 3.0,
    "extreme": 5.0,
}


def _num(candle: dict[str, Any], key: str) -> float:
    try:
        value = float(candle.get(key) or 0)
        return value if value >= 0 else 0.0
    except (TypeError, ValueError):
        return 0.0


def _pct(current: float, previous: float) -> float | None:
    if previous <= 0:
        return None
    return (current / previous - 1.0) * 100.0


def _classify(ratio: float | None) -> str:
    if ratio is None:
        return "UNAVAILABLE"
    if ratio >= THRESHOLDS["extreme"]:
        return "EXTREME_ANOMALY"
    if ratio >= THRESHOLDS["strong"]:
        return "STRONG_ANOMALY"
    if ratio >= THRESHOLDS["anomaly"]:
        return "ANOMALY"
    if ratio >= THRESHOLDS["increasing"]:
        return "INCREASING"
    return "NORMAL"


def evaluate_daily_base_volume(
    candles: list[dict[str, Any]], symbol: str = ""
) -> dict[str, Any]:
    """Evaluate latest closed daily bar against its own prior 7-day baseline."""
    bars = sorted(candles, key=lambda item: int(item.get("date") or 0))
    if len(bars) < MIN_HISTORY:
        return {
            "ok": False,
            "symbol": symbol.upper(),
            "status": "INSUFFICIENT_DATA",
            "bars": len(bars),
            "minBars": MIN_HISTORY,
            "reason": f"Need {MIN_HISTORY} closed daily candles for daily and weekly comparisons.",
        }

    latest = bars[-1]
    prior7 = bars[-8:-1]
    current7 = bars[-7:]
    previous7 = bars[-14:-7]

    prior_base_avg = mean(_num(c, "volume") for c in prior7)
    current_base = _num(latest, "volume")
    daily_rvol = current_base / prior_base_avg if prior_base_avg > 0 else None

    current7_base = sum(_num(c, "volume") for c in current7)
    previous7_base = sum(_num(c, "volume") for c in previous7)
    weekly_rvol = current7_base / previous7_base if previous7_base > 0 else None

    prior_quote_avg = mean(_num(c, "quoteVolume") for c in prior7)
    current_quote = _num(latest, "quoteVolume")
    quote_daily_rvol = current_quote / prior_quote_avg if prior_quote_avg > 0 else None
    current7_quote = sum(_num(c, "quoteVolume") for c in current7)
    previous7_quote = sum(_num(c, "quoteVolume") for c in previous7)
    quote_weekly_rvol = current7_quote / previous7_quote if previous7_quote > 0 else None

    close = _num(latest, "close")
    prev_close = _num(bars[-2], "close")
    close_7d_ago = _num(bars[-8], "close")
    change24h = _pct(close, prev_close)
    change7d = _pct(close, close_7d_ago)

    buy_quote = _num(latest, "takerBuyQuote")
    buy_share = buy_quote / current_quote if current_quote > 0 else None
    category = _classify(daily_rvol)

    # The volume anomaly is the trigger. Price and quote flow are context,
    # not mandatory gates, so an early signal is not delayed by price movement.
    return {
        "ok": True,
        "symbol": symbol.upper(),
        "category": category,
        "signal": category in {"INCREASING", "ANOMALY", "STRONG_ANOMALY", "EXTREME_ANOMALY"},
        "metrics": {
            "evaluatedDate": latest.get("date"),
            "baseVolume": current_base,
            "baseVolumePrior7dAverage": prior_base_avg,
            "baseRvolDaily": daily_rvol,
            "baseVolume7d": current7_base,
            "baseVolumePrevious7d": previous7_base,
            "baseRvol7d": weekly_rvol,
            "quoteVolume": current_quote,
            "quoteVolumePrior7dAverage": prior_quote_avg,
            "quoteRvolDaily": quote_daily_rvol,
            "quoteVolume7d": current7_quote,
            "quoteVolumePrevious7d": previous7_quote,
            "quoteRvol7d": quote_weekly_rvol,
            "buyShareQuotePct": buy_share * 100 if buy_share is not None else None,
            "priceChange24hPct": change24h,
            "priceChange7dPct": change7d,
            "close": close,
        },
        "thresholds": THRESHOLDS,
        "interpretation": {
            "volume": category,
            "price": (
                "PRICE_EXPANDING" if change24h is not None and change24h >= 3
                else "PRICE_CONTAINED" if change24h is not None and abs(change24h) < 3
                else "PRICE_WEAK" if change24h is not None
                else "UNAVAILABLE"
            ),
            "demand": (
                "BUY_SIDE_DOMINANT" if buy_share is not None and buy_share >= 0.60
                else "SELL_SIDE_OR_BALANCED" if buy_share is not None
                else "UNAVAILABLE"
            ),
            "note": "Base Volume anomaly is a market-activity alert, not proof of accumulation or a buy signal.",
        },
    }
