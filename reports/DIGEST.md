# Daily digest

Paper trading only. No real money. Research, not investment advice.

Last run finished: 2026-11-23T21:44:38Z (UTC)

## Market state
- TAIEX 36033 vs 60-day average 45711: **below (weak)**
- S&P 500 overnight: +4.73%
- Macro position multiplier: x0.75 (only ever shrinks size)

## Pipeline health
- Price data: 1973 of 1986 stocks usable
- Latest price bar: 2026-11-23; 6.1% of stocks closed exactly at their open
- Fed liquidity feed: **NOT WORKING** (FredError: WALCL failed after 4 tries (csv ConnectionError: HTTPSConnectionPool(host='fred.stlouisfed.org', port=443): Max retries exceeded with url: /graph/fredgraph.csv?id=WALCL (Caused by ReadTimeoutError("HTTPSConnec))

## Paper strategies
A strategy needs 100 closed trades before any verdict. The decision rules are in PLAN.md; the monthly check writes paper/STATUS.md.

| Strategy | Signals | Open | Closed | Progress |
|---|---|---|---|---|
| V6 | 17 | 1 | 16 | 16/100 |
| V8 | 92 | 10 | 78 | 78/100 |
| V10 | 112 | 6 | 106 | 106/100 |
| V11 | 74 | 7 | 60 | 60/100 |

## Gate
- State: **COLLECTING** as of 2026-11-01 (gate G1 not open yet)
- Capped sleeve: 2 closed trades, 1 signal dates

## New signals today (3), simulated entry at next open
- V8: 2597 潤弘
- V10: 6614 資拓宏宇
- V11: 6199 天品聯合企業股份有限公司

Full detail: paper/PAPER_REPORT.md
