# Daily digest

Paper trading only. No real money. Research, not investment advice.

Last run finished: 2026-10-27T10:19:24Z (UTC)

## Market state
- TAIEX 46096 vs 60-day average 46282: **below (weak)**
- S&P 500 overnight: +0.70%
- Macro position multiplier: x1.0 (only ever shrinks size)

## Pipeline health
- Price data: 1965 of 1979 stocks usable
- Latest price bar: 2026-10-27; 8.8% of stocks closed exactly at their open
- Fed liquidity feed: **NOT WORKING** (FredError: WALCL failed after 4 tries (csv ConnectionError: HTTPSConnectionPool(host='fred.stlouisfed.org', port=443): Max retries exceeded with url: /graph/fredgraph.csv?id=WALCL (Caused by ReadTimeoutError("HTTPSConnec))

## Paper strategies
A strategy needs 100 closed trades before any verdict. The decision rules are in PLAN.md; the monthly check writes paper/STATUS.md.

| Strategy | Signals | Open | Closed | Progress |
|---|---|---|---|---|
| V6 | 7 | 7 | 0 | 0/100 |
| V8 | 17 | 17 | 0 | 0/100 |
| V10 | 33 | 33 | 0 | 0/100 |
| V11 | 13 | 13 | 0 | 0/100 |

## New signals today (46), simulated entry at next open
- V6: 1402 遠東新, 1532 勤美, 2010 春源, 2520 冠德, 2820 華票, 4540 全球傳動, 6177 達麗
- V8: 1103 嘉泥, 2010 春源, 2031 新光鋼, 2379 瑞昱, 2520 冠德, 2892 第一金, 3005 神基, 3045 台灣大, 3592 瑞鼎, 9917 中保科, 6140 訊達電腦股份有限公司, 6751 智聯服務股份有限公司
- V10: 1808 潤隆, 2204 中華, 2379 瑞昱, 2468 華經, 2520 冠德, 2607 榮運, 2618 長榮航, 2885 元大金, 3029 零壹, 3702 大聯大, 3705 永信, 8464 億豐, 1569 濱川企業股份有限公司, 2221 大甲永和機械工業股份有限公司, 5228 鈺鎧科技股份有限公司, 5426 振發實業股份有限公司, 6221 晉泰科技股份有限公司, 6245 立端科技股份有限公司
- V11: 2328 廣宇, 3406 玉晶光, 4566 時碩工業, 4720 德淵, 6277 宏正, 3498 陽程科技股份有限公司, 4533 協易機械工業股份有限公司, 6751 智聯服務股份有限公司, 8089 康全電訊股份有限公司
- Picked by more than one strategy (not independent evidence): 2010, 2379, 2520, 6751

Full detail: paper/PAPER_REPORT.md
