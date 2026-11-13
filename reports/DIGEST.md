# Daily digest

Paper trading only. No real money. Research, not investment advice.

Last run finished: 2026-11-13T10:35:27Z (UTC)

## Market state
- TAIEX 43675 vs 60-day average 46215: **below (weak)**
- S&P 500 overnight: -0.35%
- Macro position multiplier: x1.0 (only ever shrinks size)

## Pipeline health
- Price data: 1970 of 1983 stocks usable
- Latest price bar: 2026-11-13; 8.3% of stocks closed exactly at their open
- Fed liquidity feed: **NOT WORKING** (FredError: WALCL failed after 4 tries (csv ConnectionError: HTTPSConnectionPool(host='fred.stlouisfed.org', port=443): Max retries exceeded with url: /graph/fredgraph.csv?id=WALCL (Caused by ReadTimeoutError("HTTPSConnec))

## Paper strategies
A strategy needs 100 closed trades before any verdict. The decision rules are in PLAN.md; the monthly check writes paper/STATUS.md.

| Strategy | Signals | Open | Closed | Progress |
|---|---|---|---|---|
| V6 | 16 | 2 | 14 | 14/100 |
| V8 | 88 | 44 | 41 | 41/100 |
| V10 | 104 | 36 | 68 | 68/100 |
| V11 | 68 | 35 | 28 | 28/100 |

## Gate
- State: **COLLECTING** as of 2026-11-01 (gate G1 not open yet)
- Capped sleeve: 2 closed trades, 1 signal dates

## New signals today (30), simulated entry at next open
- V6: 2597 潤弘
- V8: 1476 儒鴻, 2816 旺旺保, 3617 碩天, 6689 伊雲谷, 3374 精材科技股份有限公司, 4533 協易機械工業股份有限公司, 6690 安碁資訊股份有限公司, 7767 仁大資訊股份有限公司, 8272 全景軟體股份有限公司
- V10: 1789 神隆, 2355 敬鵬, 2453 凌群, 2611 志信, 3035 智原, 3049 精金, 6589 台康生技, 6757 台灣虎航, 6697 東捷資訊服務股份有限公司
- V11: 1476 儒鴻, 2480 敦陽科, 6108 競國, 6689 伊雲谷, 3374 精材科技股份有限公司, 4533 協易機械工業股份有限公司, 5209 新鼎系統股份有限公司, 6140 訊達電腦股份有限公司, 6690 安碁資訊股份有限公司, 7767 仁大資訊股份有限公司, 8272 全景軟體股份有限公司
- Picked by more than one strategy (not independent evidence): 1476, 3374, 4533, 6689, 6690, 7767, 8272

Full detail: paper/PAPER_REPORT.md
