"""
Meridian v2 — Neuron Live (sistem saraf hidup, audited & improved).
====================================================================
LOOP TERTUTUP:  scan -> sinyal -> keputusan -> JURNAL -> label outcome
                -> Weight Lab -> bobot baru -> scan (dengan bobot baru)

Self-test offline-safe: python3 backend/neuron_live.py
"""

from __future__ import annotations

import json
import math
import os
import time
import urllib.request
from typing import Any, NamedTuple, Optional

try:
    from .neuron import SIGNAL_NAMES, decide, neutral_weights, validate_weights
    from .weight_lab import run_weight_lab
except ImportError:
    from neuron import SIGNAL_NAMES, decide, neutral_weights, validate_weights
    from weight_lab import run_weight_lab

DATA_DIR = os.environ.get("MERIDIAN_DATA_DIR", "data")
PRED_FILE = os.path.join(DATA_DIR, "predictions.jsonl")
OUT_FILE = os.path.join(DATA_DIR, "outcomes.jsonl")
WEIGHTS_FILE = os.path.join(DATA_DIR, "weights.json")

WATCHLIST = [s.strip().upper() for s in
             os.environ.get("MERIDIAN_WATCHLIST", "BTCUSDT,ETHUSDT,SOLUSDT").split(",") if s.strip()]
HORIZON_H = float(os.environ.get("MERIDIAN_HORIZON_H", "24"))
SCAN_INTERVAL_S = float(os.environ.get("MERIDIAN_SCAN_INTERVAL_S", "300"))
LEARN_MIN_LABELED = int(os.environ.get("MERIDIAN_LEARN_MIN", "200"))


def _get_json(url: str) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": "Meridian/2.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _fetch_klines_sync(symbol: str, interval: str = "1d", limit: int = 30) -> list[dict[str, float]]:
    raw = _get_json(f"https://api.binance.com/api/v3/klines?symbol={symbol.upper()}&interval={interval}&limit={limit}")
    return [{"date": float(r[0]), "open": float(r[1]), "high": float(r[2]),
             "low": float(r[3]), "close": float(r[4]), "volume": float(r[5])} for r in raw]


def _try_call(module_name: str, fn_names: tuple[str, ...], *args: Any) -> Any:
    for mod_path in (f"backend.{module_name}", module_name):
        try:
            mod = __import__(mod_path, fromlist=["*"])
            for fn in fn_names:
                f = getattr(mod, fn, None)
                if callable(f):
                    return f(*args)
        except Exception:
            continue
    return None


def signal_fp(symbol: str) -> Optional[float]:
    v = _try_call("fp_v2_engine", ("predict",), symbol)
    return float(v) if isinstance(v, (int, float)) and math.isfinite(v) else None


def signal_mem(symbol: str) -> Optional[float]:
    v = _try_call("neuron_memory_v2", ("predict",), symbol)
    return float(v) if isinstance(v, (int, float)) and math.isfinite(v) else None


def signal_log(symbol: str) -> Optional[float]:
    v = _try_call("neuron_logistics", ("predict",), symbol)
    return float(v) if isinstance(v, (int, float)) and math.isfinite(v) else None


def signal_trend(symbol: str) -> Optional[float]:
    try:
        kl = _fetch_klines_sync(symbol, "1d", limit=30)
        closes = [c["close"] for c in kl]
        sma = sum(closes[-20:]) / len(closes[-20:])
        roc = closes[-1] / closes[-6] - 1.0
        z = 8.0 * (closes[-1] / sma - 1.0) + 10.0 * roc
        return 1.0 / (1.0 + math.exp(-z))
    except Exception:
        return None


def signal_micro(symbol: str) -> Optional[float]:
    try:
        sym = symbol.upper()
        ob = _get_json(f"https://api.binance.com/api/v3/depth?symbol={sym}&limit=50")
        bid = sum(float(b[1]) for b in ob.get("bids", []))
        ask = sum(float(a[1]) for a in ob.get("asks", []))
        imb = (bid - ask) / (bid + ask) if (bid + ask) > 0 else 0.0
        tr = _get_json(f"https://api.binance.com/api/v3/trades?symbol={sym}&limit=100")
        buy = sum(float(t["qty"]) for t in tr if t.get("isBuyerMaker") is False)
        tot = sum(float(t["qty"]) for t in tr)
        taker = (buy / tot) if tot > 0 else 0.5
        p = 0.5 + 0.5 * (0.6 * imb + 0.4 * (taker - 0.5) * 2.0)
        return max(0.01, min(0.99, p))
    except Exception:
        return None


