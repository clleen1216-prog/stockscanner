# Daily digest

Paper trading only. No real money. Research, not investment advice.

Last run finished: 2026-11-16T11:01:53Z (UTC)

## Market state
- TAIEX 41040 vs 60-day average 46135: **below (weak)**
- S&P 500 overnight: -0.40%
- Macro position multiplier: x0.75 (only ever shrinks size)

## Pipeline health
- Price data: 1971 of 1984 stocks usable
- Latest price bar: 2026-11-16; 5.2% of stocks closed exactly at their open
- Fed liquidity feed: **NOT WORKING** (FredError: WALCL failed after 4 tries (csv ConnectionError: HTTPSConnectionPool(host='fred.stlouisfed.org', port=443): Max retries exceeded with url: /graph/fredgraph.csv?id=WALCL (Caused by ReadTimeoutError("HTTPSConnec))

## Paper strategies
A strategy needs 100 closed trades before any verdict. The decision rules are in PLAN.md; the monthly check writes paper/STATUS.md.

| Strategy | Signals | Open | Closed | Progress |
|---|---|---|---|---|
| V6 | 16 | 2 | 14 | 14/100 |
| V8 | 88 | 41 | 43 | 43/100 |
| V10 | 107 | 34 | 73 | 73/100 |
| V11 | 69 | 32 | 30 | 30/100 |

## Gate
- State: **COLLECTING** as of 2026-11-01 (gate G1 not open yet)
- Capped sleeve: 2 closed trades, 1 signal dates

## New signals today (4), simulated entry at next open
- V10: 6240 松崗國際興業股份有限公司, 6690 安碁資訊股份有限公司, 7767 仁大資訊股份有限公司
- V11: 2471 資通

Full detail: paper/PAPER_REPORT.md
