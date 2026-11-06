# Daily digest

Paper trading only. No real money. Research, not investment advice.

Last run finished: 2026-11-06T10:38:02Z (UTC)

## Market state
- TAIEX 39702 vs 60-day average 46415: **below (weak)**
- S&P 500 overnight: -4.36%
- Macro position multiplier: x0.75 (only ever shrinks size)

## Pipeline health
- Price data: 1970 of 1984 stocks usable
- Latest price bar: 2026-11-06; 5.8% of stocks closed exactly at their open
- Fed liquidity feed: **NOT WORKING** (FredError: WALCL failed after 4 tries (csv ConnectionError: HTTPSConnectionPool(host='fred.stlouisfed.org', port=443): Max retries exceeded with url: /graph/fredgraph.csv?id=WALCL (Caused by ReadTimeoutError("HTTPSConnec))

## Paper strategies
A strategy needs 100 closed trades before any verdict. The decision rules are in PLAN.md; the monthly check writes paper/STATUS.md.

| Strategy | Signals | Open | Closed | Progress |
|---|---|---|---|---|
| V6 | 14 | 0 | 14 | 14/100 |
| V8 | 53 | 18 | 35 | 35/100 |
| V10 | 75 | 12 | 63 | 63/100 |
| V11 | 40 | 13 | 26 | 26/100 |

## Gate
- State: **COLLECTING** as of 2026-11-01 (gate G1 not open yet)
- Capped sleeve: 2 closed trades, 1 signal dates

## New signals today (7), simulated entry at next open
- V8: 4155 訊映, 6112 邁達特, 6782 視陽
- V10: 6136 富爾特, 6467 泰合
- V11: 6782 視陽, 3287 廣寰科技股份有限公司
- Picked by more than one strategy (not independent evidence): 6782

Full detail: paper/PAPER_REPORT.md
