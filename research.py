"""
research.py - 策略變體研究：事先列好的變體，同一份 5 年資料，逐一回測
判定標準（事先訂好，不看結果調整）：
  1. 歷史訊號 >= 100 筆
  2. 樣本內(前70%) 與 樣本外(後30%) 期望值都 > 0
  3. 期望值顯著高於「同出場規則的隨機進場」(全期間 Welch t >= 2.5，且樣本外 t >= 1.65)
全部通過才標示 ✅，否則一律視為「沒有證據」。
"""
import gc
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import pandas as pd

import analytics as an
import stock_scanner as sc

WIDE = {"atr_stop_mult": 3.0, "min_stop_pct": 0.05, "max_stop_pct": 0.15}
VARIANTS = [
    ("V0 現行策略(停損2xATR/目標2R/20天)", {}),
    ("V1 持有 40 天", {"hold_days": 40}),
    ("V2 寬停損3xATR/目標3R/40天", {**WIDE, "target_R": 3.0, "hold_days": 40}),
    ("V3 移動出場(跌破20MA,最長60天)", {**WIDE, "exit_mode": "trail", "hold_days": 60}),
    ("V4 三個進場訊號全中", {"trig_min": 3}),
    ("V5 上升趨勢整理突破", {"setup_mode": "uptrend_base"}),
    ("V6 上升趨勢+移動出場", {"setup_mode": "uptrend_base", **WIDE, "exit_mode": "trail", "hold_days": 60}),
    ("V7 上升趨勢+三訊號+移動出場", {"setup_mode": "uptrend_base", "trig_min": 3, **WIDE,
                                      "exit_mode": "trail", "hold_days": 60}),
    # --- 第二批（資金流向，價量訊號；出場方式事先固定，不看結果調整）---
    ("V8 價漲量增突破(多頭排列帶量創20日高)+移動出場",
     {"setup_mode": "flow_breakout", **WIDE, "exit_mode": "trail", "hold_days": 60}),
    ("V9 低檔爆量不破底+目標3R/40天",
     {"setup_mode": "low_volume_spike", **WIDE, "target_R": 3.0, "hold_days": 40}),
    ("V10 資金累積(CMF轉強)+移動出場",
     {"setup_mode": "cmf_accum", **WIDE, "exit_mode": "trail", "hold_days": 60}),
    ("V11 強勢股帶量創60日高+移動出場",
     {"setup_mode": "momentum_flow", **WIDE, "exit_mode": "trail", "hold_days": 60}),
]
T_REQUIRED = 2.7   # 同時測 12 個變體，門檻由 2.5 提高
MIN_TRADES = 100


def evaluate_variant(dfs, env, base_cfg, overrides):
    cfg = {**base_cfg, **overrides, "skip_samples": True}
    trades, base = [], []
    for code, d in dfs.items():
        s, f = an.compute_signals(d, cfg)
        t, _, b = an.collect_history(code, d, s, f, cfg, env["bull_by_date"])
        trades += t
        base += b
    cols = ["ret", "R", "bars", "reason", "risk_frac", "code", "date", "bull"]
    tdf = pd.DataFrame(trades, columns=cols if not trades else None)
    bdf = pd.DataFrame(base, columns=cols if not base else None)

    ov, bs = an.summarize(tdf), an.summarize(bdf)
    ins = oos = an.summarize(tdf.iloc[0:0])
    t_oos = 0.0
    if len(tdf) >= 20:
        o = tdf.sort_values("date")
        cut = int(len(o) * 0.7)
        ins, oos = an.summarize(o.iloc[:cut]), an.summarize(o.iloc[cut:])
        cut_date = o["date"].iloc[cut]
        b_late = bdf[bdf["date"] >= cut_date] if len(bdf) else bdf
        t_oos = an.welch_t(o.iloc[cut:]["R"], b_late["R"]) if len(b_late) else 0.0
    t_all = an.welch_t(tdf["R"], bdf["R"]) if len(tdf) and len(bdf) else 0.0
    passed = bool(ov["n"] >= MIN_TRADES and ins["expectancy_R"] > 0 and oos["expectancy_R"] > 0
                  and t_all >= T_REQUIRED and t_oos >= 1.65)
    return {"ov": ov, "bs": bs, "ins": ins, "oos": oos, "t_all": t_all, "t_oos": t_oos, "passed": passed}


