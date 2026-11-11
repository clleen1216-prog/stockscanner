# Daily digest

Paper trading only. No real money. Research, not investment advice.

Last run finished: 2026-11-11T10:36:47Z (UTC)

## Market state
- TAIEX 44257 vs 60-day average 46300: **below (weak)**
- S&P 500 overnight: -0.38%
- Macro position multiplier: x1.0 (only ever shrinks size)

## Pipeline health
- Price data: 1971 of 1984 stocks usable
- Latest price bar: 2026-11-11; 8.1% of stocks closed exactly at their open
- Fed liquidity feed: **NOT WORKING** (FredError: WALCL failed after 4 tries (csv ConnectionError: HTTPSConnectionPool(host='fred.stlouisfed.org', port=443): Max retries exceeded with url: /graph/fredgraph.csv?id=WALCL (Caused by ReadTimeoutError("HTTPSConnec))

## Paper strategies
A strategy needs 100 closed trades before any verdict. The decision rules are in PLAN.md; the monthly check writes paper/STATUS.md.

| Strategy | Signals | Open | Closed | Progress |
|---|---|---|---|---|
| V6 | 14 | 0 | 14 | 14/100 |
| V8 | 74 | 36 | 37 | 37/100 |
| V10 | 89 | 23 | 66 | 66/100 |
| V11 | 55 | 26 | 26 | 26/100 |

## Gate
- State: **COLLECTING** as of 2026-11-01 (gate G1 not open yet)
- Capped sleeve: 2 closed trades, 1 signal dates

## New signals today (29), simulated entry at next open
- V8: 1528 恩德, 2034 允強, 2355 敬鵬, 2453 凌群, 2466 冠西電, 2471 資通, 3029 零壹, 4174 台灣浩鼎生技股份有限公司, 4577 達航科技股份有限公司, 6150 撼訊科技股份有限公司, 6221 晉泰科技股份有限公司, 6234 高僑自動化科技股份有限公司, 6697 東捷資訊服務股份有限公司
- V10: 3617 碩天, 4927 泰鼎-KY, 5521 工信, 6112 邁達特, 9904 寶成, 3147 大綜電腦系統股份有限公司
- V11: 1528 恩德, 2355 敬鵬, 3029 零壹, 4174 台灣浩鼎生技股份有限公司, 4577 達航科技股份有限公司, 6150 撼訊科技股份有限公司, 6221 晉泰科技股份有限公司, 6234 高僑自動化科技股份有限公司, 6697 東捷資訊服務股份有限公司, 8089 康全電訊股份有限公司
- Picked by more than one strategy (not independent evidence): 1528, 2355, 3029, 4174, 4577, 6150, 6221, 6234, 6697

Full detail: paper/PAPER_REPORT.md
