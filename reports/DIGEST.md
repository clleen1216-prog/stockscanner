# Daily digest

Paper trading only. No real money. Research, not investment advice.

Last run finished: 2026-11-18T10:37:36Z (UTC)

## Market state
- TAIEX 40195 vs 60-day average 45973: **below (weak)**
- S&P 500 overnight: -1.03%
- Macro position multiplier: x0.75 (only ever shrinks size)

## Pipeline health
- Price data: 1972 of 1985 stocks usable
- Latest price bar: 2026-11-18; 7.8% of stocks closed exactly at their open
- Fed liquidity feed: **NOT WORKING** (FredError: WALCL failed after 4 tries (csv ConnectionError: HTTPSConnectionPool(host='fred.stlouisfed.org', port=443): Max retries exceeded with url: /graph/fredgraph.csv?id=WALCL (Caused by ReadTimeoutError("HTTPSConnec))

## Paper strategies
A strategy needs 100 closed trades before any verdict. The decision rules are in PLAN.md; the monthly check writes paper/STATUS.md.

| Strategy | Signals | Open | Closed | Progress |
|---|---|---|---|---|
| V6 | 17 | 2 | 15 | 15/100 |
| V8 | 90 | 28 | 58 | 58/100 |
| V10 | 110 | 22 | 88 | 88/100 |
| V11 | 71 | 21 | 43 | 43/100 |

## Gate
- State: **COLLECTING** as of 2026-11-01 (gate G1 not open yet)
- Capped sleeve: 2 closed trades, 1 signal dates

## New signals today (4), simulated entry at next open
- V8: 4977 眾達-KY
- V10: 2355 敬鵬, 4977 眾達-KY
- V11: 4977 眾達-KY
- Picked by more than one strategy (not independent evidence): 4977

Full detail: paper/PAPER_REPORT.md
