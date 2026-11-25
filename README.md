# DinoTradeOS Spot Lab v0.2

This module extends the existing standalone DinoTradeOS Risk Lab with public Binance-compatible spot-market data, symbol-specific exchange filters, a 9/21 SMA research signal, paper-only orders and simplified historical signal replay.

## Install (GitHub Pages)

1. Download the ZIP and unzip it.
2. Upload **spot-lab.html** to the root of `dennismm4/tradeos-dashboard`, next to `index.html` and `risk-lab.html`. Do not overwrite `index.html`.
3. Open `https://dennismm4.github.io/tradeos-dashboard/spot-lab.html` once Pages deploys.
4. Select BTC/USDT or ETH/USDT and press **Load public candles & rules**.
5. If the fetch fails, the app explicitly marks public data unavailable; offline demo data is synthetic and disables paper execution because verified exchange rules are missing.

## Budget assumptions

- Default paper starting capital: KES 1,200.
- Default KES per USDT: 130 **manual illustrative assumption**, NOT a live exchange rate.
- Default one-side fee: 0.1%; default one-side slippage: 0.05% — user-adjustable **simulation assumptions**, not verified exchange charges.
- Maximum planned per-trade loss 1% (KES 12 initially), daily loss 2%, peak equity drawdown 5%.
- Uses current public exchangeInfo to check LOT_SIZE / MARKET_LOT_SIZE and MIN_NOTIONAL / NOTIONAL. Such filters can change.

## Limitations / safety

**No API keys. No wallet access. No signed requests. No order creation. No live trading.**

Historical closes are not an order book. A close-price model cannot guarantee fill or stop prices, and the simplistic replay neither uses an intrabar stop-loss nor faithfully models partial fills, gaps, bid/ask spread, exchange downtime, taxes, funding or latency. Never use replay results as proof of profitability. Simulation uses one pair at a time, and changing markets while a simulated position is open is disabled.

Data is stored in localStorage only. Clear browser data = loss of simulated journal. Export CSV regularly.

**Before considering live orders:** establish legal availability of the venue and markets in the user's location; verify account minimums and fees; build a private backend (never in public GitHub Pages) with authenticated API client, key restrictions, idempotency, reconciliation, independent risk limits, kill switch, durable event log, and testnet integration tests. User must explicitly authorize each live trading step.

## Source references

Official Binance market-data endpoint: https://github.com/binance/binance-spot-api-docs/blob/master/faqs/market_data_only.md

Official exchange filters: https://github.com/binance/binance-spot-api-docs/blob/master/filters.md
