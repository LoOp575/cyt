"""Persistent store and five-minute evaluation cycle for CYT Neuron.

Uses Supabase PostgREST with a server-only service-role key. No local file writes:
Vercel instances are ephemeral. Predictions are append-only; outcomes are patched
only once when their target candle has closed.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Any

import httpx

TABLE_MODELS = "neuron_models"
TABLE_PREDICTIONS = "neuron_predictions"
TABLE_AUDITS = "neuron_audits"
SYMBOL = "BTCUSDT"
INTERVAL_MS = 300_000


def is_configured() -> bool:
    return bool(os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_SERVICE_ROLE_KEY"))


def _headers() -> dict[str, str]:
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _base() -> str:
    return os.getenv("SUPABASE_URL", "").rstrip("/") + "/rest/v1"


async def _request(client: httpx.AsyncClient, method: str, table: str,
                   params: dict[str, str] | None = None, payload: Any = None,
                   prefer: str | None = None) -> list[dict[str, Any]]:
    headers = _headers()
    if prefer:
        headers["Prefer"] = prefer
    response = await client.request(method, f"{_base()}/{table}", params=params,
                                    json=payload, headers=headers, timeout=20)
    if response.status_code >= 400:
        raise RuntimeError(f"Supabase {table}: HTTP {response.status_code} {response.text[:300]}")
    if not response.content:
        return []
    try:
        body = response.json()
        return body if isinstance(body, list) else [body]
    except ValueError:
        return []


def _iso(ms: int | float) -> str:
    return datetime.fromtimestamp(float(ms) / 1000, tz=timezone.utc).isoformat()


def _checksum(state: dict[str, Any]) -> str:
    raw = json.dumps(state, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def _load_model(client: httpx.AsyncClient):
    from backend.neuron_core import Neuron
    rows = await _request(client, "GET", TABLE_MODELS,
                          {"id": "eq.BTCUSDT", "select": "*", "limit": "1"})
    if rows:
        row = rows[0]
        return row, Neuron.from_dict(row.get("state") or {})
    neuron = Neuron()
    state = neuron.to_dict()
    payload = {"id": SYMBOL, "symbol": SYMBOL, "version": 1, "state": state,
               "checksum": _checksum(state)}
    created = await _request(client, "POST", TABLE_MODELS, payload=payload,
                             prefer="return=representation")
    return (created[0] if created else payload), neuron


async def _latest_closed_klines(client: httpx.AsyncClient):
    from backend.market_data import _parse_klines
    url = "https://api.binance.com/api/v3/klines"
    response = await client.get(url, params={"symbol": SYMBOL, "interval": "5m", "limit": "120"},
                                timeout=15)
    response.raise_for_status()
    now_ms = datetime.now(timezone.utc).timestamp() * 1000
    rows = [c for c in _parse_klines(response.json()) if c["date"] + INTERVAL_MS <= now_ms]
    if len(rows) < 61:
        raise RuntimeError(f"Need 61 closed 5m candles, received {len(rows)}.")
    return rows


async def _label_matured(client: httpx.AsyncClient, candles: list[dict[str, Any]]) -> int:
    rows = await _request(client, "GET", TABLE_PREDICTIONS, {
        "select": "id,candle_open_at,target_at,reference_price,prediction_value,probability_up,direction",
        "status": "eq.pending", "target_at": f"lte.{datetime.now(timezone.utc).isoformat()}",
        "order": "target_at.asc", "limit": "100",
    })
    by_open = {int(c["date"]): c for c in candles}
    labeled = 0
    for row in rows:
        target = datetime.fromisoformat(row["target_at"].replace("Z", "+00:00")).timestamp() * 1000
        target_open = int(target) - INTERVAL_MS
        candle = by_open.get(target_open)
        if not candle or not row.get("reference_price"):
            continue
        actual_price = float(candle["close"])
        actual_return = actual_price / float(row["reference_price"]) - 1.0
        actual_direction = "UP" if actual_return > 0 else "DOWN" if actual_return < 0 else "FLAT"
        probability_up = float(row["probability_up"])
        actual_up = 1.0 if actual_return > 0 else 0.0
        brier = (probability_up - actual_up) ** 2
        update = {
            "status": "labeled", "actual_price": actual_price,
            "actual_return": actual_return, "actual_direction": actual_direction,
            "is_correct": row["direction"] == actual_direction,
            "brier_score": brier, "labeled_at": datetime.now(timezone.utc).isoformat(),
        }
        await _request(client, "PATCH", TABLE_PREDICTIONS,
                       {"id": f"eq.{row['id']}", "status": "eq.pending"},
                       payload=update, prefer="return=minimal")
        labeled += 1
    return labeled


async def _write_audit(client: httpx.AsyncClient, model_version: int, weights: dict[str, float]):
    rows = await _request(client, "GET", TABLE_PREDICTIONS, {
        "select": "direction,actual_direction,actual_return,probability_up,brier_score,features,contributions",
        "status": "eq.labeled", "order": "labeled_at.desc", "limit": "1000",
    })
    n = len(rows)
    if n:
        accuracy = sum(1 for r in rows if r["direction"] == r["actual_direction"]) / n
        brier = sum(float(r.get("brier_score") or 0) for r in rows) / n
        mean_abs = sum(abs(float(r.get("actual_return") or 0)) for r in rows) / n
    else:
        accuracy = brier = mean_abs = None
    metrics = {"samples": n, "directionalAccuracy": accuracy,
               "brierScore": brier, "meanAbsoluteReturn": mean_abs}
    diagnostics: dict[str, Any] = {}
    feature_keys = ("screenSignal", "demandQuality", "stability", "fpStable",
                    "fpTail", "fpLiveDir", "rvol", "vwapDist")
    for key in feature_keys:
        pairs = [(float((r.get("features") or {}).get(key) or 0),
                  float(r.get("actual_return") or 0)) for r in rows]
        if len(pairs) >= 2:
            xbar = sum(x for x, _ in pairs) / len(pairs)
            ybar = sum(y for _, y in pairs) / len(pairs)
            cov = sum((x-xbar)*(y-ybar) for x,y in pairs) / len(pairs)
            vx = sum((x-xbar)**2 for x,_ in pairs) / len(pairs)
            vy = sum((y-ybar)**2 for _,y in pairs) / len(pairs)
            corr = cov / ((vx*vy)**0.5) if vx > 0 and vy > 0 else None
            abs_contrib = [abs(float((r.get("contributions") or {}).get(key) or 0)) for r in rows]
            diagnostics[key] = {
                "samples": len(pairs),
                "weight": float(weights.get(key, 0.0)),
                "returnCorrelation": corr,
                "meanAbsContribution": sum(abs_contrib) / len(abs_contrib) if abs_contrib else 0.0,
                "directionalAlignment": None if corr is None or abs(corr) < 1e-9 or abs(float(weights.get(key, 0.0))) < 1e-9 else (float(weights.get(key, 0.0)) * corr > 0),
            }
    await _request(client, "POST", TABLE_AUDITS, payload={
        "symbol": SYMBOL, "sample_count": n, "metrics": metrics,
        "feature_diagnostics": diagnostics, "model_version": model_version,
    }, prefer="return=minimal")
    return {"metrics": metrics, "featureDiagnostics": diagnostics}


async def run_cycle(client: httpx.AsyncClient) -> dict[str, Any]:
    from backend.neuron_core import build_dendrites
    from backend.screening_v2 import compute_features_v2

    candles = await _latest_closed_klines(client)
    latest = candles[-1]
    screen = compute_features_v2(candles, regime=None)
    if not screen.get("ok"):
        raise RuntimeError(screen.get("reason") or "screening-v2 did not score the 5m candle series")
    features = build_dendrites(screen=screen)
    model_row, neuron = await _load_model(client)
    prediction = neuron.predict(features)
    y = float(prediction["y"])
    direction = "UP" if y > 0 else "DOWN" if y < 0 else "FLAT"
    probability_up = max(0.0, min(1.0, (y + 1.0) / 2.0))
    candle_open_ms = int(latest["date"])
    target_ms = candle_open_ms + 2 * INTERVAL_MS
    state = neuron.to_dict()
    record = {
        "symbol": SYMBOL, "candle_open_at": _iso(candle_open_ms),
        "target_at": _iso(target_ms), "reference_price": float(latest["close"]),
        "prediction_value": y, "direction": direction, "probability_up": probability_up,
        "features": features, "contributions": prediction.get("contributions") or {},
        "weights_snapshot": state.get("weights") or {},
        "weights_version": int(model_row.get("version") or 1),
        "model_version": prediction.get("model") or "unknown",
        "source": "binance-spot-klines", "feature_timeframe": "5m", "status": "pending",
    }
    inserted = await _request(client, "POST", TABLE_PREDICTIONS, payload=record,
                              prefer="resolution=ignore-duplicates,return=representation")
    labeled = await _label_matured(client, candles)
    audit = await _write_audit(client, int(model_row.get("version") or 1), neuron.weights)
    return {
        "ok": True, "symbol": SYMBOL, "cycle": "5m",
        "predictionCreated": bool(inserted), "prediction": inserted[0] if inserted else None,
        "labeledNow": labeled, "audit": audit,
        "note": "5m feature inputs are experimental/provisional; champion weights are not auto-mutated.",
    }


async def status(client: httpx.AsyncClient) -> dict[str, Any]:
    model_rows = await _request(client, "GET", TABLE_MODELS,
                                {"id": "eq.BTCUSDT", "select": "*", "limit": "1"})
    counts = await _request(client, "GET", TABLE_PREDICTIONS,
                            {"select": "id,status", "limit": "1000"})
    latest_rows = await _request(client, "GET", TABLE_PREDICTIONS,
                                 {"select": "*", "order": "created_at.desc", "limit": "1"})
    pending = sum(1 for r in counts if r.get("status") == "pending")
    labeled = sum(1 for r in counts if r.get("status") == "labeled")
    latest = latest_rows[0] if latest_rows else None
    model = model_rows[0] if model_rows else {}
    age_seconds = None
    if latest and latest.get("created_at"):
        age_seconds = max(0.0, (datetime.now(timezone.utc) -
            datetime.fromisoformat(latest["created_at"].replace("Z", "+00:00"))).total_seconds())
    checksum_valid = bool(model.get("state") and model.get("checksum") and
                          _checksum(model["state"]) == model["checksum"])
    return {
        "ok": True, "configured": True, "live": bool(age_seconds is not None and age_seconds < 600),
        "latestAgeSeconds": age_seconds,
        "cronReady": bool(os.getenv("NEURON_CRON_SECRET") or os.getenv("CRON_SECRET")),
        "predictionCount": len(counts), "pendingCount": pending, "labeledCount": labeled,
        "latestPrediction": latest,
        "model": {**model, "checksumValid": checksum_valid},
        "featureHealth": {k: bool(latest and k in (latest.get("features") or {}))
                          for k in ("screenSignal", "demandQuality", "stability", "fpStable",
                                    "fpTail", "fpLiveDir", "rvol", "vwapDist")},
    }


async def journal(client: httpx.AsyncClient, limit: int):
    return await _request(client, "GET", TABLE_PREDICTIONS, {
        "select": "*", "order": "created_at.desc", "limit": str(limit),
    })


async def audit(client: httpx.AsyncClient):
    rows = await _request(client, "GET", TABLE_AUDITS, {
        "select": "*", "order": "created_at.desc", "limit": "1",
    })
    if not rows:
        return {"ok": True, "configured": True, "metrics": {"samples": 0}, "generatedAt": None}
    row = rows[0]
    return {"ok": True, "configured": True, "metrics": row.get("metrics") or {},
            "featureDiagnostics": row.get("feature_diagnostics") or {},
            "generatedAt": row.get("created_at")}
