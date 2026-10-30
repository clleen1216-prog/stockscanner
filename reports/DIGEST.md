# Daily digest

Paper trading only. No real money. Research, not investment advice.

Last run finished: 2026-10-30T10:27:28Z (UTC)

## Market state
- TAIEX 45212 vs 60-day average 46541: **below (weak)**
- S&P 500 overnight: -0.30%
- Macro position multiplier: x1.0 (only ever shrinks size)

## Pipeline health
- Price data: 1970 of 1984 stocks usable
- Latest price bar: 2026-10-30; 7.5% of stocks closed exactly at their open
- Fed liquidity feed: **NOT WORKING** (FredError: WALCL failed after 4 tries (csv ConnectionError: HTTPSConnectionPool(host='fred.stlouisfed.org', port=443): Max retries exceeded with url: /graph/fredgraph.csv?id=WALCL (Caused by ReadTimeoutError("HTTPSConnec))

## Paper strategies
A strategy needs 100 closed trades before any verdict. The decision rules are in PLAN.md; the monthly check writes paper/STATUS.md.

| Strategy | Signals | Open | Closed | Progress |
|---|---|---|---|---|
| V6 | 14 | 8 | 6 | 6/100 |
| V8 | 34 | 26 | 8 | 8/100 |
| V10 | 55 | 39 | 16 | 16/100 |
| V11 | 23 | 14 | 8 | 8/100 |

## New signals today (16), simulated entry at next open
- V6: 1216 統一, 2606 裕民, 2617 台航, 2834 臺企銀, 2897 王道銀行
- V8: 2412 中華電, 2516 新建, 2603 長榮, 5013 強新工業股份有限公司
- V10: 2355 敬鵬, 2520 冠德, 2897 王道銀行, 5269 祥碩, 6140 訊達電腦股份有限公司
- V11: 2603 長榮, 5013 強新工業股份有限公司
- Picked by more than one strategy (not independent evidence): 2603, 2897, 5013

Full detail: paper/PAPER_REPORT.md
