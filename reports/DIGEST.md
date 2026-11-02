# Daily digest

Paper trading only. No real money. Research, not investment advice.

Last run finished: 2026-11-02T10:35:56Z (UTC)

## Market state
- TAIEX 44920 vs 60-day average 46566: **below (weak)**
- S&P 500 overnight: -1.82%
- Macro position multiplier: x1.0 (only ever shrinks size)

## Pipeline health
- Price data: 1971 of 1985 stocks usable
- Latest price bar: 2026-11-02; 9.8% of stocks closed exactly at their open
- Fed liquidity feed: **NOT WORKING** (FredError: WALCL failed after 4 tries (csv ConnectionError: HTTPSConnectionPool(host='fred.stlouisfed.org', port=443): Max retries exceeded with url: /graph/fredgraph.csv?id=WALCL (Caused by ReadTimeoutError("HTTPSConnec))

## Paper strategies
A strategy needs 100 closed trades before any verdict. The decision rules are in PLAN.md; the monthly check writes paper/STATUS.md.

| Strategy | Signals | Open | Closed | Progress |
|---|---|---|---|---|
| V6 | 14 | 7 | 7 | 7/100 |
| V8 | 42 | 30 | 12 | 12/100 |
| V10 | 60 | 41 | 19 | 19/100 |
| V11 | 30 | 20 | 9 | 9/100 |

## Gate
- State: **COLLECTING** as of 2026-11-01 (gate G1 not open yet)
- Capped sleeve: 2 closed trades, 1 signal dates

## New signals today (20), simulated entry at next open
- V8: 1416 廣豐, 1528 恩德, 6112 邁達特, 4741 泓瀚科技股份有限公司, 6221 晉泰科技股份有限公司, 6234 高僑自動化科技股份有限公司, 6425 易發精機股份有限公司, 6609 台灣瀧澤科技股份有限公司
- V10: 2023 燁輝, 2609 陽明, 3518 柏騰, 6902 GOGOLOOK, 3268 海德威電子工業股份有限公司
- V11: 1416 廣豐, 4741 泓瀚科技股份有限公司, 6221 晉泰科技股份有限公司, 6234 高僑自動化科技股份有限公司, 6425 易發精機股份有限公司, 6609 台灣瀧澤科技股份有限公司, 8099 大同世界科技股份有限公司
- Picked by more than one strategy (not independent evidence): 1416, 4741, 6221, 6234, 6425, 6609

Full detail: paper/PAPER_REPORT.md
