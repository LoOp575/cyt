"""
Meridian cyt — gates & verdict metadata (utility kecil, dipisah dari screener).

Sumber: backend/screening.py v1 di repo Test (fungsi terverifikasi, tidak
diubah secara semantik). Dipisah supaya modul screening_v2 tetap byte-identik
dengan Screner.py repo meri (janji modul ISOLASI tetap terjaga), sementara
gate unlock & label verdict tetap tersedia di level server.
"""

from __future__ import annotations

from typing import Any, Optional

VERDICT_META = {
    "LONG": {"label": "Long candidate", "tone": "long", "rank": 0},
    "WATCH": {"label": "Watchlist", "tone": "watch", "rank": 1},
    "NEUTRAL": {"label": "Neutral", "tone": "neutral", "rank": 2},
    "NO_SIGNAL": {"label": "No signal — distortion", "tone": "flat", "rank": 3},
    "AVOID": {"label": "Avoid", "tone": "avoid", "rank": 4},
    "INSUFFICIENT_DATA": {"label": "Insufficient data", "tone": "flat", "rank": 5},
}


def apply_unlock_gate(
    result: dict[str, Any],
    unlock: Optional[dict[str, Any]],
    watch_pct: float = 1.0,
    avoid_pct: float = 3.0,
) -> bool:
    """Downgrade LONG saat token-unlock material jatuh tempo <=30 hari.

    Mirror red-flag filter: unlock overhang adalah sinyal *supply shock*,
    bukan sinyal demand — hanya bisa mem-veto long, tidak pernah promosi.
    Absent/unavailable unlock feed = no-op murni.

    Threshold: persen market cap (`percentOfMcap`) dalam 30 hari:
      >= avoid_pct (default 3%) -> AVOID (eksklusi keras, seperti instability)
      >= watch_pct (default 1%) -> WATCH (tunggu lewat jendela unlock)
    Return True saat verdict berubah.
    """
    if not unlock or not result.get("ok"):
        return False
    pct = unlock.get("percentOfMcap")
    try:
        pct_f = float(pct) if pct is not None else None
    except (TypeError, ValueError):
        pct_f = None
    if pct_f is None or result.get("verdict") != "LONG":
        result.setdefault("filters", {})["unlockOverhang"] = pct_f is not None and pct_f >= watch_pct
        return False

    result.setdefault("filters", {})["unlockOverhang"] = pct_f >= watch_pct

    target = None
    if pct_f >= avoid_pct:
        target = "AVOID"
    elif pct_f >= watch_pct:
        target = "WATCH"
    if target is None:
        return False

    result["verdict"] = target
    meta = VERDICT_META[target]
    result["verdictLabel"] = meta["label"]
    result["verdictTone"] = meta["tone"]
    when = unlock.get("date") or "within 30d"
    result.setdefault("reasons", []).append(
        f"Supply overhang: unlock of ~{pct_f:.1f}% of market cap due {when} "
        f"(>= {watch_pct if target == 'WATCH' else avoid_pct}% gate) — long vetoed (unlock-overhang rule)."
    )
    return True
