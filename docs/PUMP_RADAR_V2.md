# Pump Radar V2: Detector Specification

## Scope and safety

This is an additive detector. It does not replace `backend/radar.py`, alter the Screener, or change existing API routes. The engine is pure computation and accepts closed daily candles. A later integration step must supply the existing candle schema and persist Track Record outcomes.

## Required candle fields

`date, open, high, low, close, volume, quoteVolume, takerBuyBase, takerBuyQuote`

- Base Volume is token quantity.
- Quote Volume is notional turnover (USDT for the Binance USDT market).
- Taker-buy share is aggressor-side flow, not proof of beneficial ownership or accumulation.
- The in-progress daily candle must be removed before scoring.

## Detector A: Dormant Volume Anomaly

Initial experimental conditions (all required):
- 90D drawdown <= -15%.
- Daily Base RVOL >= 3.0x.
- Daily Quote RVOL >= 3.0x.
- 7D Quote RVOL >= 1.5x.
- 7D price return between -5% and +5%.

## Detector B: Active Volume Expansion

Initial experimental conditions (all required):
- Daily Base RVOL >= 2.5x.
- Daily Quote RVOL >= 2.5x.
- 7D Quote RVOL >= 1.5x.
- 24H price return >= +3%.
- 7D price return > 0%.

## Formula definitions

- Daily RVOL = current closed-day volume / median of the prior 30 closed daily volumes.
- 7D RVOL = sum(last 7 closed daily volumes) / (7 x median of the prior 30 daily volumes).
- 90D drawdown = latest close / highest high over last 90 closed candles - 1.
- Buy share = takerBuyQuote / quoteVolume. Base equivalent is also exposed.
- Price Demand Efficiency = 7D price return (%) / 7D Quote Volume growth (%). It is descriptive only and is not used as a standalone trigger.
- Volume/price distortion = 7D Quote Volume growth minus 7D Base Volume growth. A large gap can reflect price/mix effects, not organic unit demand.

The baseline excludes the evaluated candle to avoid self-inflation. The engine requires 100 closed candles.

## Scores (0-100, heuristic and uncalibrated)

Dormant weights: Base RVOL 25%, Quote RVOL 25%, 7D Quote RVOL 15%, taker-buy share 15%, 90D drawdown 10%, price containment 10%.

Active weights: Base RVOL 20%, Quote RVOL 25%, 7D Quote RVOL 15%, taker-buy share 15%, price momentum 25%.

Scores are ranking aids, not probabilities. Trigger eligibility and score are separate outputs. Do not describe a high score as a guaranteed pump or whale signal.

## Historical evaluation

For each historical signal, calculate close-to-close returns after 24H, 72H, and 7D. Run a walk-forward backtest over at least 120 days, preferably longer, and report:
- number of signals per category;
- median and mean forward returns;
- percentage of positive outcomes;
- maximum adverse excursion if OHLC data is available;
- false-positive rate and signal overlap;
- performance by liquidity bucket.

Do not tune parameters on the same dates used for final evaluation. Use a chronological train/validation/test split.

## Planned integration (not included in this initial module)

1. Add a new route without changing existing routes.
2. Reuse the existing Binance candle/data layer; do not create a second market-data stack.
3. Add frontend category tabs and metric detail rows.
4. Persist signal snapshots and outcomes using the project's existing storage only after its schema is inspected.
5. Compare V2 with legacy Radar before making V2 the default.