def collect_signals(symbol: str) -> dict[str, Optional[float]]:
    return {
        "fp": signal_fp(symbol),
        "trend": signal_trend(symbol),
        "micro": signal_micro(symbol),
        "mem": signal_mem(symbol),
        "log": signal_log(symbol),
    }


def _append_jsonl(path: str, obj: dict[str, Any]) -> None:
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def _load_jsonl(path: str) -> list[dict[str, Any]]:
    if not os.path.exists(path):
        return []
    out: list[dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except ValueError:
                    continue
    return out


def load_active_weights() -> tuple[dict[str, float], int]:
    try:
        with open(WEIGHTS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        w = validate_weights(data.get("weights"))
        if w:
            return w, int(data.get("version", 1))
    except Exception:
        pass
    return neutral_weights(), 0


def save_weights(w: dict[str, float], metrics: dict[str, float]) -> int:
    _, ver = load_active_weights()
    new_ver = ver + 1
    d = os.path.dirname(WEIGHTS_FILE)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(WEIGHTS_FILE, "w", encoding="utf-8") as f:
        json.dump({"version": new_ver, "updated_ts": time.time(),
                   "weights": w, "metrics": metrics}, f, indent=2)
    return new_ver


class FinalDecision(NamedTuple):
    d: Any
    trade: bool
    size_frac: float
    vetoes: list[str]
    reasons: list[str]


try:
    from .neuron_memory_v2 import load_memory_rows, memory_veto
    from .neuron_logistics import logistics_diag, veto_from_diag
    HAVE_VETO_MODULES = True
except ImportError:
    try:
        from neuron_memory_v2 import load_memory_rows, memory_veto
        from neuron_logistics import logistics_diag, veto_from_diag
        HAVE_VETO_MODULES = True
    except ImportError:
        HAVE_VETO_MODULES = False

LOG_DIAG_TTL_S = 60.0
_log_diag_cache: dict[str, tuple[float, Optional[dict]]] = {}


def _log_diag_cached(symbol: str) -> Optional[dict]:
    now = time.time()
    hit = _log_diag_cache.get(symbol)
    if hit is not None and now - hit[0] < LOG_DIAG_TTL_S:
        return hit[1]
    diag: Optional[dict] = None
    try:
        diag = logistics_diag(symbol) if logistics_diag else None
    except Exception:
        diag = None
    _log_diag_cache[symbol] = (now, diag)
    return diag


def apply_final_vetoes(symbol: str, signals: dict[str, Optional[float]],
                       d: Any, mem_rows: Optional[list] = None,
                       log_diag: Any = "auto") -> FinalDecision:
    trade, size = bool(d.trade), float(getattr(d, "size_frac", 0.0))
    raw_v = getattr(d, "vetoes", None)
    if isinstance(raw_v, dict):
        vetoes = [k for k, ok in raw_v.items() if not ok]
    else:
        vetoes = list(raw_v or [])
    reasons = list(getattr(d, "reasons", []) or [])
    if trade and HAVE_VETO_MODULES:
        try:
            rows = load_memory_rows() if mem_rows is None else mem_rows
            if not memory_veto(signals, rows):
                vetoes.append("mem")
                reasons.append("veto memory: setup serupa terbukti sering gagal")
        except Exception:
            pass
        try:
            diag = _log_diag_cached(symbol) if log_diag == "auto" else log_diag
            if not veto_from_diag(diag):
                vetoes.append("log")
                reasons.append("veto logistik: biaya eksekusi > edge arah")
        except Exception:
            pass
        if "mem" in vetoes or "log" in vetoes:
            trade, size = False, 0.0
    return FinalDecision(d, trade, size, vetoes, reasons)


def decide_with_vetoes(symbol: str, signals: dict[str, Optional[float]],
                       weights: dict[str, float]) -> FinalDecision:
    return apply_final_vetoes(symbol, signals, decide(signals, weights=weights))


def scan_once(verbose: bool = True) -> list[dict[str, Any]]:
    weights, ver = load_active_weights()
    results: list[dict[str, Any]] = []
    for symbol in WATCHLIST:
        signals = collect_signals(symbol)
        entry_price: Optional[float] = None
        try:
            t = _get_json(f"https://api.binance.com/api/v3/ticker/24hr?symbol={symbol.upper()}")
            entry_price = float(t["lastPrice"])
        except Exception:
            pass
        fd = decide_with_vetoes(symbol, signals, weights)
        d = fd.d
        row = {
            "id": f"{int(time.time())}-{symbol}",
            "ts": time.time(), "symbol": symbol,
            "signals": signals, "entry_price": entry_price,
            "p_fused": d.p_fused, "direction": d.direction,
            "score": d.score, "trade": fd.trade, "size": fd.size_frac,
            "vetoes": fd.vetoes, "reasons": fd.reasons,
            "weights_ver": ver, "sources": d.used_sources,
        }
        _append_jsonl(PRED_FILE, row)
        results.append(row)
        if verbose:
            src = ",".join(d.used_sources) or "-"
            v_txt = f" VETO[{','.join(fd.vetoes)}]" if fd.vetoes else ""
            print(f"  {symbol:10s} P={d.p_fused if d.p_fused is not None else float('nan'):.3f} "
                  f"S={d.sat:.2f} score={d.score:.3f} {d.direction:5s} "
                  f"trade={fd.trade} sumber=[{src}]{v_txt}")
    return results


def _exit_price_from_klines(klines: list[dict[str, float]], target_ms: float
                            ) -> Optional[float]:
    for k in klines:
        if k["date"] <= target_ms < k["date"] + 3600_000:
            return k["close"]
    return None


def label_pending() -> int:
    preds = _load_jsonl(PRED_FILE)
    labeled_ids = {o.get("pred_id") for o in _load_jsonl(OUT_FILE)}
    horizon_ms = HORIZON_H * 3600_000
    now_ms = time.time() * 1000.0
    n = 0
    for p in preds:
        if p["id"] in labeled_ids or p["ts"] * 1000.0 + horizon_ms > now_ms:
            continue
        try:
            need = int(HORIZON_H) + 48
            kl = _fetch_klines_sync(p["symbol"], "1h", limit=need)
            exit_p = _exit_price_from_klines(kl, p["ts"] * 1000.0 + horizon_ms)
        except Exception:
            continue
        if exit_p is None or not p.get("entry_price"):
            continue
        ret = exit_p / p["entry_price"] - 1.0
        y = 1 if ret > 0 else 0
        _append_jsonl(OUT_FILE, {"pred_id": p["id"], "ts": time.time(),
                                 "symbol": p["symbol"], "y": y,
                                 "ret": round(ret, 6), "horizon_h": HORIZON_H})
        n += 1
    return n


def build_training_rows() -> list[tuple[dict[str, Optional[float]], int]]:
    outcomes = {o["pred_id"]: o["y"] for o in _load_jsonl(OUT_FILE)}
    rows: list[tuple[dict[str, Optional[float]], int]] = []
    for p in _load_jsonl(PRED_FILE):
        y = outcomes.get(p["id"])
        if y is None:
            continue
        sig = {name: p.get("signals", {}).get(name) for name in SIGNAL_NAMES}
        rows.append((sig, int(y)))
    return rows


def learn(verbose: bool = True) -> dict[str, Any]:
    rows = build_training_rows()
    if len(rows) < LEARN_MIN_LABELED:
        if verbose:
            print(f"  belajar: {len(rows)}/{LEARN_MIN_LABELED} sampel berlabel — belum cukup")
        return {"learned": False, "reason": "sampel kurang", "n": len(rows)}
    res = run_weight_lab(rows)
    if res.used_optimized:
        ver = save_weights(res.weights, res.metrics)
        if verbose:
            print(f"  BOBOT BARU v{ver} dipasang! gates={res.gate} metrics={res.metrics}")
        return {"learned": True, "version": ver, "metrics": res.metrics}
    if verbose:
        print(f"  gate gagal -> bobot lama tetap: {res.reasons}")
    return {"learned": False, "reasons": res.reasons}


if __name__ == "__main__":
    import sys
    import tempfile

    if len(sys.argv) > 1 and sys.argv[1] != "selftest":
        cmd = sys.argv[1]
        if cmd == "scan":
            scan_once()
        elif cmd == "label":
            print(f"dilabeli: {label_pending()}")
        elif cmd == "learn":
            learn()
        else:
            print("perintah: scan | label | learn | selftest")
        sys.exit(0)

    tmp = tempfile.mkdtemp()
    PRED_FILE_T = os.path.join(tmp, "p.jsonl")
    OUT_FILE_T = os.path.join(tmp, "o.jsonl")
    WEIGHTS_FILE_T = os.path.join(tmp, "w.json")

    _append_jsonl(PRED_FILE_T, {"id": "a", "ts": 1.0, "symbol": "BTCUSDT",
                                "signals": {"fp": 0.7, "trend": None}, "entry_price": 100.0})
    with open(PRED_FILE_T, "a", encoding="utf-8") as f:
        f.write("KORUP\n")
    assert len(_load_jsonl(PRED_FILE_T)) == 1

    kl = [{"date": 0.0, "close": 10.0}, {"date": 3600_000.0, "close": 11.0}]
    assert _exit_price_from_klines(kl, 1800_000.0) == 10.0
    assert _exit_price_from_klines(kl, 3600_000.0) == 11.0
    assert _exit_price_from_klines(kl, 7200_000.0) is None

    old_wf = WEIGHTS_FILE
    WEIGHTS_FILE = WEIGHTS_FILE_T
    v1 = save_weights(neutral_weights(), {})
    w, v = load_active_weights()
    assert v == 1 and validate_weights(w) is not None
    with open(WEIGHTS_FILE_T, "w", encoding="utf-8") as f:
        f.write("{{{{")
    w2, v2 = load_active_weights()
    assert v2 == 0 and w2 == neutral_weights()
    WEIGHTS_FILE = old_wf

    d = decide({"fp": None, "trend": 0.8, "micro": 0.75, "mem": None, "log": None})
    assert d.direction == "LONG" and set(d.used_sources) == {"trend", "micro"}

    _append_jsonl(PRED_FILE_T, {"id": "b", "ts": 2.0, "symbol": "ETHUSDT",
                                "signals": {"fp": 0.2}, "entry_price": 5.0})
    _append_jsonl(OUT_FILE_T, {"pred_id": "b", "y": 0})
    old_pf, old_of = PRED_FILE, OUT_FILE
    PRED_FILE, OUT_FILE = PRED_FILE_T, OUT_FILE_T
    rows = build_training_rows()
    assert len(rows) == 1 and rows[0][1] == 0 and rows[0][0]["fp"] == 0.2
    PRED_FILE, OUT_FILE = old_pf, old_of

    from types import SimpleNamespace
    d_fake = SimpleNamespace(p_fused=0.8, sat=0.5, score=0.6, direction="LONG",
                             trade=True, size_frac=0.5, vetoes=[],
                             used_sources=["trend"], reasons=[])
    sig_q = {"fp": 0.9, "trend": 0.9, "micro": 0.9, "mem": None, "log": None}
    if HAVE_VETO_MODULES:
        fail_rows = [{"signals": sig_q, "y": 0, "ts": time.time()} for _ in range(20)]
        fd = apply_final_vetoes("TEST", sig_q, d_fake, mem_rows=fail_rows, log_diag=None)
        assert fd.trade is False and fd.size_frac == 0.0 and "mem" in fd.vetoes
        win_rows = [{"signals": sig_q, "y": 1, "ts": time.time()} for _ in range(20)]
        fd2 = apply_final_vetoes("TEST", sig_q, d_fake, mem_rows=win_rows, log_diag=None)
        assert fd2.trade is True and "mem" not in fd2.vetoes
        fd3 = apply_final_vetoes("TEST", sig_q, d_fake, mem_rows=[],
                                 log_diag={"cost_frac": 0.02, "edge_ratio": 10.0})
        assert "log" in fd3.vetoes and fd3.trade is False
        fd4 = apply_final_vetoes("TEST", sig_q, d_fake, mem_rows=[], log_diag=None)
        assert fd4.vetoes == [] and fd4.trade is True
        d_no = SimpleNamespace(trade=False, size_frac=0.0, vetoes=[], reasons=[])
        fd5 = apply_final_vetoes("TEST", sig_q, d_no, mem_rows=fail_rows,
                                 log_diag={"cost_frac": 0.02, "edge_ratio": 10.0})
        assert fd5.vetoes == []
    _log_diag_cache["CACHETEST"] = (time.time(), {"cost_frac": 0.001, "edge_ratio": 9.0})
    assert _log_diag_cached("CACHETEST")["edge_ratio"] == 9.0

    print("SELF-TEST OK — neuron_live v2 (sistem saraf hidup)")