# Daily digest

Paper trading only. No real money. Research, not investment advice.

Last run finished: 2026-11-09T10:32:23Z (UTC)

## Market state
- TAIEX 41662 vs 60-day average 46361: **below (weak)**
- S&P 500 overnight: +0.31%
- Macro position multiplier: x0.75 (only ever shrinks size)

## Pipeline health
- Price data: 1970 of 1984 stocks usable
- Latest price bar: 2026-11-09; 6.9% of stocks closed exactly at their open
- Fed liquidity feed: **NOT WORKING** (FredError: WALCL failed after 4 tries (csv ConnectionError: HTTPSConnectionPool(host='fred.stlouisfed.org', port=443): Max retries exceeded with url: /graph/fredgraph.csv?id=WALCL (Caused by ReadTimeoutError("HTTPSConnec))

## Paper strategies
A strategy needs 100 closed trades before any verdict. The decision rules are in PLAN.md; the monthly check writes paper/STATUS.md.

| Strategy | Signals | Open | Closed | Progress |
|---|---|---|---|---|
| V6 | 14 | 0 | 14 | 14/100 |
| V8 | 57 | 21 | 36 | 36/100 |
| V10 | 79 | 16 | 63 | 63/100 |
| V11 | 42 | 14 | 26 | 26/100 |

## Gate
- State: **COLLECTING** as of 2026-11-01 (gate G1 not open yet)
- Capped sleeve: 2 closed trades, 1 signal dates

## New signals today (10), simulated entry at next open
- V8: 1789 神隆, 3703 欣陸, 3466 德晉科技股份有限公司, 3691 碩禾電子材料股份有限公司
- V10: 1789 神隆, 9933 中鼎, 3466 德晉科技股份有限公司, 6245 立端科技股份有限公司
- V11: 1742 台灣蠟品股份有限公司, 3691 碩禾電子材料股份有限公司
- Picked by more than one strategy (not independent evidence): 1789, 3466, 3691

Full detail: paper/PAPER_REPORT.md
