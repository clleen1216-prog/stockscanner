"""
us_research.py - 美股(S&P 500) 策略變體研究：使用與台股完全相同的 12 個變體與通過標準，不另外調整。
通過標準（事先訂定）：訊號 >= 100 筆、樣本內與樣本外期望值都 > 0、
期望值相對隨機進場 Welch t >= 2.7 且樣本外 t >= 1.65。
"""
import gc
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import analytics as an
import research as rs
import stock_scanner as sc
import us_data as us


def build_us_report(rows, date_str, n_stocks, spx):
    txt = rs.build_report(rows, date_str)
    txt = txt.replace(f"# 策略變體研究 {date_str}", f"# 美股 S&P 500 策略變體研究 {date_str}", 1)
    txt = txt.replace("同一份 5 年資料", f"同一份 5 年資料（S&P 500 現有成分股 {n_stocks} 檔）", 1)
    txt = txt.replace("只回測目前仍上市櫃的股票（倖存者偏差），實際結果通常更差。",
                      "只回測「現在」的 S&P 500 成分股（倖存者偏差更嚴重：它們是留在指數裡的贏家），實際結果通常更差。")
    extra = ["", "## 美股版補充",
             f"- 交易成本：來回 {us.US_CONFIG['round_trip_cost']*100:.1f}%（價差與滑價），無證交稅；美股沒有漲跌幅限制，跳空可能讓停損成交得比停損價更差。",
             "- 市場多空以 S&P 500 是否在 200 日均線之上判定（台股版用 60 日均線）。",
             f"- 只有約 {n_stocks} 檔股票，訊號數比台股少，統計檢定力較弱。"]
    if spx is not None and len(spx) > 2:
        extra.append(f"- 同期 S&P 500 指數（價格）漲幅 {(spx.iloc[-1] / spx.iloc[0] - 1) * 100:+.0f}%：策略期望值要與「直接買指數」相比才有意義。")
    return txt + "\n" + "\n".join(extra)


def run(dfs, env, cfg, date_str, n_stocks, out_dir):
    rows = rs.run_research(dfs, env, cfg)
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"us_research_{date_str}.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(build_us_report(rows, date_str, n_stocks, env.get("spx")))
    return rows, path


def main():
    cfg = dict(us.US_CONFIG)
    session = sc.create_session()
    env = us.us_environment(session, cfg["history_range"])
    universe = us.get_sp500_list(session)
    if not universe:
        print("❌ 無法取得 S&P 500 成分股清單。")
        return
    print(f"S&P 500 成分股 {len(universe)} 檔，下載 5 年資料...")
    dfs = {}
    with ThreadPoolExecutor(max_workers=cfg["max_workers"]) as ex:
        futs = {ex.submit(us.fetch_us_kline, session, sym, cfg["history_range"]): sym for sym, _ in universe}
        for k, fut in enumerate(as_completed(futs), 1):
            if k % 100 == 0:
                print(f"  下載進度 {k}/{len(universe)}")
            df = fut.result()
            if df is not None and len(df) >= 250:
                dfs[futs[fut]] = an.add_indicators(df)
    print(f"可用股票 {len(dfs)} 檔\n")
    date_str = datetime.now().strftime("%Y%m%d")
    _, path = run(dfs, env, cfg, date_str, len(dfs), cfg["report_dir"])
    print(f"\n📁 美股研究報告已存檔至 {path}")
    gc.collect()


if __name__ == "__main__":
    main()