def run_research(dfs, env, base_cfg):
    rows = []
    for name, ov in VARIANTS:
        t0 = time.time()
        r = evaluate_variant(dfs, env, base_cfg, ov)
        r["name"] = name
        rows.append(r)
        o = r["ov"]
        print(f"{name}: n={o['n']} 勝率={o['win_rate']*100:.1f}% 期望值={o['expectancy_R']:+.2f}R "
              f"| 隨機 {r['bs']['expectancy_R']:+.2f}R | t={r['t_all']:.2f} "
              f"| 樣本外 {r['oos']['expectancy_R']:+.2f}R (n={r['oos']['n']}) "
              f"{'✅' if r['passed'] else '—'} ({time.time()-t0:.0f}s)")
    return rows


def build_report(rows, date_str):
    L = [f"# 策略變體研究 {date_str}", "",
         f"同一份 5 年資料、事先列好的 {len(VARIANTS)} 個變體，含交易成本。每個變體都與「相同出場規則的隨機進場」比較。", "",
         f"**通過標準（事先訂定）**：訊號 ≥ {MIN_TRADES} 筆、樣本內與樣本外期望值都 > 0、"
         f"期望值相對隨機進場的 t 值 ≥ {T_REQUIRED}（已因同時測 12 個變體而提高門檻），且樣本外 t 值 ≥ 1.65。", "",
         "| 變體 | 訊號數 | 勝率 | 期望值 | 隨機進場期望值 | t 值 | 樣本內 | 樣本外 (n) | 結果 |",
         "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        o, b = r["ov"], r["bs"]
        L.append(f"| {r['name']} | {o['n']} | {o['win_rate']*100:.1f}% | {o['expectancy_R']:+.2f}R | "
                 f"{b['expectancy_R']:+.2f}R | {r['t_all']:.2f} | {r['ins']['expectancy_R']:+.2f}R | "
                 f"{r['oos']['expectancy_R']:+.2f}R ({r['oos']['n']}) | {'✅ 通過' if r['passed'] else '❌ 未通過'} |")
    winners = [r for r in rows if r["passed"]]
    L += ["", "## 結論"]
    if winners:
        L += [f"- 通過檢驗的變體：{', '.join(w['name'] for w in winners)}。",
              "- 即使通過，仍需先小額模擬追蹤數週再使用；同時測了 12 個變體，仍有少數機率是運氣。"]
    else:
        L += ["- **沒有任何變體通過檢驗。** 在這份資料上找不到可靠的統計優勢，請不要依這些訊號交易。"]
    L += ["", "## 注意事項",
           "- 不同股票在同一天的訊號會一起漲跌，實際的統計信心比 t 值顯示的更低。",
           "- 只回測目前仍上市櫃的股票（倖存者偏差），實際結果通常更差。",
           "- 不要因為某個變體看起來不錯就反覆微調參數；那只是在擬合過去。",
           "- 僅供研究學習，非投資建議。"]
    return "\n".join(L)


def main():
    session = sc.create_session()
    env = sc.check_market_environment(session)
    stock_list = sc.get_taiwan_stock_list()
    if not stock_list:
        print("❌ 無法取得股票清單。")
        return
    print(f"下載 {len(stock_list)} 檔 5 年資料...")
    dfs = {}
    with ThreadPoolExecutor(max_workers=sc.CONFIG["max_workers"]) as ex:
        futs = {ex.submit(sc.fetch_stock_kline, session, c, m): c for c, _, m in stock_list}
        for k, fut in enumerate(as_completed(futs), 1):
            if k % 200 == 0:
                print(f"  下載進度 {k}/{len(stock_list)}")
            df = fut.result()
            if df is not None and len(df) >= 250:
                dfs[futs[fut]] = an.add_indicators(df)
    print(f"可用股票 {len(dfs)} 檔\n")
    rows = run_research(dfs, env, sc.CONFIG)
    os.makedirs(sc.CONFIG["report_dir"], exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d")
    path = os.path.join(sc.CONFIG["report_dir"], f"research_{date_str}.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(build_report(rows, date_str))
    print(f"\n📁 研究報告已存檔至 {path}")
    gc.collect()


if __name__ == "__main__":
    main()
