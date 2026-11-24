"""
Meridian v2 — Fokker-Planck Engine v2 (audited & improved).
============================================================
Menyalakan sinyal `fp` di neuron_live: probabilitas harga naik pada
horizon, dihitung dari PDE Fokker-Planck di ruang log-price.

Self-test offline-safe: python3 backend/fp_v2_engine.py
"""

from __future__ import annotations

import json
import math
import urllib.request
from typing import Any, Optional

EWMA_LAMBDA = 0.94
BURN_IN = 30
GRID_N = 401
GRID_WIDTH_SIGMA = 6.0
CFL_SAFETY = 0.4
MAX_SUBSTEPS = 20000
MASS_TOL = 0.02
KAPPA_MAX = 2.0
EPS_P = 1e-12


def _fetch_klines_sync(symbol: str, interval: str = "1d", limit: int = 120) -> list[dict[str, float]]:
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol.upper()}&interval={interval}&limit={limit}"
    req = urllib.request.Request(url, headers={"User-Agent": "Meridian/2.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        raw = json.loads(resp.read().decode("utf-8"))
    return [{"date": float(r[0]), "open": float(r[1]), "high": float(r[2]),
             "low": float(r[3]), "close": float(r[4]), "volume": float(r[5])} for r in raw]


def estimate_returns(closes: list[float]) -> list[float]:
    rets: list[float] = []
    for i in range(1, len(closes)):
        if closes[i - 1] > 0 and closes[i] > 0:
            rets.append(math.log(closes[i] / closes[i - 1]))
    return rets


def ewma_sigma(rets: list[float]) -> tuple[float, bool]:
    if len(rets) < 2:
        return 0.0, False
    mean_r = sum(rets) / len(rets)
    w, wsum, acc = 1.0, 0.0, 0.0
    for r in reversed(rets):
        acc += w * (r - mean_r) ** 2
        wsum += w
        w *= EWMA_LAMBDA
    return math.sqrt(max(acc / wsum, EPS_P)), len(rets) >= BURN_IN


def adaptive_kappa(rets: list[float]) -> float:
    if len(rets) < BURN_IN:
        return 0.0
    n = len(rets)
    m = sum(rets) / n
    den = sum((r - m) ** 2 for r in rets)
    if den <= EPS_P:
        return 0.0
    num = sum((rets[i] - m) * (rets[i - 1] - m) for i in range(1, n))
    rho = num / den
    return KAPPA_MAX * max(0.0, -rho)


def solve_fp(x0: float, theta: float, mu0: float, sigma: float, kappa: float,
             horizon_days: float, grid_n: int = GRID_N
             ) -> tuple[list[float], list[float], float]:
    T = max(horizon_days, 1e-6)
    half = GRID_WIDTH_SIGMA * sigma * math.sqrt(T)
    dx = (2.0 * half) / (grid_n - 1)
    xs = [x0 - half + i * dx for i in range(grid_n)]

    sig0 = 3.0 * dx
    p = [math.exp(-((x - x0) ** 2) / (2.0 * sig0 * sig0)) for x in xs]
    norm = sum(p) * dx
    p = [pi / norm for pi in p]

    mu_max = abs(mu0) + kappa * (2.0 * half)
    dt = CFL_SAFETY * dx * dx / (sigma * sigma + mu_max * dx + EPS_P)
    n_steps = int(math.ceil(T / dt))
    if n_steps > MAX_SUBSTEPS:
        return xs, p, float("nan")
    dt_a = T / n_steps

    s2 = sigma * sigma
    for _ in range(n_steps):
        p_new = [0.0] * grid_n
        for i in range(grid_n):
            if i < grid_n - 1:
                xm = 0.5 * (xs[i] + xs[i + 1])
                mu_r = mu0 + kappa * (theta - xm)
                f_r = mu_r * (p[i] if mu_r >= 0 else p[i + 1])
            else:
                f_r = 0.0
            if i > 0:
                xm = 0.5 * (xs[i - 1] + xs[i])
                mu_l = mu0 + kappa * (theta - xm)
                f_l = mu_l * (p[i - 1] if mu_l >= 0 else p[i])
            else:
                f_l = 0.0
            adv = -(f_r - f_l) / dx
            d2 = (p[i + 1] - 2.0 * p[i] + p[i - 1]) / (dx * dx) \
                if 0 < i < grid_n - 1 else 0.0
            v = p[i] + dt_a * (adv + 0.5 * s2 * d2)
            p_new[i] = v if v > 0.0 else 0.0
        p = p_new

    mass = sum(p) * dx
    return xs, p, abs(mass - 1.0)


def fp_probability_from_closes(closes: list[float], horizon_days: float
                               ) -> tuple[Optional[float], dict[str, Any]]:
    if len(closes) < 20:
        return None, {"reason": "data < 20"}
    rets = estimate_returns(closes)
    sigma, burned = ewma_sigma(rets)
    if sigma <= 0:
        return None, {"reason": "sigma nol"}
    kappa = adaptive_kappa(rets)
    mu0 = sum(rets) / len(rets)
    x0 = math.log(closes[-1])
    tail = closes[-60:]
    theta = math.log(sum(tail) / len(tail))

    xs, dens, drift = solve_fp(x0, theta, mu0, sigma, kappa, horizon_days)
    if math.isnan(drift):
        return None, {"reason": "solver melewati batas substep"}

    dxg = xs[1] - xs[0]
    p_up = sum(d for x, d in zip(xs, dens) if x >= x0) * dxg
    p_up = max(EPS_P, min(1.0 - EPS_P, p_up))

    w_data = min(1.0, len(rets) / (3.0 * BURN_IN))
    w_mass = max(0.0, 1.0 - drift / MASS_TOL)
    conf = w_data * w_mass * (1.0 if burned else 0.5)
    p_final = conf * p_up + (1.0 - conf) * 0.5

    diag = {"sigma": round(sigma, 6), "kappa": round(kappa, 4),
            "mu0": round(mu0, 6), "mass_drift": round(drift, 6),
            "p_raw": round(p_up, 4), "confidence": round(conf, 4),
            "burned_in": 1.0 if burned else 0.0}
    return p_final, diag


def predict(symbol: str, horizon_h: float = 24.0) -> Optional[float]:
    try:
        kl = _fetch_klines_sync(symbol, "1d", limit=120)
    except Exception:
        return None
    closes = [c["close"] for c in kl]
    p, _diag = fp_probability_from_closes(closes, horizon_h / 24.0)
    return p


if __name__ == "__main__":
    s, burned = ewma_sigma([0.01] * 10)
    assert not burned and s > 0
    _, burned2 = ewma_sigma([0.01] * 60)
    assert burned2

    rets_mr = [0.02, -0.02] * 40
    rets_tr = [0.01 + 0.0001 * i for i in range(90)]
    assert adaptive_kappa(rets_mr) > 0.5
    assert adaptive_kappa(rets_tr) == 0.0

    x0, mu, sig, T = 0.0, 0.001, 0.02, 5.0
    xs, dens, drift = solve_fp(x0, x0, mu, sig, 0.0, T)
    assert drift < MASS_TOL, drift
    dxg = xs[1] - xs[0]
    p_up = sum(d for x, d in zip(xs, dens) if x >= x0) * dxg
    z = mu * math.sqrt(T) / sig
    p_exact = 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))
    assert abs(p_up - p_exact) < 0.03, (p_up, p_exact)

    xs4, dens4, _ = solve_fp(0.0, -0.05, 0.0, 0.02, 2.0, 2.0, grid_n=201)
    p4 = sum(d for x, d in zip(xs4, dens4) if x >= 0.0) * (xs4[1] - xs4[0])
    assert p4 < 0.3, p4

    p5, _ = fp_probability_from_closes([100.0] * 10, 1.0)
    assert p5 is None

    import random
    rng = random.Random(11)
    price, closes = 100.0, []
    for _ in range(120):
        closes.append(price)
        price *= math.exp(rng.gauss(0.0, 0.02))
    p6, diag = fp_probability_from_closes(closes, 1.0)
    assert p6 is not None and 0.0 < p6 < 1.0
    assert 0.0 <= diag["confidence"] <= 1.0 and diag["burned_in"] == 1.0

    print(f"demo diag: {diag}")
    print("SELF-TEST OK — fp_v2_engine (fokker_planck v2)")
