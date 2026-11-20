# Daily digest

Paper trading only. No real money. Research, not investment advice.

Last run finished: 2026-11-20T10:37:24Z (UTC)

## Market state
- TAIEX 36033 vs 60-day average 45711: **below (weak)**
- S&P 500 overnight: -2.02%
- Macro position multiplier: x0.75 (only ever shrinks size)

## Pipeline health
- Price data: 1972 of 1985 stocks usable
- Latest price bar: 2026-11-20; 6.5% of stocks closed exactly at their open
- Fed liquidity feed: **NOT WORKING** (FredError: WALCL failed after 4 tries (csv ConnectionError: HTTPSConnectionPool(host='fred.stlouisfed.org', port=443): Max retries exceeded with url: /graph/fredgraph.csv?id=WALCL (Caused by ReadTimeoutError("HTTPSConnec))

## Paper strategies
A strategy needs 100 closed trades before any verdict. The decision rules are in PLAN.md; the monthly check writes paper/STATUS.md.

| Strategy | Signals | Open | Closed | Progress |
|---|---|---|---|---|
| V6 | 17 | 1 | 16 | 16/100 |
| V8 | 91 | 10 | 77 | 77/100 |
| V10 | 111 | 6 | 105 | 105/100 |
| V11 | 73 | 8 | 58 | 58/100 |

## Gate
- State: **COLLECTING** as of 2026-11-01 (gate G1 not open yet)
- Capped sleeve: 2 closed trades, 1 signal dates

## New signals today (1), simulated entry at next open
- V10: 7765 中華資安

Full detail: paper/PAPER_REPORT.md
