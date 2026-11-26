# Daily digest

Paper trading only. No real money. Research, not investment advice.

Last run finished: 2026-11-26T19:21:10Z (UTC)

## Market state
- TAIEX 38195 vs 60-day average 45367: **below (weak)**
- S&P 500 overnight: -0.25%
- Macro position multiplier: x0.75 (only ever shrinks size)

## Pipeline health
- Price data: 1973 of 1987 stocks usable
- Latest price bar: 2026-11-25; 5.2% of stocks closed exactly at their open
- Fed liquidity feed: **NOT WORKING** (FredError: WALCL failed after 4 tries (csv ConnectionError: HTTPSConnectionPool(host='fred.stlouisfed.org', port=443): Max retries exceeded with url: /graph/fredgraph.csv?id=WALCL (Caused by ReadTimeoutError("HTTPSConnec))

## Paper strategies
A strategy needs 100 closed trades before any verdict. The decision rules are in PLAN.md; the monthly check writes paper/STATUS.md.

| Strategy | Signals | Open | Closed | Progress |
|---|---|---|---|---|
| V6 | 17 | 1 | 16 | 16/100 |
| V8 | 94 | 10 | 80 | 80/100 |
| V10 | 113 | 6 | 107 | 107/100 |
| V11 | 77 | 9 | 61 | 61/100 |

## Gate
- State: **COLLECTING** as of 2026-11-01 (gate G1 not open yet)
- Capped sleeve: 2 closed trades, 1 signal dates

## New signals today (6), simulated entry at next open
- V8: 7765 中華資安, 6590 普鴻資訊股份有限公司
- V10: 6590 普鴻資訊股份有限公司
- V11: 7765 中華資安, 3285 微端科技股份有限公司, 6590 普鴻資訊股份有限公司
- Picked by more than one strategy (not independent evidence): 6590, 7765

Full detail: paper/PAPER_REPORT.md
