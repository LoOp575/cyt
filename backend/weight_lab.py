"""
Meridian v2 — Weight Lab (audited & improved).
===============================================
Mencari bobot fusi w* dari DATA, lalu memutuskan boleh/tidak dipakai live.

METODE LOCKED:
  Objective : minimalkan Brier = mean((P_fused - y)^2)
  Kendala   : w_i in [0.05, 0.45], sum(w) = 1
  Optimizer : scipy SLSQP -> fallback pairwise-transfer descent (tanpa scipy)
  Validasi  : walk-forward kronologis train -> val -> test (TIDAK shuffle)
  Gerbang   : SEMUA harus lolos, else bobot tetap NETRAL.

PENINGKATAN vs rancangan awal (hasil audit):
 1. Import dual-mode (package / jalankan langsung) — dulu crash kalau
    diimport sebagai `backend.weight_lab`.
 2. Prediksi None (tidak ada sinyal) dihukum 0.25 (= tebakan 0.5) — jujur,
    coverage konsisten, bukan di-skip diam-diam.
 3. AUC midrank pure-python, tie-safe — tanpa dependensi sklearn.
 4. Split KRONOLOGIS, tidak pernah shuffle time series (anti-lookahead).
    Label y wajib dibuat caller HANYA dari masa depan setelah timestamp
    sinyal — Weight Lab tidak pernah melihat masa depan.
 5. Fallback descent pairwise-transfer: sum(w)=1 dan bounds terjaga PERSIS.
 6. Gerbang gagal -> bobot netral + alasan jelas. Neuron tetap jalan,
    tidak pernah error cuma karena bobot belum layak.
 7. Deterministik (self-test di-seed; optimizer tanpa RNG).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

try:  # IMPROVEMENT #1: dual-mode import
    from .neuron import (SIGNAL_NAMES, W_MIN, W_MAX, fuse, saturation,
                         neutral_weights, validate_weights)
except ImportError:
    from neuron import (SIGNAL_NAMES, W_MIN, W_MAX, fuse, saturation,
                        neutral_weights, validate_weights)

try:
    from scipy.optimize import minimize as _scipy_minimize
    HAVE_SCIPY = True
except ImportError:
    HAVE_SCIPY = False

# ---------------------------------------------------------------------------
# Konstanta gerbang LOCKED
# ---------------------------------------------------------------------------
MIN_SAMPLES = 200          # minimal sampel test
AUC_MIN = 0.60
PRECISION_MIN = 0.55
S_MIN = 0.30               # ambang saturation untuk precision
MIN_PRECISION_SAMPLES = 20 # minimal trade yang diambil di test
BRIER_MARGIN = 0.01        # harus lebih baik dari netral dengan margin ini

Row = tuple[dict[str, Optional[float]], int]  # (signals, y in {0,1})


# ---------------------------------------------------------------------------
# Metrik inti
# ---------------------------------------------------------------------------

def brier(weights: dict[str, float], rows: list[Row]) -> float:
    """IMPROVEMENT #2: prediksi None dihukum (0.5 - y)^2 = 0.25."""
    if not rows:
        return float("nan")
    total = 0.0
    for signals, y in rows:
        p, _ = fuse(signals, weights)
        p = 0.5 if p is None else p
        total += (p - y) ** 2
    return total / len(rows)


def auc_score(y: list[int], s: list[float]) -> float:
    """AUC Mann-Whitney midrank (IMPROVEMENT #3). NaN kalau satu kelas."""
    n = len(y)
    if n == 0 or not (0 < sum(y) < n):
        return float("nan")
    order = sorted(range(n), key=lambda i: s[i])
    ranks = [0.0] * n
    i = 0
    while i < n:  # midrank untuk ties
        j = i
        while j < n and s[order[j]] == s[order[i]]:
            j += 1
        mid = (i + j - 1) / 2.0 + 1.0
        for k in range(i, j):
            ranks[order[k]] = mid
        i = j
    n_pos = sum(y)
    sum_pos = sum(ranks[i] for i in range(n) if y[i] == 1)
    return (sum_pos - n_pos * (n_pos + 1) / 2.0) / (n_pos * (n - n_pos))


