"""Additive Pump Radar V2 engine.

Pure computation only. Does not fetch data, mutate storage, or alter the legacy
radar/screener. Input candles use the daily schema from backend.screening:
{date, open, high, low, close, volume, quoteVolume, takerBuyBase,
 takerBuyQuote}. All signals are evaluated on closed candles supplied by caller.
"""
from __future__ import annotations

from statistics import median
from typing import Any

BASELINE_DAYS = 30
WINDOW_DAYS = 7
MIN_HISTORY = 100
EPS = 1e-12

DEFAULTS = {
    "dormant_drawdown_90d": -15.0,
    "dormant_daily_base_rvol": 3.0,
    "dormant_daily_quote_rvol": 3.0,
    "dormant_weekly_quote_rvol": 1.5,
    "dormant_price_7d_min": -5.0,
    "dormant_price_7d_max": 5.0,
    "active_daily_base_rvol": 2.5,
    "active_daily_quote_rvol": 2.5,
    "active_weekly_quote_rvol": 1.5,
    "active_price_24h": 3.0,
    "active_price_7d_min": 0.0,
}


def _number(candle: dict[str, Any], key: str, default: float = 0.0) -> float:
    value = candle.get(key, default)
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if result >= 0 else default


def _median(values: list[float]) -> float:
    clean = [v for v in values if v > EPS]
    return float(median(clean)) if clean else 0.0


def _ratio(value: float, baseline: float) -> float | None:
    return value / baseline if baseline > EPS else None


def _pct(current: float, previous: float) -> float | None:
    if previous <= EPS:
        return None
    return (current / previous - 1.0) * 100.0


def _window_sum(candles: list[dict[str, Any]], field: str, start: int, end: int) -> float:
    return sum(_number(c, field) for c in candles[start:end])


def _score_rvol(value: float | None, threshold: float) -> float:
    if value is None or threshold <= 0:
        return 0.0
    # 0 at 1x, 100 at 4x threshold; bounded and interpretable.
    return max(0.0, min(100.0, (value - 1.0) / (3.0 * threshold - 1.0) * 100.0))


def _score_buy_share(value: float | None) -> float:
    if value is None:
        return 0.0
    return max(0.0, min(100.0, (value - 0.45) / 0.25 * 100.0))


def _score_drawdown(value: float | None) -> float:
    if value is None:
        return 0.0
    # 15% drawdown = 0; 60% or deeper = 100.
    return max(0.0, min(100.0, (abs(min(value, 0.0)) - 15.0) / 45.0 * 100.0))


def _score_price_containment(change_7d: float | None) -> float:
    if change_7d is None:
        return 0.0
    # Best when price is contained near flat; fades outside +/-5%.
    return max(0.0, 100.0 - max(0.0, abs(change_7d) - 1.0) * 20.0)


def _score_positive_momentum(change_24h: float | None, change_7d: float | None) -> float:
    if change_24h is None or change_7d is None:
        return 0.0
    a = max(0.0, min(100.0, change_24h / 10.0 * 100.0))
    b = max(0.0, min(100.0, change_7d / 20.0 * 100.0))
    return 0.6 * a + 0.4 * b


