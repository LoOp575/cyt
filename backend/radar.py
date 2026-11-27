# ============================================================
# radar.py — PUMP RADAR untuk Meridian
# Logika = hasil validasi backtest SEI (jangan diubah dulu!)
# ============================================================
import requests
from datetime import datetime

# ---------- KONFIGURASI ----------
BASELINE_DAYS  = 20    # baseline = rata-rata volume 20 hari sebelumnya
SPIKE_RATIO    = 2.0   # trigger tunggal: volume >= 2x baseline
CLUSTER_RATIO  = 1.2   # trigger cluster: >= 1.2x baseline
CLUSTER_MIN    = 2     # ...minimal 2 dari 5 hari terakhir
CLUSTER_WINDOW = 5
VETO_CRASH_PCT = -8.0  # hari crash <= -8% = sinyal gugur
SUPPRESS_DAYS  = 7     # sinyal baru minimal 7 hari dari sinyal sebelumnya

BINANCE_URL = "https://data-api.binance.vision/api/v3/klines"


def fetch_klines(symbol: str, limit: int = 100) -> list:
    """Tarik candle harian dari Binance (API publik, tanpa key)."""
    r = requests.get(BINANCE_URL, params={
        "symbol": symbol, "interval": "1d", "limit": limit
    }, timeout=15)
    r.raise_for_status()
    return [{
        "time":      datetime.utcfromtimestamp(k[0] / 1000).strftime("%d %b"),
        "open":      float(k[1]),
        "high":      float(k[2]),
        "low":       float(k[3]),
        "close":     float(k[4]),
        "volume":    float(k[5]),
        "taker_buy": float(k[9]),
    } for k in r.json()]


def compute_baseline(candles: list, i: int):
    """Rata-rata volume 20 hari SEBELUM hari i (anti lookahead)."""
    start = i - BASELINE_DAYS
    if start < 0:
        return None
    window = candles[start:i]
    return sum(c["volume"] for c in window) / len(window)


def day_change_pct(c: dict) -> float:
    return (c["close"] - c["open"]) / c["open"] * 100


def evaluate_day(candles: list, i: int):
    """Evaluasi hari ke-i pakai data sampai hari i saja."""
    c = candles[i]
    base = compute_baseline(candles, i)
    if base is None or base <= 0:
        return None

    ratio = c["volume"] / base

    cluster_hits = 0
    for j in range(max(0, i - CLUSTER_WINDOW + 1), i + 1):
        bj = compute_baseline(candles, j)
        if bj and (candles[j]["volume"] / bj) >= CLUSTER_RATIO:
            cluster_hits += 1

    change = day_change_pct(c)
    vetoed = change <= VETO_CRASH_PCT
    trig   = (ratio >= SPIKE_RATIO or cluster_hits >= CLUSTER_MIN) and not vetoed

    return {
        "time": c["time"], "ratio": round(ratio, 2),
        "cluster_hits": cluster_hits, "change_pct": round(change, 1),
        "vetoed": vetoed, "triggered": trig,
        "buy_share": round(c["taker_buy"] / c["volume"], 3),
        "close": c["close"],
    }


def radar_summary(symbol: str) -> dict:
    """
    Ringkasan radar 1 coin — dipakai API di Bagian 2.
    Candle TERAKHIR masih berjalan (belum tutup), jadi sinyal
    hanya dihitung dari candle yang SUDAH CLOSE.
    """
    candles = fetch_klines(symbol, 100)
    closed  = candles[:-1]          # buang candle hari ini yang belum tutup
    last    = evaluate_day(closed, len(closed) - 1)

    # kumpulin sinyal dengan suppress anti-FOMO
    signals, last_i = [], -10**9
    for i in range(len(closed)):
        ev = evaluate_day(closed, i)
        if ev and ev["triggered"]:
            if i - last_i >= SUPPRESS_DAYS:
                signals.append(ev)
                last_i = i

    status = "TRIGGER" if (last and last["triggered"]) else "IDLE"
    return {
        "symbol": symbol,
        "status": status,
        "today":  last,           # status hari closed terakhir
        "signals": signals,       # riwayat sinyal yang lolos
    }
