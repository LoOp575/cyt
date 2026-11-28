# Pump Radar V2: Daily Base Volume Anomaly

## Purpose

Pump Radar V2 scans the Binance USD-M Futures USDT perpetual universe and detects unusual daily token-unit trading activity relative to each contract's own recent history. The first trigger is Base Volume anomaly. Price movement and Quote Volume are supporting context, not mandatory gates.

This is additive. The legacy Radar and Screener are not replaced.

## Data source and scan behavior

- Universe: Binance USD-M Futures, contractType=PERPETUAL, quoteAsset=USDT, status=TRADING.
- Daily candles: Binance Futures fapi/v1/klines, interval 1d.
- Only completed UTC daily candles are evaluated.
- Scanner API is paginated into batches to keep each serverless request bounded.
- The frontend scans all pages sequentially when Pump Radar V2 opens if no completed scan is cached for the latest closed UTC candle date. It also supports a manual full rescan.
- The browser caches the completed daily snapshot in localStorage. This is not durable server-side history and does not run as a background job while the page is closed.

## Primary detector: daily Base Volume RVOL

For the latest fully closed daily candle:

Base RVOL Daily = latest closed daily Base Volume / mean(Base Volume of the prior 7 closed daily candles)

The evaluated candle is excluded from its own baseline.

### Initial experimental categories

| Ratio | Category |
|---:|---|
| < 1.5x | Normal |
| 1.5x to < 2.0x | Increasing |
| 2.0x to < 3.0x | Anomaly |
| 3.0x to < 5.0x | Strong Anomaly |
| >= 5.0x | Extreme Anomaly |

These are initial research thresholds, not statistically validated trading signals. Thresholds should later be evaluated across historical symbols and liquidity buckets.

## Secondary context

- Base RVOL 7D: sum of the latest 7 closed daily Base Volumes / sum of the 7 closed daily Base Volumes immediately before that window.
- Quote RVOL Daily: latest closed daily Quote Volume / mean Quote Volume of the prior 7 closed daily candles.
- Quote RVOL 7D: latest 7D Quote Volume / previous 7D Quote Volume.
- Buy Share Quote: takerBuyQuote / quoteVolume. Aggressor-side flow is not proof of beneficial ownership or whale accumulation.
- Price changes 24H and 7D provide movement context. They do not suppress the primary Base Volume anomaly trigger.

## Minimum history and handling

- 15 closed daily candles are required for the two consecutive 7D windows plus daily baseline.
- In-progress UTC daily candle is excluded.
- Missing/failed candles for a pair are reported as skipped; synthetic candles are never used.
- Base Volume is token quantity; Quote Volume is notional turnover in quote asset units (USDT for these contracts).

## Limitations

- The scan is initiated by the frontend on page open after the latest daily close, or manually. It is not a server-side scheduled/background scan.
- Browser cache is per device/browser and can be cleared.
- The first implementation does not persist a server-side Track Record.
- A volume anomaly can be caused by news, liquidation, arbitrage, market-maker activity, or other flows. It is not a buy/entry signal.
- Funding rate, open interest, order book depth, spread, and 1H/15M entry confirmation are not part of this first scanner iteration.
