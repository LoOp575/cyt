"""
Meridian v2 — Neuron Core (audited & improved).
================================================
5 lapis: Signals -> Fusion -> Saturation -> Veto -> Decision.

RUMUS LOCKED:
  Fusion     : P_fused = prod_i p_i^w_i   (geometric mean berbobot, sum w = 1)
  Saturation : S = 2 * |P_fused - 0.5|
  Score      : conf_dir * S * prod(veto)   (conf_long = P, conf_short = 1 - P)
  Decision   : trade jika score >= SCORE_MIN dan semua veto lolos

PENINGKATAN vs rancangan awal (hasil audit):
 1. Sinyal hilang (None) ditangani JUJUR: bobot dinormalisasi ulang atas
    sumber yang ada — TIDAK mengarang nilai 0.5.
 2. p di-clip ke [0.01, 0.99] — geometric mean tidak degenerate (p=0 -> P=0).
 3. Bobot tervalidasi (bounds [0.05, 0.45], sum=1); invalid -> fallback netral,
    neuron tetap jalan, bukan crash.
 4. Veto FP dihitung INTERNAL (arah vs p_fp) — tidak mungkin lupa dipasang caller.
 5. Simetris LONG/SHORT: conf_short = 1 - P_fused, bukan sisi long saja.
 6. Pure functions, tanpa dependensi eksternal. Self-test: python3 backend/neuron.py
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------------------
# Konstanta LOCKED
# ---------------------------------------------------------------------------

SIGNAL_NAMES = ("fp", "trend", "micro", "mem", "log")
P_CLIP_LO = 0.01
P_CLIP_HI = 0.99
W_MIN = 0.05
W_MAX = 0.45
SUM_TOL = 1e-3


@dataclass
class NeuronConfig:
    score_min: float = 0.18   # ambang trade; bisa dikalibrasi Weight Lab
    min_sources: int = 2      # minimal sumber aktif baru boleh memutuskan
    max_size: float = 0.05    # max 5% equity per trade


DEFAULT_CFG = NeuronConfig()


# ---------------------------------------------------------------------------
# Lapis 1-2: Fusion (geometric mean berbobot)
# ---------------------------------------------------------------------------

def neutral_weights() -> dict[str, float]:
    n = len(SIGNAL_NAMES)
    return {name: 1.0 / n for name in SIGNAL_NAMES}


def validate_weights(weights: Optional[dict[str, float]]) -> Optional[dict[str, float]]:
    """IMPROVEMENT #3: bobot invalid -> None (pemanggil fallback ke netral)."""
    if not weights or set(weights.keys()) != set(SIGNAL_NAMES):
        return None
    for w in weights.values():
        if not (W_MIN - SUM_TOL <= float(w) <= W_MAX + SUM_TOL):
            return None
    if abs(sum(float(w) for w in weights.values()) - 1.0) > SUM_TOL:
        return None
    return {k: float(v) for k, v in weights.items()}


def clip_p(p: float) -> float:
    """IMPROVEMENT #2: clip ke [0.01, 0.99]."""
    return max(P_CLIP_LO, min(P_CLIP_HI, float(p)))


def fuse(p: dict[str, Optional[float]],
         weights: Optional[dict[str, float]] = None
         ) -> tuple[Optional[float], list[str]]:
    """P_fused = prod p_i^w_i. Sinyal None -> dilewati, bobot sisa
    dinormalisasi (IMPROVEMENT #1). Return (P_fused|None, sumber terpakai)."""
    w = validate_weights(weights) or neutral_weights()
    used = [name for name in SIGNAL_NAMES if p.get(name) is not None]
    if not used:
        return None, []
    total_w = sum(w[name] for name in used)
    if total_w <= 0.0:
        return None, used
    logp = 0.0
    for name in used:
        logp += (w[name] / total_w) * math.log(clip_p(p[name]))
    return math.exp(logp), used


def saturation(p_fused: float) -> float:
    return 2.0 * abs(p_fused - 0.5)


# ---------------------------------------------------------------------------
# Lapis 3-5: Veto + Decision
# ---------------------------------------------------------------------------

@dataclass
class NeuronDecision:
    p_fused: Optional[float]
    sat: float
    score: float
    direction: str          # "LONG" / "SHORT" / "NONE"
    size_frac: float        # fraksi equity (0 = no trade)
    trade: bool
    used_sources: list[str]
    vetoes: dict[str, bool]
    reasons: list[str] = field(default_factory=list)