def precision_at_s(rows: list[Row], weights: dict[str, float],
                   s_min: float) -> tuple[float, int]:
    """Precision arah pada baris dengan S >= s_min. Return (precision, taken)."""
    taken = correct = 0
    for signals, y in rows:
        p, _ = fuse(signals, weights)
        if p is None:
            continue
        if saturation(p) < s_min:
            continue
        taken += 1
        pred_long = p >= 0.5
        if (y == 1) == pred_long:
            correct += 1
    return (correct / taken if taken else 0.0), taken


# ---------------------------------------------------------------------------
# Optimizer
# ---------------------------------------------------------------------------

def _vec_to_weights(x: list[float]) -> dict[str, float]:
    return {name: float(x[i]) for i, name in enumerate(SIGNAL_NAMES)}


def _optimize_slsqp(rows: list[Row]) -> Optional[dict[str, float]]:
    n = len(SIGNAL_NAMES)
    x0 = [1.0 / n] * n
    res = _scipy_minimize(
        lambda x: brier(_vec_to_weights(x), rows), x0, method="SLSQP",
        bounds=[(W_MIN, W_MAX)] * n,
        constraints=[{"type": "eq", "fun": lambda x: sum(x) - 1.0}],
        options={"maxiter": 200, "ftol": 1e-10},
    )
    if not res.success:
        return None
    return validate_weights(_vec_to_weights(res.x.tolist()))


def _optimize_descent(rows: list[Row], sweeps: int = 8, step0: float = 0.05
                      ) -> dict[str, float]:
    """IMPROVEMENT #5: transfer delta antar pasangan bobot — simplex & bounds
    terjaga persis, deterministik, tanpa scipy."""
    names = list(SIGNAL_NAMES)
    w = neutral_weights()
    best = brier(w, rows)
    step = step0
    for _ in range(sweeps):
        improved = False
        for i in range(len(names)):
            for j in range(len(names)):
                if i == j:
                    continue
                for sign in (+1, -1):
                    cand = dict(w)
                    wi, wj = cand[names[i]] + sign * step, cand[names[j]] - sign * step
                    if not (W_MIN <= wi <= W_MAX and W_MIN <= wj <= W_MAX):
                        continue
                    cand[names[i]], cand[names[j]] = wi, wj
                    b = brier(cand, rows)
                    if b < best - 1e-12:
                        w, best, improved = cand, b, True
        if not improved:
            step /= 2.0
            if step < 1e-4:
                break
    return w


def optimize_weights(rows: list[Row]) -> dict[str, float]:
    if HAVE_SCIPY:
        w = _optimize_slsqp(rows)
        if w is not None:
            return w
    return _optimize_descent(rows)


# ---------------------------------------------------------------------------
# Walk-forward + gerbang live
# ---------------------------------------------------------------------------

def walk_forward_split(n: int, train_frac: float = 0.5,
                       val_frac: float = 0.25) -> tuple[list[int], list[int], list[int]]:
    """IMPROVEMENT #4: kronologis, tanpa shuffle, tanpa tumpang tindih."""
    i_tr, i_va = int(n * train_frac), int(n * (train_frac + val_frac))
    return list(range(i_tr)), list(range(i_tr, i_va)), list(range(i_va, n))


@dataclass
class WeightLabResult:
    weights: dict[str, float]
    used_optimized: bool
    gate: dict[str, bool]
    metrics: dict[str, float]
    reasons: list[str] = field(default_factory=list)


