"""
Meridian v2 — Neuron Dashboard (audited & improved).
=====================================================
Self-test offline-safe: python3 backend/neuron_dashboard.py
"""

from __future__ import annotations

import os
import sys
import time
from typing import Any, Optional

try:
    from .neuron_live import (OUT_FILE, PRED_FILE, WATCHLIST, _load_jsonl,
                              collect_signals, decide_with_vetoes, label_pending,
                              load_active_weights, scan_once)
except ImportError:
    from neuron_live import (OUT_FILE, PRED_FILE, WATCHLIST, _load_jsonl,
                             collect_signals, decide_with_vetoes, label_pending,
                             load_active_weights, scan_once)

DASH_INTERVAL_S = float(os.environ.get("MERIDIAN_DASH_INTERVAL_S", "1.0"))
SCAN_EVERY = int(os.environ.get("MERIDIAN_DASH_SCAN_EVERY", "30"))
BAR_W = 10
SPARK = "▁▂▃▄▅▆▇█"
PULSE = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
FLOW = ["●──►", "─●─►", "──●►", "───►"]
LEFT_COL = ("fp", "trend", "micro")
RIGHT_COL = ("mem", "log")


def _c(code: str, s: str) -> str:
    return f"\033[{code}m{s}\033[0m"


def bar(p: Optional[float], width: int = BAR_W) -> str:
    if p is None:
        return "░" * width
    p = max(0.0, min(1.0, float(p)))
    cells = p * width
    full = int(cells)
    frac = cells - full
    out = "█" * full
    if full < width and frac >= 0.125:
        out += "▏▎▍▌▋▊▉"[min(6, int(frac * 8) - 1)]
    return out + "░" * (width - len(out))


def sparkline(vals: list[Optional[float]], width: int = 24) -> str:
    v = [float(x) for x in vals if x is not None][-width:]
    if not v:
        return "·"
    if len(v) == 1:
        return "▄"
    lo, hi = min(v), max(v)
    if hi - lo < 1e-12:
        return "▄" * len(v)
    return "".join(SPARK[min(7, int((x - lo) / (hi - lo) * 7.999))] for x in v)


def glyph(v: Optional[float]) -> tuple[str, str, str]:
    if v is None:
        return "○", "TIDUR", "90"
    return "●", "HIDUP", "32"


def _node(name: str, val: Optional[float], conn: str = "├─",
          show_status: bool = False) -> str:
    g, st, cl = glyph(val)
    v_str = f"{val:.2f}" if val is not None else " --"
    line = f"{conn}{_c(cl, g)} {name:<6}{_c(cl, v_str.rjust(4))} {_c('90' if val is None else cl, bar(val))}"
    if show_status:
        line += f" {_c(cl, st)}"
    return line


def collect_state() -> dict[str, Any]:
    preds = _load_jsonl(PRED_FILE)
    outs = _load_jsonl(OUT_FILE)
    weights, ver = load_active_weights()
    syms: list[dict[str, Any]] = []
    for s in WATCHLIST:
        try:
            sig = collect_signals(s)
            fd = decide_with_vetoes(s, sig, weights)
            syms.append({"symbol": s, "signals": sig,
                         "p_fused": fd.d.p_fused, "sat": fd.d.sat,
                         "score": fd.d.score, "direction": fd.d.direction,
                         "trade": bool(fd.trade), "size": fd.size_frac,
                         "vetoes": list(fd.vetoes),
                         "sources": list(fd.d.used_sources)})
        except Exception as exc:
            syms.append({"symbol": s, "error": str(exc)})
    hist = [p.get("p_fused") for p in preds[-40:]]
    return {"symbols": syms, "n_pred": len(preds), "n_out": len(outs),
            "w_ver": ver, "hist": hist, "ts": time.time()}


