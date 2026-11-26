# DinoTradeOS Spot Lab v0.3 (research and simulation only)

## Install (GitHub Pages)

Upload **spot-lab.html** and **engine.js** into the same directory in `dennismm4/tradeos-dashboard` (and optionally `risk-lab.html`). The public page will be at `https://dennismm4.github.io/tradeos-dashboard/spot-lab.html` after Pages deployment. Upload both files together: the UI depends on engine.js.

The existing index.html is untouched. No broker credentials, funded balances, exchange signed orders or live execution are part of this package.

## Recommended sequence

1. Load **public** BTC/USDT candles and verified symbol filters. The dashboard will fail closed if the public Binance data API is blocked by browser or region.
2. Run **seven automatic stress checks** and inspect their pass/fail results. These use synthetic fixtures and test code logic; they are NOT live exchange or strategy tests.
3. Run **70/30 historical replay**, checking rejected orders, simulated stops, entry locks, actual costs and out-of-sample performance separately.
4. Re-run with higher fees/slippage and different market intervals. Do not optimise on the out-of-sample split, or it stops being unseen data.
5. Only use manual paper entries with fresh public candles and verified pair filters. Never fund real trading based on these results.

## Reproducible local tests

With Node.js installed, run `node tests.js` (12 tests, no packages needed). Results reflect deterministic synthetic scenarios and calculation correctness, NOT forecast profitability. `tests.js` is not required for GitHub Pages.

## Important limitations

- KES/USDT is a manually entered assumption, not a live exchange quote.
- Risk is configured as an illustrative planned loss and may be exceeded by gaps or exchange execution conditions.
- OHLC backtests cannot determine real intrabar order path; the simulator models stops conservatively, but does not represent real fill quality.
- The simulator halts NEW entries once a daily-loss or drawdown threshold trips; it cannot guarantee flattening at the threshold or cap the size of a loss.
- Buy/sell in the page are simulated paper entries and exits, not real orders. Paper entries use completed candle closes rather than executable bid/ask. The manual paper positions do not automatically process stop-losses as time passes; only replay engine models intrabar stops.
- This is educational research software and is not brokerage, investment or legal advice.