def compute_pump_radar(candles: list[dict[str, Any]], symbol: str = "",
                       params: dict[str, float] | None = None) -> dict[str, Any]:
    """Return Dormant and Active classifications for one asset.

    The last candle is assumed CLOSED. The caller must remove an in-progress
    daily candle before calling. At least 100 candles are required so 90D
    drawdown and a 30D prior baseline can be evaluated without lookahead.
    """
    cfg = {**DEFAULTS, **(params or {})}
    n = len(candles)
    if n < MIN_HISTORY:
        return {
            "ok": False, "symbol": symbol, "status": "INSUFFICIENT_DATA",
            "bars": n, "minBars": MIN_HISTORY,
            "reason": f"Need at least {MIN_HISTORY} closed daily candles; got {n}.",
        }

    required = ("close", "high", "volume", "quoteVolume", "takerBuyBase", "takerBuyQuote")
    missing = [key for key in required if key not in candles[-1]]
    if missing:
        return {
            "ok": False, "symbol": symbol, "status": "MISSING_FIELDS",
            "missingFields": missing,
            "reason": "Pump Radar V2 requires base and quote volume plus taker-buy fields.",
        }

    last = candles[-1]
    close = _number(last, "close")
    prev_close = _number(candles[-2], "close")
    close_7d_ago = _number(candles[-8], "close")
    if close <= EPS or prev_close <= EPS or close_7d_ago <= EPS:
        return {"ok": False, "symbol": symbol, "status": "INVALID_PRICE", "reason": "Invalid close price."}

    change_24h = _pct(close, prev_close)
    change_7d = _pct(close, close_7d_ago)

    # The baseline excludes the evaluated candle: no lookahead/self-inflation.
    prior_base = [_number(c, "volume") for c in candles[-(BASELINE_DAYS + 1):-1]]
    prior_quote = [_number(c, "quoteVolume") for c in candles[-(BASELINE_DAYS + 1):-1]]
    base_median = _median(prior_base)
    quote_median = _median(prior_quote)
    base_today = _number(last, "volume")
    quote_today = _number(last, "quoteVolume")
    base_rvol = _ratio(base_today, base_median)
    quote_rvol = _ratio(quote_today, quote_median)

    # Seven-day aggregate versus seven times the prior daily median.
    quote_7d = _window_sum(candles, "quoteVolume", n - 7, n)
    base_7d = _window_sum(candles, "volume", n - 7, n)
    weekly_quote_rvol = _ratio(quote_7d, quote_median * 7.0)
    weekly_base_rvol = _ratio(base_7d, base_median * 7.0)

    # 90D drawdown from the highest high in the last 90 closed candles.
    high_90d = max(_number(c, "high") for c in candles[-90:])
    drawdown_90d = (close / high_90d - 1.0) * 100.0 if high_90d > EPS else None

    buy_base = _number(last, "takerBuyBase")
    buy_quote = _number(last, "takerBuyQuote")
    buy_share_base = buy_base / base_today if base_today > EPS else None
    buy_share_quote = buy_quote / quote_today if quote_today > EPS else None
    sell_share_base = 1.0 - buy_share_base if buy_share_base is not None else None

    # Price-demand efficiency: price return per percentage point of quote-volume
    # growth against the previous 7D period. Not a probability or causal measure.
    quote_prev_7d = _window_sum(candles, "quoteVolume", n - 14, n - 7)
    quote_growth_7d = _pct(quote_7d, quote_prev_7d)
    price_demand_efficiency = (
        change_7d / quote_growth_7d
        if quote_growth_7d is not None and abs(quote_growth_7d) > 1e-9
        else None
    )
    base_prev_7d = _window_sum(candles, "volume", n - 14, n - 7)
    base_growth_7d = _pct(base_7d, base_prev_7d)

    # Compare USD-denominated activity with token-unit activity. Large divergence
    # can be price/mix-driven, so expose it rather than treating it as demand proof.
    volume_price_distortion = (
        quote_growth_7d - base_growth_7d
        if quote_growth_7d is not None and base_growth_7d is not None
        else None
    )

    # Separate category rules. All required values must exist.
    dormant = (
        drawdown_90d is not None and drawdown_90d <= cfg["dormant_drawdown_90d"]
        and base_rvol is not None and base_rvol >= cfg["dormant_daily_base_rvol"]
        and quote_rvol is not None and quote_rvol >= cfg["dormant_daily_quote_rvol"]
        and weekly_quote_rvol is not None and weekly_quote_rvol >= cfg["dormant_weekly_quote_rvol"]
        and change_7d is not None
        and cfg["dormant_price_7d_min"] <= change_7d <= cfg["dormant_price_7d_max"]
    )
    active = (
        base_rvol is not None and base_rvol >= cfg["active_daily_base_rvol"]
        and quote_rvol is not None and quote_rvol >= cfg["active_daily_quote_rvol"]
        and weekly_quote_rvol is not None and weekly_quote_rvol >= cfg["active_weekly_quote_rvol"]
        and change_24h is not None and change_24h >= cfg["active_price_24h"]
        and change_7d is not None and change_7d > cfg["active_price_7d_min"]
    )

    dormant_score = (
        0.25 * _score_rvol(base_rvol, cfg["dormant_daily_base_rvol"])
        + 0.25 * _score_rvol(quote_rvol, cfg["dormant_daily_quote_rvol"])
        + 0.15 * _score_rvol(weekly_quote_rvol, cfg["dormant_weekly_quote_rvol"])
        + 0.15 * _score_buy_share(buy_share_quote)
        + 0.10 * _score_drawdown(drawdown_90d)
        + 0.10 * _score_price_containment(change_7d)
    )
    active_score = (
        0.20 * _score_rvol(base_rvol, cfg["active_daily_base_rvol"])
        + 0.25 * _score_rvol(quote_rvol, cfg["active_daily_quote_rvol"])
        + 0.15 * _score_rvol(weekly_quote_rvol, cfg["active_weekly_quote_rvol"])
        + 0.15 * _score_buy_share(buy_share_quote)
        + 0.25 * _score_positive_momentum(change_24h, change_7d)
    )

    if dormant and active:
        category = "BOTH"
    elif dormant:
        category = "DORMANT_VOLUME_ANOMALY"
    elif active:
        category = "ACTIVE_VOLUME_EXPANSION"
    else:
        category = "WATCH"

    return {
        "ok": True,
        "symbol": symbol.upper(),
        "category": category,
        "scores": {
            "dormant": round(dormant_score, 1),
            "active": round(active_score, 1),
        },
        "signals": {"dormant": dormant, "active": active},
        "metrics": {
            "close": close,
            "change24hPct": round(change_24h, 3) if change_24h is not None else None,
            "change7dPct": round(change_7d, 3) if change_7d is not None else None,
            "drawdown90dPct": round(drawdown_90d, 3) if drawdown_90d is not None else None,
            "baseVolume": base_today,
            "baseVolume7d": base_7d,
            "baseRvolDaily": round(base_rvol, 3) if base_rvol is not None else None,
            "baseRvol7d": round(weekly_base_rvol, 3) if weekly_base_rvol is not None else None,
            "baseGrowth7dPct": round(base_growth_7d, 3) if base_growth_7d is not None else None,
            "quoteVolumeUsdt": quote_today,
            "quoteVolume7dUsdt": quote_7d,
            "quoteRvolDaily": round(quote_rvol, 3) if quote_rvol is not None else None,
            "quoteRvol7d": round(weekly_quote_rvol, 3) if weekly_quote_rvol is not None else None,
            "quoteGrowth7dPct": round(quote_growth_7d, 3) if quote_growth_7d is not None else None,
            "buyShareBasePct": round(buy_share_base * 100, 2) if buy_share_base is not None else None,
            "buyShareQuotePct": round(buy_share_quote * 100, 2) if buy_share_quote is not None else None,
            "sellShareBasePct": round(sell_share_base * 100, 2) if sell_share_base is not None else None,
            "priceDemandEfficiency": round(price_demand_efficiency, 5) if price_demand_efficiency is not None else None,
            "volumePriceDistortionPctPoints": round(volume_price_distortion, 3) if volume_price_distortion is not None else None,
        },
        "interpretation": {
            "buyPressure": (
                "BUY_SIDE_DOMINANT" if buy_share_quote is not None and buy_share_quote >= 0.60
                else "SELL_SIDE_OR_BALANCED" if buy_share_quote is not None
                else "UNAVAILABLE"
            ),
            "priceResponse": (
                "PRICE_CONTAINED" if abs(change_7d) <= 5.0
                else "PRICE_EXPANDING" if change_7d > 5.0
                else "PRICE_WEAK"
            ),
            "volumeQuality": (
                "BASE_AND_QUOTE_BOTH_EXPANDED"
                if base_rvol is not None and quote_rvol is not None and base_rvol >= 2.0 and quote_rvol >= 2.0
                else "CHECK_PRICE_MIX_OR_BASE_VOLUME"
            ),
            "caution": "Volume and taker-buy share do not prove whale accumulation or future price appreciation.",
        },
        "parameters": cfg,
        "evaluatedOn": last.get("date"),
    }


def forward_outcomes(candles: list[dict[str, Any]], signal_index: int) -> dict[str, float | None]:
    """Measure close-to-close forward returns after a historical signal index."""
    if signal_index < 0 or signal_index >= len(candles):
        raise IndexError("signal_index out of range")
    entry = _number(candles[signal_index], "close")
    if entry <= EPS:
        return {"return24hPct": None, "return72hPct": None, "return7dPct": None}
    result: dict[str, float | None] = {}
    for days, key in ((1, "return24hPct"), (3, "return72hPct"), (7, "return7dPct")):
        target = signal_index + days
        result[key] = (
            round((_number(candles[target], "close") / entry - 1.0) * 100.0, 3)
            if target < len(candles) else None
        )
    return result
