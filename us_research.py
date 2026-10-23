"""
us_research.py - 美股策略變體研究：使用與台股完全相同的 12 個變體與通過標準，不另外調整。
用法：python us_research.py [wide|sp500]（也可用環境變數 US_UNIVERSE；預設 wide）
  wide  = 全美股普通股中，最近 20 日成交金額前 3000 檔（較完整、較慢）
  sp500 = S&P 500 現有成分股（較快）
通過標準（事先訂定）：訊號 >= 100 筆、樣本內與樣本外期望值都 > 0、
期望值相對隨機進場 Welch t >= 2.7 且樣本外 t >= 1.65。
"""
import gc
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import analytics as an
import research as rs
import stock_scanner as sc
import us_data as us


def build_us_report(rows, date_str, n_stocks, spx, kind="sp500", cost=0.001, tried=None):
    label = (f"S&P 500 現有成分股 {n_stocks} 檔" if kind == "sp500" else
             f"美股流動性前 {n_stocks} 檔普通股（依最近 20 日成交金額，自 {tried} 檔中挑選）")
    title = "美股 S&P 500" if kind == "sp500" else "美股寬名單(約 3000 檔)"
    txt = rs.build_report(rows, date_str)
    txt = txt.replace(f"# 策略變體研究 {date_str}", f"# {title} 策略變體研究 {date_str}", 1)
    txt = txt.replace("同一份 5 年資料", f"同一份 5 年資料（{label}）", 1)
    bias = ("只回測「現在」的 S&P 500 成分股（倖存者偏差更嚴重：它們是留在指數裡的贏家），實際結果通常更差。"
            if kind == "sp500" else
            "只回測「現在」仍在交易、且「現在」流動性夠高的股票：已下市或已變冷門的股票不在名單裡（倖存者偏差＋以未來資訊選股），實際結果通常更差。")
    txt = txt.replace("只回測目前仍上市櫃的股票（倖存者偏差），實際結果通常更差。", bias)
    extra = ["", "## 美股版補充",
             f"- 交易成本：來回 {cost*100:.1f}%（價差與滑價），無證交稅；美股沒有漲跌幅限制，跳空可能讓停損成交得比停損價更差。",
             "- 市場多空以 S&P 500 是否在 200 日均線之上判定（台股版用 60 日均線）。",
             f"- 股票數 {n_stocks} 檔；訊號數與統計檢定力取決於名單大小。"]
    if kind == "wide":
        extra.append("- 名單由 Nasdaq 官方代號表過濾（排除 ETF、測試、權證、特別股等）；過濾以代號與名稱規則判斷，可能有少數誤判。")
    if spx is not None and len(spx) > 2:
        extra.append(f"- 同期 S&P 500 指數（價格）漲幅 {(spx.iloc[-1] / spx.iloc[0] - 1) * 100:+.0f}%：策略期望值要與「直接買指數」相比才有意義。")
    return txt + "\n" + "\n".join(extra)


def run(dfs, env, cfg, date_str, n_stocks, out_dir, kind="sp500", tried=None):
    rows = rs.run_research(dfs, env, cfg)
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"us_research_{kind}_{date_str}.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(build_us_report(rows, date_str, n_stocks, env.get("spx"), kind, cfg["round_trip_cost"], tried))
    return rows, path


def download(session, universe, cfg, label):
    raw, failed = {}, 0
    with ThreadPoolExecutor(max_workers=cfg["max_workers"]) as ex:
        futs = {ex.submit(us.fetch_us_kline, session, sym, cfg["history_range"]): sym for sym, _ in universe}
        for k, fut in enumerate(as_completed(futs), 1):
            if k % 250 == 0:
                print(f"  {label}下載進度 {k}/{len(universe)}（失敗 {failed}）")
            df = fut.result()
            if df is None:
                failed += 1
            else:
                raw[futs[fut]] = df
    return raw, failed


def main():
    kind = (sys.argv[1] if len(sys.argv) > 1 else os.environ.get("US_UNIVERSE", "wide")).strip().lower()
    if kind not in ("wide", "sp500"):
        kind = "wide"
    cfg = dict(us.US_WIDE_CONFIG if kind == "wide" else us.US_CONFIG)
    session = us.us_session()
    env = us.us_environment(session, cfg["history_range"])
    universe = us.get_us_universe(session) if kind == "wide" else us.get_sp500_list(session)
    if not universe:
        print("❌ 無法取得股票清單。")
        return
    print(f"名單 {len(universe)} 檔（{kind}），下載 5 年資料...")
    raw, failed = download(session, universe, cfg, "")
    print(f"成功 {len(raw)} 檔，失敗 {failed} 檔")
    if kind == "wide":
        keep = us.select_liquid(raw, cfg["wide_universe_size"], cfg["min_price"], cfg["min_dollar_vol"])
    else:
        keep = [s for s, df in raw.items() if len(df) >= 250]
    print(f"納入回測 {len(keep)} 檔\n")
    dfs = {s: an.add_indicators(raw[s]) for s in keep}
    del raw
    gc.collect()
    date_str = datetime.now().strftime("%Y%m%d")
    _, path = run(dfs, env, cfg, date_str, len(dfs), cfg["report_dir"], kind, len(universe))
    print(f"\n📁 美股研究報告已存檔至 {path}")


if __name__ == "__main__":
    main()
