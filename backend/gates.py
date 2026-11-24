"""
Meridian cyt — verdict metadata (utility kecil, dipisah dari screener).

Modul ini hanya menyediakan metadata label dan urutan verdict. Token unlock tidak menjadi input, gate, filter, atau bobot model.
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
