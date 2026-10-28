# Daily digest

Paper trading only. No real money. Research, not investment advice.

Last run finished: 2026-10-28T10:26:28Z (UTC)

## Market state
- TAIEX 47036 vs 60-day average 46399: **above (bull)**
- S&P 500 overnight: +0.60%
- Macro position multiplier: x1.0 (only ever shrinks size)

## Pipeline health
- Price data: 1969 of 1983 stocks usable
- Latest price bar: 2026-10-28; 10.9% of stocks closed exactly at their open
- Fed liquidity feed: **NOT WORKING** (FredError: WALCL failed after 4 tries (csv ConnectionError: HTTPSConnectionPool(host='fred.stlouisfed.org', port=443): Max retries exceeded with url: /graph/fredgraph.csv?id=WALCL (Caused by ReadTimeoutError("HTTPSConnec))

## Paper strategies
A strategy needs 100 closed trades before any verdict. The decision rules are in PLAN.md; the monthly check writes paper/STATUS.md.

| Strategy | Signals | Open | Closed | Progress |
|---|---|---|---|---|
| V6 | 9 | 9 | 0 | 0/100 |
| V8 | 29 | 29 | 0 | 0/100 |
| V10 | 40 | 37 | 3 | 3/100 |
| V11 | 21 | 21 | 0 | 0/100 |

## New signals today (29), simulated entry at next open
- V6: 2025 千興, 8081 致新
- V8: 1808 潤隆, 2328 廣宇, 2393 億光, 4540 全球傳動, 6415 矽力*-KY, 6689 伊雲谷, 1569 濱川企業股份有限公司, 3374 精材科技股份有限公司, 4716 大立高分子工業股份有限公司, 4714 永捷創新科技股份有限公司, 6179 亞通利大能源股份有限公司, 6233 旺玖科技股份有限公司
- V10: 1709 和益, 3006 晶豪科, 4540 全球傳動, 4174 台灣浩鼎生技股份有限公司, 6233 旺玖科技股份有限公司, 6418 詠昇電子股份有限公司, 6425 易發精機股份有限公司
- V11: 3545 敦泰, 6415 矽力*-KY, 6689 伊雲谷, 1569 濱川企業股份有限公司, 3691 碩禾電子材料股份有限公司, 4716 大立高分子工業股份有限公司, 4714 永捷創新科技股份有限公司, 6233 旺玖科技股份有限公司
- Picked by more than one strategy (not independent evidence): 1569, 4540, 4714, 4716, 6233, 6415, 6689

Full detail: paper/PAPER_REPORT.md