def decide(signals: dict[str, Optional[float]],
           weights: Optional[dict[str, float]] = None,
           vetoes: Optional[dict[str, bool]] = None,
           cfg: Optional[NeuronConfig] = None) -> NeuronDecision:
    """Veto caller: liquidity / volatility / memory (True = lolos).
    Veto fp dihitung internal (IMPROVEMENT #4)."""
    cfg = cfg or DEFAULT_CFG
    vetoes_in = dict(vetoes or {})
    reasons: list[str] = []

    p_fused, used = fuse(signals, weights)
    if p_fused is None:
        return NeuronDecision(None, 0.0, 0.0, "NONE", 0.0, False, [], {},
                              ["tidak ada sinyal"])
    if len(used) < cfg.min_sources:
        return NeuronDecision(p_fused, saturation(p_fused), 0.0, "NONE", 0.0,
                              False, used, {},
                              [f"sumber {len(used)} < min {cfg.min_sources}"])

    S = saturation(p_fused)
    direction = "LONG" if p_fused >= 0.5 else "SHORT"

    v: dict[str, bool] = {
        "liquidity": bool(vetoes_in.get("liquidity", True)),
        "volatility": bool(vetoes_in.get("volatility", True)),
        "memory": bool(vetoes_in.get("memory", True)),
    }
    p_fp = signals.get("fp")
    if p_fp is not None:
        v["fp"] = (p_fp >= 0.5) if direction == "LONG" else (p_fp < 0.5)
    veto_pass = all(v.values())

    conf = p_fused if direction == "LONG" else 1.0 - p_fused  # IMPROVEMENT #5
    score = conf * S * (1.0 if veto_pass else 0.0)

    if not veto_pass:
        failed = [k for k, ok in v.items() if not ok]
        reasons.append("veto: " + ",".join(failed))
    elif score < cfg.score_min:
        reasons.append(f"score {score:.3f} < min {cfg.score_min}")

    trade = veto_pass and score >= cfg.score_min
    size_frac = round(cfg.max_size * S, 4) if trade else 0.0

    return NeuronDecision(p_fused, round(S, 6), round(score, 6), direction,
                          size_frac, trade, used, v, reasons)


# ---------------------------------------------------------------------------
# SELF-TEST offline-safe — python3 backend/neuron.py
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # 1. Fusion math murni
    P, used = fuse({"fp": 0.8, "trend": 0.6})
    assert abs(P - math.sqrt(0.8 * 0.6)) < 1e-9 and set(used) == {"fp", "trend"}

    # 2. Soft-AND: satu sumber 0.05 menyeret P ke bawah keras
    P2, _ = fuse({"fp": 0.9, "trend": 0.9, "micro": 0.05})
    assert P2 < 0.35

    # 3. Saturation
    assert abs(saturation(0.75) - 0.5) < 1e-9

    # 4. Veto caller mematikan trade
    d = decide({"fp": 0.8, "trend": 0.8}, vetoes={"liquidity": False})
    assert not d.trade and d.score == 0.0 and "liquidity" in d.reasons[0]

    # 5. Veto FP internal: arah LONG tapi p_fp < 0.5 -> mati
    d5 = decide({"fp": 0.3, "trend": 0.9, "micro": 0.9})
    assert not d5.trade and d5.vetoes.get("fp") is False

    # 6. Sinyal hilang -> renormalisasi jujur; semua hilang -> NONE
    P6, used6 = fuse({"fp": None, "trend": 0.7, "micro": 0.7})
    assert set(used6) == {"trend", "micro"} and abs(P6 - 0.7) < 1e-9
    d6 = decide({})
    assert d6.direction == "NONE" and not d6.trade

    # 6b. Sumber terlalu sedikit -> no trade
    d6b = decide({"fp": 0.8})
    assert not d6b.trade and "min" in d6b.reasons[0]

    # 7. Bobot invalid -> fallback netral, tetap jalan (bukan crash)
    d7 = decide({"fp": 0.8, "trend": 0.8}, weights={"fp": 0.9, "trend": 0.9})
    assert d7.trade

    # 8. Simetri SHORT
    d8 = decide({"fp": 0.2, "trend": 0.2, "micro": 0.2, "mem": 0.2, "log": 0.2})
    assert d8.direction == "SHORT" and d8.trade

    # 9. Size cap
    assert d8.size_frac <= DEFAULT_CFG.max_size + 1e-9

    # Demo kecil
    demo = decide({"fp": 0.72, "trend": 0.65, "micro": 0.80, "mem": None, "log": 0.60},
                  vetoes={"liquidity": True, "volatility": True, "memory": True})
    print(f"demo: P={demo.p_fused:.3f} S={demo.sat:.3f} score={demo.score:.3f} "
          f"dir={demo.direction} size={demo.size_frac} trade={demo.trade}")

    print("SELF-TEST OK — neuron v2")