def render(st: dict[str, Any], frame: int = 0) -> str:
    pulse = PULSE[frame % len(PULSE)]
    flow = FLOW[frame % len(FLOW)]
    L: list[str] = []

    L.append("╭" + "─" * 56 + "╮")
    L.append(f"  {_c('1;36', '⚡ MERIDIAN V2 — SISTEM SARAF HIDUP')}   "
             f"{_c('1;35', pulse)} detak {frame}")
    L.append("╰" + "─" * 56 + "╯")
    L.append(f"  {_c('90', 'SENSOR market_data')} {flow}")

    alive: set[str] = set()
    for s in st.get("symbols") or []:
        sym = s.get("symbol", "?")
        L.append(_c("90", "  " + "─" * 52))
        if "error" in s:
            L.append(f"  {sym}  {_c('31', '✖ sensor gagal')}: {s['error']}")
            continue
        L.append(f"  {_c('1;37', sym)}")
        sig = s.get("signals") or {}
        alive |= set(s.get("sources") or [])
        left = [(n, sig.get(n)) for n in LEFT_COL]
        right = [(n, sig.get(n)) for n in RIGHT_COL]
        for i in range(3):
            conn = "├─" if i < 2 else "└─"
            ln = _node(left[i][0], left[i][1], conn)
            rn = _node(right[i][0], right[i][1], "  ", show_status=True) if i < 2 else ""
            L.append(f"  {ln}    {rn}")
        p = s.get("p_fused")
        p_str = f"{p:.2f}" if p is not None else " --"
        sc = float(s.get("score") or 0.0)
        dirn = s.get("direction", "HOLD")
        vetoes = s.get("vetoes") or []
        v_txt = ",".join(vetoes) if vetoes else "✓"
        v_col = "31" if vetoes else "32"
        d_col = "32" if dirn == "LONG" else ("31" if dirn == "SHORT" else "90")
        trade = bool(s.get("trade"))
        t_txt, t_col = (("◆ TRADE", "1;32") if trade else ("trade=NO", "90"))
        L.append(f"  ╰{_c('90', flow)} FUSION P={_c('36', p_str)} "
                 f"S={s.get('sat', 0.0):.2f} ─► VETO {_c(v_col, v_txt)} ─► "
                 f"{_c(d_col, dirn)} score={sc:+.2f} {_c(t_col, t_txt)}")

    if not st.get("symbols"):
        L.append(f"  {_c('33', 'menunggu data…')}")

    n_pred = st.get("n_pred", 0)
    n_out = st.get("n_out", 0)
    ver = st.get("w_ver", 0)
    L.append(_c("90", "  " + "─" * 52))
    L.append(f"  ♥ jurnal {_c('1;36', str(n_pred))} pred │ "
             f"{_c('1;36', str(n_out))} label │ bobot {_c('1;33', f'v{ver}')} │ "
             f"saraf aktif {_c('1;32' if alive else '33', f'{len(alive)}/5')}")
    L.append(f"  riwayat P: {_c('36', sparkline(st.get('hist') or []))}")
    clock = time.strftime("%H:%M:%S", time.localtime(st.get("ts") or time.time()))
    err = st.get("last_err")
    L.append(f"  {clock}" + (f"  {_c('31', '⚠ ' + err)}" if err
                             else f"  {_c('32', 'sensor OK')}"))
    return "\n".join(L) + "\n"


def dashboard_loop() -> None:
    if os.name == "nt":
        os.system("")
    sys.stdout.write("\033[2J\033[H\033[?25l")
    sys.stdout.flush()
    frame = 0
    last_err: Optional[str] = None
    st: Optional[dict[str, Any]] = None
    try:
        while True:
            if frame % SCAN_EVERY == 0:
                try:
                    scan_once(verbose=False)
                    label_pending()
                    last_err = None
                except Exception as exc:
                    last_err = str(exc)
                try:
                    st = collect_state()
                except Exception as exc:
                    last_err = str(exc)
            if st is None:
                st = {"symbols": [], "n_pred": 0, "n_out": 0,
                      "w_ver": 0, "hist": [], "ts": time.time()}
            st["last_err"] = last_err
            st["ts"] = time.time()
            sys.stdout.write("\033[H\033[0J" + render(st, frame))
            sys.stdout.flush()
            time.sleep(DASH_INTERVAL_S)
            frame += 1
    except KeyboardInterrupt:
        pass
    finally:
        sys.stdout.write("\033[?25h\033[0J")
        sys.stdout.flush()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "live":
        dashboard_loop()
        sys.exit(0)

    assert bar(None) == "░" * BAR_W
    assert bar(0.5) == "█████░░░░░"
    assert bar(0.0) == "░" * BAR_W and bar(1.0) == "█" * BAR_W
    for v in (0.1, 0.37, 0.55, 0.83, 0.99):
        assert len(bar(v)) == BAR_W

    assert sparkline([]) == "·"
    assert sparkline([0.5, 0.5, 0.5]) == "▄▄▄"
    assert "█" in sparkline([0.0, 0.5, 1.0])
    assert set(sparkline([None, 0.2, None, 0.8])) <= set(SPARK)

    assert glyph(None) == ("○", "TIDUR", "90")
    assert glyph(0.5)[0] == "●" and glyph(0.5)[1] == "HIDUP"

    st = {"symbols": [{"symbol": "BTCUSDT",
                       "signals": {"fp": 0.6, "trend": 0.8, "micro": 0.5,
                                   "mem": None, "log": 0.55},
                       "p_fused": 0.64, "sat": 0.28, "score": 0.36,
                       "direction": "LONG", "trade": False, "size": 0.0,
                       "vetoes": [], "sources": ["fp", "trend", "micro", "log"]}],
          "n_pred": 42, "n_out": 18, "w_ver": 3,
          "hist": [0.5, 0.6, 0.64], "ts": 0.0}
    f = render(st, 7)
    for need in ("FUSION", "VETO", "TIDUR", "HIDUP", "LONG", "detak",
                 "42", "v3", "BTCUSDT", "riwayat"):
        assert need in f, need
    assert "●" in f and "○" in f

    assert isinstance(render({}, 0), str)
    f_err = render({"symbols": [{"symbol": "X", "error": "boom"}],
                    "n_pred": 0, "n_out": 0, "w_ver": 0, "hist": [], "ts": 0.0}, 1)
    assert "sensor gagal" in f_err and "boom" in f_err

    print("SELF-TEST OK — neuron_dashboard v2")