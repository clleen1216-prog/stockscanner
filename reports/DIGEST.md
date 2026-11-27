# Daily digest

Paper trading only. No real money. Research, not investment advice.

Last run finished: 2026-11-27T19:15:33Z (UTC)

## Market state
- TAIEX 39152 vs 60-day average 45253: **below (weak)**
- S&P 500 overnight: +1.60%
- Macro position multiplier: x0.75 (only ever shrinks size)

## Pipeline health
- Price data: 1974 of 1987 stocks usable
- Latest price bar: 2026-11-26; 7.3% of stocks closed exactly at their open
- Fed liquidity feed: **NOT WORKING** (FredError: WALCL failed after 4 tries (csv ConnectionError: HTTPSConnectionPool(host='fred.stlouisfed.org', port=443): Max retries exceeded with url: /graph/fredgraph.csv?id=WALCL (Caused by ReadTimeoutError("HTTPSConnec))

## Paper strategies
A strategy needs 100 closed trades before any verdict. The decision rules are in PLAN.md; the monthly check writes paper/STATUS.md.

| Strategy | Signals | Open | Closed | Progress |
|---|---|---|---|---|
| V6 | 17 | 1 | 16 | 16/100 |
| V8 | 97 | 11 | 82 | 82/100 |
| V10 | 116 | 9 | 107 | 107/100 |
| V11 | 80 | 10 | 63 | 63/100 |

## Gate
- State: **COLLECTING** as of 2026-11-01 (gate G1 not open yet)
- Capped sleeve: 2 closed trades, 1 signal dates

## New signals today (9), simulated entry at next open
- V8: 2516 新建, 6614 資拓宏宇, 3285 微端科技股份有限公司
- V10: 2254 巨鎧精密-創, 2355 敬鵬, 3285 微端科技股份有限公司
- V11: 2516 新建, 6614 資拓宏宇, 3609 三一東林科技股份有限公司
- Picked by more than one strategy (not independent evidence): 2516, 3285, 6614

Full detail: paper/PAPER_REPORT.md