def run_weight_lab(rows: list[Row]) -> WeightLabResult:
    neutral = neutral_weights()
    if len(rows) < 10:
        return WeightLabResult(neutral, False, {}, {}, ["data terlalu sedikit"])

    _, _, te = walk_forward_split(len(rows))
    rows_tr = [rows[i] for i in range(int(len(rows) * 0.5))]
    rows_te = [rows[i] for i in te]
    w_opt = optimize_weights(rows_tr)

    brier_neu = brier(neutral, rows_te)
    brier_opt = brier(w_opt, rows_te)

    ys: list[int] = []
    ss: list[float] = []
    for signals, y in rows_te:
        p, _ = fuse(signals, w_opt)
        if p is not None:
            ys.append(y)
            ss.append(p)
    auc = auc_score(ys, ss)
    prec, taken = precision_at_s(rows_te, w_opt, S_MIN)

    gate = {
        "sample": len(rows_te) >= MIN_SAMPLES,
        "brier": brier_opt <= brier_neu - BRIER_MARGIN,
        "auc": (not math.isnan(auc)) and auc >= AUC_MIN,
        "precision": prec >= PRECISION_MIN and taken >= MIN_PRECISION_SAMPLES,
    }
    ok = all(gate.values())
    reasons = [f"gate gagal: {k}" for k, v in gate.items() if not v]

    final = validate_weights(w_opt) if ok else None
    if final is None:
        final, ok2 = neutral, False
        if ok:
            reasons.append("bobot optimized invalid -> netral")
        ok = False

    metrics = {
        "brier_neutral_test": round(brier_neu, 6),
        "brier_opt_test": round(brier_opt, 6),
        "auc_test": round(auc, 4) if not math.isnan(auc) else float("nan"),
        "precision_test": round(prec, 4),
        "taken_test": float(taken),
        "n_test": float(len(rows_te)),
    }
    return WeightLabResult(final, ok, gate, metrics, reasons)


# ---------------------------------------------------------------------------
# SELF-TEST offline-safe — python3 backend/weight_lab.py
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import random

    rng = random.Random(7)

    # 1. AUC dasar
    assert auc_score([0, 0, 1, 1], [0.1, 0.2, 0.8, 0.9]) == 1.0
    assert auc_score([1, 1, 0, 0], [0.1, 0.2, 0.8, 0.9]) == 0.0
    assert abs(auc_score([0, 1], [0.5, 0.5]) - 0.5) < 1e-12  # ties
    assert math.isnan(auc_score([1, 1], [0.3, 0.7]))          # satu kelas

    # 2. Brier: prediksi None dihukum 0.25
    empty_rows = [({}, 1), ({}, 0)]
    assert abs(brier(neutral_weights(), empty_rows) - 0.25) < 1e-12

    # 3. Split kronologis
    tr, va, te = walk_forward_split(100)
    assert tr[0] == 0 and te[-1] == 99 and not (set(tr) & set(te))

    # 4. Data informatif -> gerbang lolos, bobot dipakai
    rows_info = []
    for _ in range(1200):
        y = 1 if rng.random() < 0.5 else 0
        rows_info.append((
            {"fp": 0.55 if y else 0.45, "trend": 0.90 if y else 0.10,
             "micro": 0.5 + rng.uniform(-0.02, 0.02), "mem": 0.5, "log": 0.5},
            y))
    r1 = run_weight_lab(rows_info)
    assert r1.used_optimized and all(r1.gate.values()), r1
    assert r1.metrics["brier_opt_test"] < r1.metrics["brier_neutral_test"]
    assert validate_weights(r1.weights) is not None

    # 5. Data noise -> gerbang gagal, bobot tetap NETRAL (bukan error)
    rows_noise = [({"fp": 0.5, "trend": 0.5, "micro": 0.5, "mem": 0.5, "log": 0.5},
                   1 if rng.random() < 0.5 else 0) for _ in range(1200)]
    r2 = run_weight_lab(rows_noise)
    assert not r2.used_optimized and r2.weights == neutral_weights()
    assert r2.reasons, "harus ada alasan gate gagal"

    # 6. Fallback descent tanpa scipy: tetap memperbaiki Brier
    w_d = _optimize_descent(rows_info[:600])
    assert brier(w_d, rows_info[:600]) < brier(neutral_weights(), rows_info[:600])

    # 7. Determinisme
    assert run_weight_lab(rows_info).weights == r1.weights

    print(f"demo informatif: gates={r1.gate} brier {r1.metrics['brier_neutral_test']}"
          f" -> {r1.metrics['brier_opt_test']} auc={r1.metrics['auc_test']}")
    print(f"demo noise     : used_optimized={r2.used_optimized} reasons={r2.reasons}")
    print("SELF-TEST OK — weight_lab v2")
