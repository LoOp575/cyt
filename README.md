# Meridian cyt — filtered & simplified build

Screener kualitas koin crypto: demand-quality model + neuron adaptif online +
CryptoRank tokenomics. Repo ini adalah **build terkurasi** — dari 3 repo
(Test, meri) hanya modul yang lolos filter akurasi yang dibawa, commit
satu-per-satu sesuai layer.

## Hasil filter (kena / tidak)

| Layer | Yang dipilih | Alasan |
|---|---|---|
| Screener | `screening_v2.py` | v2 dengan 7 fix akurasi (multicollinearity d_pos dihapus, dead zone koin 61-89 hari dihapus, z-score standardisasi, dsb). v1 TIDAK dibawa. |
| Market data | `market_data.py` (Test) | Punya `fetch_symbol_klines` + deteksi `SymbolNotListed` + `search_binance_symbols` (versi meri tidak). |
| Fokker-Planck | `fokker_planck.py` (Test) | Superset: candles + orderbook + simulate + backtest. Versi meri hanya subset. |
| CryptoRank | `cryptorank.py` (v3) + `cryptorank_vesting.py` (v2) | Endpoint plan berbeda & saling melengkapi: v3 = market table/unlocks/funding-investor, v2 = search/detail/vesting. |
| Neuron | `neuron_core` + `neuron_memory` + `neuron_logistic` + `weight_lab` | Self-test lulus semua: RMSProp + surprise gate + regime switch + Wilson pattern trust + gerbang Brier/AUC/precision. |
| Server | `server.py` lean (15 routes) | 38 route disederhanakan: layer eksperimental (fp-v2 compare, fp-live, calibrate v1) dibuang. |
| Unlock gate | `gates.py` | Dipisah dari screener supaya modul v2 tetap byte-identik dengan sumbernya. |

## Cara jalan (lokal)

```bash
pip install -r requirements.txt
uvicorn backend.server:app --port 8000
# probe:
#   curl localhost:8000/api/health
#   curl "localhost:8000/api/screen-v2/BTCUSDT"
#   curl -X POST localhost:8000/api/neuron/predict -H 'Content-Type: application/json' -d '{"symbol":"BTCUSDT"}'
```

## Deploy Vercel

1. Import repo ini di Vercel (region `sin1` sudah diset di `vercel.json`
   — Binance geo-block US, jadi JANGAN pindah ke region US).
2. Environment variables:
   - `PYTHON_VERSION` = `3.12.x` (wajib)
   - `CRYPTORANK_API_KEY` = key dari https://cryptorank.io/public-api/dashboard
   - `SCREEN_SOURCE` = `auto` (opsional)
3. Deploy. Verifikasi: `/api/health` -> `cryptorank.configured: true`.

## Arsitektur stateless (penting)

Neuron & memory state **disimpan di client** (localStorage) dan dikirim balik
di body tiap request `/api/neuron/*`. Server Vercel ephemeral tidak menyimpan
state antar-request — flow: `predict` -> simpan state -> (nanti) `episode/close`
dengan realized return -> state baru -> `refit` (usulan) -> `validate`
(gerbang) -> baru bobot dipakai. Bobot ACCEPT pun tetap PROVISIONAL.

## Alur belajar neuron

```
predict (dendrite dari screen-v2 + fp + unlock)  ->  episode PENDING
episode/close (+4% misal)                        ->  episode CLOSED, RMSProp update
episode >= 30 CLOSED                             ->  refit = usulan bobot baru
episode >= 50 CLOSED                             ->  weight_lab: Brier/AUC/precision
LOLOS gerbang                                    ->  bobot baru boleh dipasang (tetap PROVISIONAL)
```

## Modul

```
backend/
├── market_data.py          Binance mirror→US→spot→MEXC→futures→CoinGecko→seed (label jujur)
├── screening_v2.py         Screener demand-quality v2 (7 fix) — satu-satunya screener
├── cryptorank.py           CR v3: market table, unlocks 30d, funding/investor (self-gating)
├── cryptorank_vesting.py   CR v2: search, detail, vesting/allocations (tanpa fallback palsu)
├── neuron_core.py          Neuron 10 dendrite, tanh, RMSProp, surprise gate
├── neuron_memory.py        Hippocampus episode + cortex pattern trust (Wilson LB)
├── neuron_logistic.py      Guru offline refit (split temporal 75/25)
├── weight_lab.py           Gerbang validasi bobot (Brier/AUC/precision + relatif)
├── fokker_planck.py        PDE solver (isolated, sumber dendrite fp)
├── gates.py                VERDICT_META + unlock gate (dipisah dari screener)
└── server.py               FastAPI lean, 15 routes, stateless
```

Setiap modul punya self-test bawaan: `python3 backend/<modul>.py`
