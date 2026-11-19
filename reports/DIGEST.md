# Daily digest

Paper trading only. No real money. Research, not investment advice.

Last run finished: 2026-11-19T10:37:41Z (UTC)

## Market state
- TAIEX 38427 vs 60-day average 45864: **below (weak)**
- S&P 500 overnight: -0.23%
- Macro position multiplier: x0.75 (only ever shrinks size)

## Pipeline health
- Price data: 1972 of 1985 stocks usable
- Latest price bar: 2026-11-19; 3.5% of stocks closed exactly at their open
- Fed liquidity feed: **NOT WORKING** (FredError: WALCL failed after 4 tries (csv ConnectionError: HTTPSConnectionPool(host='fred.stlouisfed.org', port=443): Max retries exceeded with url: /graph/fredgraph.csv?id=WALCL (Caused by ReadTimeoutError("HTTPSConnec))

## Paper strategies
A strategy needs 100 closed trades before any verdict. The decision rules are in PLAN.md; the monthly check writes paper/STATUS.md.

| Strategy | Signals | Open | Closed | Progress |
|---|---|---|---|---|
| V6 | 17 | 2 | 15 | 15/100 |
| V8 | 91 | 17 | 70 | 70/100 |
| V10 | 110 | 10 | 100 | 100/100 |
| V11 | 73 | 13 | 53 | 53/100 |

## Gate
- State: **COLLECTING** as of 2026-11-01 (gate G1 not open yet)
- Capped sleeve: 2 closed trades, 1 signal dates

## New signals today (3), simulated entry at next open
- V8: 6782 視陽
- V11: 2412 中華電, 6782 視陽
- Picked by more than one strategy (not independent evidence): 6782

Full detail: paper/PAPER_REPORT.md
