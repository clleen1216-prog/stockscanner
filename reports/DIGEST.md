# Daily digest

Paper trading only. No real money. Research, not investment advice.

Last run finished: 2026-11-12T10:37:05Z (UTC)

## Market state
- TAIEX 43092 vs 60-day average 46251: **below (weak)**
- S&P 500 overnight: +1.31%
- Macro position multiplier: x1.0 (only ever shrinks size)

## Pipeline health
- Price data: 1971 of 1984 stocks usable
- Latest price bar: 2026-11-12; 7.8% of stocks closed exactly at their open
- Fed liquidity feed: **NOT WORKING** (FredError: WALCL failed after 4 tries (csv ConnectionError: HTTPSConnectionPool(host='fred.stlouisfed.org', port=443): Max retries exceeded with url: /graph/fredgraph.csv?id=WALCL (Caused by ReadTimeoutError("HTTPSConnec))

## Paper strategies
A strategy needs 100 closed trades before any verdict. The decision rules are in PLAN.md; the monthly check writes paper/STATUS.md.

| Strategy | Signals | Open | Closed | Progress |
|---|---|---|---|---|
| V6 | 15 | 1 | 14 | 14/100 |
| V8 | 79 | 37 | 40 | 40/100 |
| V10 | 95 | 27 | 68 | 68/100 |
| V11 | 57 | 25 | 28 | 28/100 |

## Gate
- State: **COLLECTING** as of 2026-11-01 (gate G1 not open yet)
- Capped sleeve: 2 closed trades, 1 signal dates

## New signals today (14), simulated entry at next open
- V6: 3374 精材科技股份有限公司
- V8: 3701 大眾控, 3715 定穎投控, 6152 百一, 3379 彬台科技股份有限公司, 4105 台灣東洋藥品工業股份有限公司
- V10: 2471 資通, 4426 利勤, 4904 遠傳, 6152 百一, 3691 碩禾電子材料股份有限公司, 6617 共信醫藥科技控股股份有限公司
- V11: 3701 大眾控, 3379 彬台科技股份有限公司
- Picked by more than one strategy (not independent evidence): 3379, 3701, 6152

Full detail: paper/PAPER_REPORT.md
