"""
Meridian v2 — Neuron Logistics (audited & improved).
=====================================================
Menyalakan sinyal `log` (kelima & terakhir): logistik EKSEKUSI.
Self-test offline-safe: python3 backend/neuron_logistics.py
"""

from __future__ import annotations

import json
import math
import os
import urllib.request
from typing import Optional

try:
    from .fp_v2_engine import BURN_IN, estimate_returns, ewma_sigma
except ImportError:
    from fp_v2_engine import BURN_IN, estimate_returns, ewma_sigma

TAKER_FEE = float(os.environ.get("MERIDIAN_TAKER_FEE", "0.001"))
K_TILT = 6.0
K_IMB = 3.0
DEPTH_BAND = 0.001
EDGE_REF = 3.0
K_CONF = 1.5
MAX_SPREAD_FRAC = 0.005
MAX_COST_FRAC = 0.01
EDGE_VETO_MIN = 1.5


def _sigmoid(z: float) -> float:
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    ez = math.exp(z)
    return ez / (1.0 + ez)


def _get_json(url: str) -> dict | list:
    req = urllib.request.Request(url, headers={"User-Agent": "Meridian/2.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def logistics_from_book(book: dict, closes: list[float],
                        horizon_h: float = 24.0,
                        fee: float = TAKER_FEE
                        ) -> tuple[Optional[float], dict]:
    bids = [(float(r[0]), float(r[1])) for r in (book.get("bids") or []) if len(r) >= 2]
    asks = [(float(r[0]), float(r[1])) for r in (book.get("asks") or []) if len(r) >= 2]
    if not bids or not asks:
        return None, {"reason": "buku kosong"}
    best_bid, bid_qty = bids[0]
    best_ask, ask_qty = asks[0]
    if best_bid <= 0 or best_ask <= 0 or best_ask <= best_bid:
        return None, {"reason": "buku crossed/locked"}
    mid = 0.5 * (best_bid + best_ask)
    spread_frac = (best_ask - best_bid) / mid
    if spread_frac > MAX_SPREAD_FRAC:
        return None, {"reason": "spread lebar", "spread_frac": round(spread_frac, 6)}

    denom = bid_qty + ask_qty
    micro = (best_bid * ask_qty + best_ask * bid_qty) / denom if denom > 0 else mid
    tilt = (micro - mid) / (0.5 * (best_ask - best_bid)) if denom > 0 else 0.0
    tilt = max(-1.0, min(1.0, tilt))
    lo, hi = mid * (1.0 - DEPTH_BAND), mid * (1.0 + DEPTH_BAND)
    db = sum(p * q for p, q in bids if p >= lo)
    da = sum(p * q for p, q in asks if p <= hi)
    tot = db + da
    imb = (db - da) / tot if tot > 0 else 0.0
    p_flow = _sigmoid(K_TILT * tilt + K_IMB * imb)

    cost = spread_frac + 2.0 * fee
    rets = estimate_returns(closes)
    if len(rets) < BURN_IN:
        return None, {"reason": "data volatilitas kurang", "n_returns": len(rets)}
    sigma_h, _burned = ewma_sigma(rets)
    expected = sigma_h * math.sqrt(max(horizon_h, 1e-9))
    edge_ratio = expected / cost if cost > 0 else 0.0

    conf = _sigmoid(K_CONF * (edge_ratio - EDGE_REF))
    p = conf * p_flow + (1.0 - conf) * 0.5

    diag = {"spread_frac": round(spread_frac, 6), "tilt": round(tilt, 4),
            "imb": round(imb, 4), "p_flow": round(p_flow, 4),
            "cost_frac": cost, "sigma_1h": round(sigma_h, 6),
            "expected_move": round(expected, 6),
            "edge_ratio": round(edge_ratio, 4), "conf": round(conf, 4),
            "fee": fee}
    return max(0.001, min(0.999, p)), diag


def veto_from_diag(diag: Optional[dict]) -> bool:
    if diag is None:
        return True
    if diag.get("cost_frac", 0.0) > MAX_COST_FRAC:
        return False
    if diag.get("edge_ratio", float("inf")) < EDGE_VETO_MIN:
        return False
    return True


def _gather(symbol: str) -> tuple[Optional[dict], Optional[list[float]]]:
    sym = symbol.upper()
    try:
        book = _get_json(f"https://api.binance.com/api/v3/depth?symbol={sym}&limit=50")
        raw_kl = _get_json(f"https://api.binance.com/api/v3/klines?symbol={sym}&interval=1h&limit=80")
        closes = [float(r[4]) for r in raw_kl]
        return book, closes
    except Exception:
        return None, None


def predict(symbol: str, horizon_h: float = 24.0) -> Optional[float]:
    book, closes = _gather(symbol)
    if book is None or closes is None:
        return None
    p, _diag = logistics_from_book(book, closes, horizon_h)
    return p


def logistics_diag(symbol: str, horizon_h: float = 24.0) -> Optional[dict]:
    book, closes = _gather(symbol)
    if book is None or closes is None:
        return None
    return logistics_from_book(book, closes, horizon_h)[1]


def logistics_veto(symbol: str, horizon_h: float = 24.0) -> bool:
    return veto_from_diag(logistics_diag(symbol, horizon_h))


if __name__ == "__main__":
    import random

    assert abs(_sigmoid(0.0) - 0.5) < 1e-12
    assert _sigmoid(10.0) > _sigmoid(5.0) > _sigmoid(0.0)

    book_sym = {"bids": [[100.0, 5.0], [99.99, 5.0]],
                "asks": [[100.01, 5.0], [100.02, 5.0]]}
    p, d = logistics_from_book(book_sym, [100.0] * 40, fee=0.001)
    assert abs(d["tilt"]) < 1e-9 and abs(d["imb"]) < 1e-3
    assert abs(p - 0.5) < 0.02, p

    rng = random.Random(5)
    price, closes = 100.0, []
    for _ in range(80):
        closes.append(price)
        price *= math.exp(rng.gauss(0.0, 0.005))

    p_bull, d_bull = logistics_from_book({"bids": [[100.0, 9.0]], "asks": [[100.02, 1.0]]}, closes)
    assert p_bull > 0.9, (p_bull, d_bull)

    p_bear, _ = logistics_from_book({"bids": [[100.0, 1.0]], "asks": [[100.02, 9.0]]}, closes)
    assert p_bear < 0.1, p_bear

    p_wide, _ = logistics_from_book({"bids": [[100.0, 5.0]], "asks": [[100.6, 5.0]]}, closes)
    assert p_wide is None

    p_thin, _ = logistics_from_book(book_sym, [100.0] * 10)
    assert p_thin is None

    _, d_fee = logistics_from_book(book_sym, closes, fee=0.0004)
    assert abs(d_fee["cost_frac"] - (0.01 / 100.005 + 0.0008)) < 1e-9

    assert veto_from_diag(None) is True
    assert veto_from_diag({"cost_frac": 0.02, "edge_ratio": 10.0}) is False
    assert veto_from_diag({"cost_frac": 0.002, "edge_ratio": 0.5}) is False
    assert veto_from_diag({"cost_frac": 0.002, "edge_ratio": 5.0}) is True

    print(f"demo diag: {d_bull}")
    print("SELF-TEST OK — neuron_logistics v2")