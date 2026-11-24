"""
Meridian v2 — Neuron Memory (audited & improved).
===================================================
Self-test offline-safe: python3 backend/neuron_memory_v2.py
"""

from __future__ import annotations

import time
from typing import Any, Optional

try:
    from .neuron import SIGNAL_NAMES, neutral_weights
    from .neuron_live import (PRED_FILE, OUT_FILE, _load_jsonl,
                              signal_fp, signal_log, signal_micro, signal_trend)
except ImportError:
    from neuron import SIGNAL_NAMES, neutral_weights
    from neuron_live import (PRED_FILE, OUT_FILE, _load_jsonl,
                             signal_fp, signal_log, signal_micro, signal_trend)

HALF_LIFE_DAYS = 14.0
SIM_MIN = 0.70
MIN_COMMON_DIMS = 2
PRIOR_STRENGTH = 12.0
MIN_NEIGHBORS_EFF = 5.0
VETO_MIN_N = 8.0
VETO_FAIL_RATE = 0.35


def similarity(a: dict[str, Any], b: dict[str, Any],
               weights: Optional[dict[str, float]] = None) -> Optional[float]:
    w = weights or neutral_weights()
    common = [k for k in SIGNAL_NAMES
              if a.get(k) is not None and b.get(k) is not None]
    if len(common) < MIN_COMMON_DIMS:
        return None
    tot_w = sum(w[k] for k in common)
    if tot_w <= 0:
        return None
    diff = sum(w[k] * abs(float(a[k]) - float(b[k])) for k in common) / tot_w
    return max(0.0, 1.0 - diff)


def age_weight(ts: float, now: Optional[float] = None) -> float:
    now = now if now is not None else time.time()
    age_days = max(0.0, now - float(ts)) / 86400.0
    return 0.5 ** (age_days / HALF_LIFE_DAYS)


def memory_stats(signals: dict[str, Any], rows: list[dict[str, Any]],
                 weights: Optional[dict[str, float]] = None,
                 now: Optional[float] = None) -> dict[str, Any]:
    now = now if now is not None else time.time()
    n_eff = wins_eff = 0.0
    pairs = 0
    for r in rows:
        sim = similarity(signals, r.get("signals") or {}, weights)
        if sim is None or sim < SIM_MIN:
            continue
        wgt = sim * age_weight(float(r.get("ts", now)), now)
        n_eff += wgt
        if int(r.get("y", 0)) == 1:
            wins_eff += wgt
        pairs += 1
    if n_eff < MIN_NEIGHBORS_EFF:
        return {"n_eff": round(n_eff, 4), "wins_eff": round(wins_eff, 4),
                "pairs": pairs, "p_raw": None, "p_mem": None}
    p_raw = wins_eff / n_eff
    p_mem = (wins_eff + PRIOR_STRENGTH * 0.5) / (n_eff + PRIOR_STRENGTH)
    return {"n_eff": round(n_eff, 4), "wins_eff": round(wins_eff, 4),
            "pairs": pairs, "p_raw": round(p_raw, 4), "p_mem": round(p_mem, 4)}


def memory_p(signals: dict[str, Any], rows: list[dict[str, Any]],
             weights: Optional[dict[str, float]] = None) -> Optional[float]:
    return memory_stats(signals, rows, weights)["p_mem"]


def memory_veto(signals: dict[str, Any], rows: list[dict[str, Any]],
                weights: Optional[dict[str, float]] = None) -> bool:
    st = memory_stats(signals, rows, weights)
    if st["p_raw"] is None or st["n_eff"] < VETO_MIN_N:
        return True
    return st["p_raw"] >= VETO_FAIL_RATE


def load_memory_rows(pred_path: str = PRED_FILE,
                     out_path: str = OUT_FILE) -> list[dict[str, Any]]:
    outs = {o.get("pred_id"): o for o in _load_jsonl(out_path)}
    rows: list[dict[str, Any]] = []
    for p in _load_jsonl(pred_path):
        o = outs.get(p.get("id"))
        if not o or "y" not in o:
            continue
        rows.append({"signals": p.get("signals") or {},
                     "y": int(o["y"]), "ts": float(p.get("ts", 0.0))})
    return rows


def predict(symbol: str) -> Optional[float]:
    rows = load_memory_rows()
    if not rows:
        return None
    signals = {"fp": signal_fp(symbol), "trend": signal_trend(symbol),
               "micro": signal_micro(symbol), "mem": None, "log": signal_log(symbol)}
    return memory_p(signals, rows)


if __name__ == "__main__":
    now = time.time()
    assert similarity({"fp": 0.8}, {"fp": 0.8}) is None
    assert abs(similarity({"fp": 0.8, "trend": 0.6}, {"fp": 0.8, "trend": 0.6}) - 1.0) < 1e-9
    assert abs(age_weight(now - 14 * 86400.0, now) - 0.5) < 1e-9

    rows = [{"signals": {"fp": 0.8, "trend": 0.8}, "y": 1, "ts": now} for _ in range(10)]
    st = memory_stats({"fp": 0.8, "trend": 0.8}, rows, now=now)
    assert st["p_raw"] == 1.0 and st["p_mem"] < 1.0
    assert memory_veto({"fp": 0.8, "trend": 0.8}, rows) is True

    rows_bad = [{"signals": {"fp": 0.8, "trend": 0.8}, "y": 0, "ts": now} for _ in range(10)]
    assert memory_veto({"fp": 0.8, "trend": 0.8}, rows_bad) is False
    print("SELF-TEST OK — neuron_memory_v2")