# Daily digest

Paper trading only. No real money. Research, not investment advice.

Last run finished: 2026-11-10T10:33:49Z (UTC)

## Market state
- TAIEX 42712 vs 60-day average 46321: **below (weak)**
- S&P 500 overnight: +2.35%
- Macro position multiplier: x1.0 (only ever shrinks size)

## Pipeline health
- Price data: 1971 of 1984 stocks usable
- Latest price bar: 2026-11-10; 7.8% of stocks closed exactly at their open
- Fed liquidity feed: **NOT WORKING** (FredError: WALCL failed after 4 tries (csv ConnectionError: HTTPSConnectionPool(host='fred.stlouisfed.org', port=443): Max retries exceeded with url: /graph/fredgraph.csv?id=WALCL (Caused by ReadTimeoutError("HTTPSConnec))

## Paper strategies
A strategy needs 100 closed trades before any verdict. The decision rules are in PLAN.md; the monthly check writes paper/STATUS.md.

| Strategy | Signals | Open | Closed | Progress |
|---|---|---|---|---|
| V6 | 14 | 0 | 14 | 14/100 |
| V8 | 61 | 25 | 36 | 36/100 |
| V10 | 83 | 19 | 64 | 64/100 |
| V11 | 45 | 17 | 26 | 26/100 |

## Gate
- State: **COLLECTING** as of 2026-11-01 (gate G1 not open yet)
- Capped sleeve: 2 closed trades, 1 signal dates

## New signals today (11), simulated entry at next open
- V8: 2618 長榮航, 4426 利勤, 3147 大綜電腦系統股份有限公司, 5230 雷笛克光學股份有限公司
- V10: 3029 零壹, 3049 精金, 3105 穩懋半導體股份有限公司, 6150 撼訊科技股份有限公司
- V11: 6112 邁達特, 3147 大綜電腦系統股份有限公司, 5230 雷笛克光學股份有限公司
- Picked by more than one strategy (not independent evidence): 3147, 5230

Full detail: paper/PAPER_REPORT.md
