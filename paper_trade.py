"""
paper_trade.py - 紙上交易（前瞻驗證）：同時追蹤 4 個策略（V6 對照組 + V8 / V10 / V11），不用真錢。
- 訊號日收盤後產生訊號 → 隔日開盤價「模擬進場」→ 停損 / 收盤跌破20MA / 最長60天 出場（含交易成本）
- 每次執行都用最新資料重新結算所有未結束的交易（可重複執行，不會重複記錄）
- 同時記錄「同期間大盤報酬」與「訊號當天大盤多空」，用來檢查策略是否只是靠多頭行情
- 每天備份三大法人買賣超資料到 paper/chips/，累積之後可回測「法人連買」策略
輸出：paper/ledger.csv（逐筆紀錄）、paper/PAPER_REPORT.md（績效報告）
"""
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import numpy as np
import pandas as pd

import analytics as an
import archive
import regime
import research as rs
import stock_scanner as sc

PAPER_DIR = "paper"
LEDGER = os.path.join(PAPER_DIR, "ledger.csv")
LAST_RUN = os.path.join(PAPER_DIR, "last_run.json")
MIN_CLOSED_FOR_VERDICT = 100
PAPER_SLIPPAGE = 0.001      # extra 0.1% haircut per round trip on top of fees and tax (real fills are worse)
LIMIT_UP_GAP = 0.09         # open 9%+ above the signal close = locked limit-up, a real order would not fill
STRAT_KEYS = ["V6", "V8", "V10", "V11"]
COLS = ["strategy", "signal_date", "code", "name", "market", "status", "entry_date", "entry_price",
        "stop", "risk_frac", "exit_date", "exit_price", "exit_reason", "bars", "ret", "R",
        "last_close", "unreal_R", "bull", "bench_ret", "chip_foreign_lots", "chip_trust_lots",
        "fed_expanding", "vix_close", "turnover20"]


def strategy_cfgs():
    out = {}
    for key in STRAT_KEYS:       # 與研究報告的變體設定完全相同
        ov = next(o for n, o in rs.VARIANTS if n.split()[0] == key)
        out[key] = {**sc.CONFIG, **ov, "skip_samples": True}
    return out


def resolve(d, i, cfg):
    """以最新資料重新模擬第 i 根 K 棒產生的訊號，回傳該筆交易目前狀態。
    v3 fill realism: a gap-up open of LIMIT_UP_GAP or more is "unfillable" (no trade), and every trade pays
    PAPER_SLIPPAGE on top of the standard cost. Both apply to every open trade on every run."""
    n = len(d)
    j0 = i + 1
    if j0 >= n:
        return {"status": "pending"}
    o, h, l, c = d["Open"].values, d["High"].values, d["Low"].values, d["Close"].values
    entry = float(o[j0])
    if np.isfinite(entry) and np.isfinite(c[i]) and entry >= float(c[i]) * (1 + LIMIT_UP_GAP):
        return {"status": "unfillable", "entry_date": d.index[j0].strftime("%Y-%m-%d"),
                "entry_price": round(entry, 2), "exit_reason": "limit_up_open"}
    r = an.simulate_trade(o, h, l, c, d["ATR14"].values, i, cfg, d["MA20"].values)
    if r is None:
        return {"status": "invalid"}
    rf = r["risk_frac"]
    ret = r["ret"] - PAPER_SLIPPAGE
    out = {"entry_date": d.index[j0].strftime("%Y-%m-%d"), "entry_price": round(entry, 2),
           "stop": round(entry * (1 - rf), 2), "risk_frac": round(rf, 4),
           "last_close": round(float(c[-1]), 2)}
    closed = r["reason"] != "time" or j0 + cfg["hold_days"] <= n
    if closed:
        out.update(status="closed", exit_date=d.index[j0 + r["bars"] - 1].strftime("%Y-%m-%d"),
                   exit_price=round(entry * (1 + r["ret"] + an.ROUND_TRIP_COST), 2),
                   exit_reason=r["reason"], bars=r["bars"], ret=round(ret, 4), R=round(ret / rf, 3))
    else:
        ur = float(c[-1]) / entry - 1 - an.ROUND_TRIP_COST - PAPER_SLIPPAGE
        out.update(status="open", bars=n - j0, unreal_R=round(ur / rf, 3))
    return out


def process_stock(code, name, market, df, cfgs, open_rows, chips, env):
    d = an.add_indicators(df)
    last = d.iloc[-1]
    avg_vol = float(d["Volume"].iloc[-20:].mean())
    base = sc.CONFIG
    liquid = (last["Close"] >= base["min_price"] and base["min_avg_vol_20d"] <= avg_vol <= base["max_avg_vol_20d"]
              and np.isfinite(last["ATR14"]))
    updates, new_sigs = {}, []
    sig_date = d.index[-1].strftime("%Y-%m-%d")
    bull = None
    if env.get("bull_by_date") is not None:
        b = env["bull_by_date"].asof(d.index[-1])
        bull = None if pd.isna(b) else bool(b > 0.5)
    ch = chips.get(code)
    macro = env.get("macro") or {}
    fed = macro.get("fed") or {}
    fed_flag = int(fed["expanding"]) if fed.get("units_ok") else None   # 訊號當天的 Fed 流動性狀態（前瞻驗證用）
    for key, cfg in cfgs.items():
        rows = open_rows.get(key, [])
        for sd in rows:                              # 更新這檔股票尚未結束的交易
            loc = d.index.get_indexer([pd.Timestamp(sd)])[0]
            if loc >= 0:
                updates[(key, code, sd)] = resolve(d, loc, cfg)
        # 這檔股票在此策略下仍有未結束的交易 → 不重複開新單；剛好今天結束的則可接受今天的新訊號
        active = any(updates.get((key, code, sd), {"status": "open"})["status"] in ("pending", "open") for sd in rows)
        if not active and liquid:
            s, _ = an.compute_signals(d, cfg)
            if bool(s["entry"].iloc[-1]):
                new_sigs.append({"strategy": key, "signal_date": sig_date, "code": code, "name": name.strip(),
                                 "market": market, "status": "pending", "bull": bull,
                                 "fed_expanding": fed_flag, "vix_close": macro.get("vix"),
                                 "turnover20": round(float((d["Close"] * d["Volume"]).iloc[-20:].mean()), 0),
                                 "chip_foreign_lots": int(ch["foreign"] / 1000) if ch else None,
                                 "chip_trust_lots": int(ch["trust"] / 1000) if ch else None})
    return updates, new_sigs


def apply_updates(ledger, updates, new_sigs):
    for (key, code, sig_date), upd in updates.items():
        m = ((ledger["strategy"] == key) & (ledger["code"].astype(str) == code)
             & (ledger["signal_date"] == sig_date))
        for k, v in upd.items():
            ledger.loc[m, k] = v
    if new_sigs:
        add = pd.DataFrame(new_sigs, columns=COLS).astype(object)
        ledger = pd.concat([ledger, add], ignore_index=True) if len(ledger) else add
    return ledger


def fill_bench(ledger, series):
    """已結束的交易，補上「同期間大盤報酬」（進場日收盤到出場日收盤，約略值）。"""
    if series is None:
        return ledger
    todo = ledger[(ledger["status"] == "closed") & ledger["bench_ret"].isna()]
    for idx, r in todo.iterrows():
        b0, b1 = series.asof(pd.Timestamp(r["entry_date"])), series.asof(pd.Timestamp(r["exit_date"]))
        if pd.notna(b0) and pd.notna(b1) and b0 > 0:
            ledger.at[idx, "bench_ret"] = round(float(b1 / b0 - 1), 4)
    return ledger


def closed_frame(closed):
    return closed.assign(ret=closed["ret"].astype(float), R=closed["R"].astype(float),
                         bars=closed["bars"].astype(float), date=pd.to_datetime(closed["signal_date"]))


def verdict(closed):
    n = len(closed)
    if n < MIN_CLOSED_FOR_VERDICT:
        return f"⏳ 樣本不足（{n}/{MIN_CLOSED_FOR_VERDICT}）"
    c = closed_frame(closed)
    sm = an.summarize(c)
    bench = closed["bench_ret"].dropna().astype(float)
    excess_ok = True
    if len(bench) >= 30:
        excess_ok = c.loc[bench.index, "ret"].mean() > bench.mean()
    return "✅ 前瞻為正且達顯著，可考慮極小額實測" if (sm["expectancy_R"] > 0 and sm["t_stat"] >= 1.65 and excess_ok) \
        else "❌ 未達標，建議放棄"


def build_report(ledger, date_str, extra=None):
    L = [f"# 紙上交易報告 {date_str}", "",
         "同時追蹤 4 個策略，**純模擬，沒有使用真錢**：V6（對照組）、V8 價漲量增突破、V10 資金累積(CMF)、V11 強勢股帶量創高。",
         "回測期望值：V6 +0.15R、V8 +0.06R、V10 +0.08R、V11 +0.09R；這份紙上交易要驗證它們在「沒看過的新資料」上是否成立。", "",
         "## 各策略績效（已結束交易，含交易成本）",
         "| 策略 | 累計訊號 | 已結束 | 持有中 | 勝率 | 平均每筆 | t 值 | 平均報酬 | 同期大盤 | 判定 |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for key in STRAT_KEYS:
        g = ledger[ledger["strategy"] == key]
        cl = g[g["status"] == "closed"]
        op = int((g["status"] == "open").sum())
        if len(cl):
            c = closed_frame(cl)
            sm = an.summarize(c)
            bench = cl["bench_ret"].dropna().astype(float)
            bench_txt = f"{bench.mean()*100:+.1f}%" if len(bench) else "—"
            L.append(f"| {key} | {len(g)} | {len(cl)} | {op} | {sm['win_rate']*100:.1f}% | {sm['expectancy_R']:+.2f}R | "
                     f"{sm['t_stat']:.2f} | {c['ret'].mean()*100:+.1f}% | {bench_txt} | {verdict(cl)} |")
        else:
            L.append(f"| {key} | {len(g)} | 0 | {op} | — | — | — | — | — | {verdict(cl)} |")
    L += ["", f"**判定規則（事先訂定）**：每個策略需 ≥ {MIN_CLOSED_FOR_VERDICT} 筆已結束交易，平均每筆 > 0、t ≥ 1.65，"
          "且平均報酬高於同期大盤，才考慮極小額實測；否則放棄。不因中途結果調整規則。", ""]

    L += ["## 多頭 vs 空頭（訊號當天加權指數是否在季線之上）",
          "| 策略 | 多頭：筆數 / 平均每筆 | 空頭：筆數 / 平均每筆 |", "|---|---|---|"]
    for key in STRAT_KEYS:
        cl = ledger[(ledger["strategy"] == key) & (ledger["status"] == "closed")]
        cells = []
        for flag in (True, False):
            sub = cl[cl["bull"] == flag]
            cells.append(f"{len(sub)} / {sub['R'].astype(float).mean():+.2f}R" if len(sub) >= 10
                         else f"{len(sub)} / 樣本不足")
        L.append(f"| {key} | {cells[0]} | {cells[1]} |")

    L += ["", "## Fed 流動性狀態 vs 結果（訊號當天，前瞻資料；每格 ≥ 10 筆才顯示平均）",
          "| 策略 | 流動性擴張：筆數 / 平均每筆 | 流動性收縮：筆數 / 平均每筆 |", "|---|---|---|"]
    for key in STRAT_KEYS:
        cl = ledger[(ledger["strategy"] == key) & (ledger["status"] == "closed")]
        flag = pd.to_numeric(cl["fed_expanding"], errors="coerce")
        cells = []
        for val in (1, 0):
            sub = cl[flag == val]
            cells.append(f"{len(sub)} / {sub['R'].astype(float).mean():+.2f}R" if len(sub) >= 10
                         else f"{len(sub)} / 樣本不足")
        L.append(f"| {key} | {cells[0]} | {cells[1]} |")

    opn = ledger[ledger["status"] == "open"]
    pend = ledger[ledger["status"] == "pending"]
    L += ["", f"## 持有中 {len(opn)} 筆｜今日新訊號 {len(pend)} 筆（隔日開盤模擬進場）"]
    if len(pend):
        multi = pend.groupby("code")["strategy"].apply(list)
        for key in STRAT_KEYS:
            sub = pend[pend["strategy"] == key]
            if len(sub):
                names = "、".join(f"{r.code} {r['name']}" for _, r in sub.head(15).iterrows())
                L.append(f"- {key}（{len(sub)} 檔）：{names}{'…' if len(sub) > 15 else ''}")
        both = [f"{c} {pend[pend['code'] == c].iloc[0]['name']}（{'+'.join(v)}）" for c, v in multi.items() if len(v) >= 2]
        if both:
            L.append(f"- 同時被多個策略選中：{'、'.join(both[:15])}")
    L += [""] + list(extra or [])
    L += ["", "## 注意",
          "- 這 4 個策略都是「買強勢股」，訊號高度重疊，不是 4 個獨立的驗證。",
          "- 這是模擬，真實交易會有滑價、漲跌停鎖死買不到等問題，結果通常更差。",
          "- 同期大盤為進場日到出場日加權指數的約略報酬，用來檢查策略是否只是跟著大盤漲。",
          "- 僅供研究學習，非投資建議。"]
    return "\n".join(L)


def save_chips(twse, tpex):
    os.makedirs(os.path.join(PAPER_DIR, "chips"), exist_ok=True)
    for mk, data in (("TWSE", twse), ("TPEx", tpex)):
        day = sc.CHIP_DATES.get(mk)
        if data and day:
            path = os.path.join(PAPER_DIR, "chips", f"chips_{mk}_{day}.csv")
            if not os.path.exists(path):
                pd.DataFrame([{"code": k, "foreign_shares": v["foreign"], "trust_shares": v["trust"]}
                              for k, v in data.items()]).to_csv(path, index=False)


def run_summary(env, new_sigs, ledger, n_stocks, n_fetched):
    """Small machine-readable record of this run, read by digest.py and heartbeat.py."""
    macro = env.get("macro") or {}
    fed = macro.get("fed") or {}
    return {
        "finished_utc": datetime.now(timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "twii_close": env.get("twii_close"), "twii_ma60": env.get("twii_ma60"),
        "twii_above_ma60": bool(env.get("is_day_bullish")), "sp500_overnight_pct": env.get("night_pct"),
        "size_mult": macro.get("size_mult"), "vix": macro.get("vix"),
        "fed_ok": bool(fed.get("units_ok")), "fed_error": fed.get("error"),
        "stocks_listed": n_stocks, "stocks_fetched": n_fetched,
        "new_signals": [{"strategy": s["strategy"], "code": s["code"], "name": s["name"]} for s in new_sigs],
        "ledger_rows": int(len(ledger)),
    }


def main():
    sc.CONFIG["history_range"] = "2y"
    cfgs = strategy_cfgs()
    os.makedirs(PAPER_DIR, exist_ok=True)
    if os.path.exists(LEDGER):
        ledger = pd.read_csv(LEDGER, encoding="utf-8-sig", dtype={"code": str})
    else:
        ledger = pd.DataFrame(columns=COLS)
    if "strategy" not in ledger.columns:
        ledger["strategy"] = "V6"                    # 舊版帳本只追蹤 V6
    for c in COLS:
        if c not in ledger.columns:
            ledger[c] = None
    ledger = ledger[COLS].astype(object)

    session = sc.create_session()
    env = sc.check_market_environment(session)
    try:
        env["macro"] = regime.get_macro(session)
        if regime.log_macro(env["macro"], os.path.join(PAPER_DIR, "macro_log.csv")):
            print("已新增一筆宏觀前瞻快照。")
    except Exception as e:
        env["macro"] = None
        print(f"⚠️ 宏觀快照略過：{type(e).__name__}: {e}")
    stock_list = sc.get_taiwan_stock_list()
    if not stock_list:
        print("❌ 無法取得股票清單。")
        return
    twse, tpex = sc.fetch_institutional_data()
    save_chips(twse, tpex)

    open_by = {}
    for _, r in ledger[ledger["status"].isin(["pending", "open"])].iterrows():
        open_by.setdefault(str(r["code"]), {}).setdefault(r["strategy"], []).append(r["signal_date"])

    updates, new_sigs = {}, []
    fetched = 0
    bars = []
    with ThreadPoolExecutor(max_workers=sc.CONFIG["max_workers"]) as ex:
        futs = {ex.submit(sc.fetch_stock_kline, session, code, market): (code, name, market)
                for code, name, market in stock_list}
        for k, fut in enumerate(as_completed(futs), 1):
            if k % 200 == 0:
                print(f"進度 {k}/{len(stock_list)}")
            code, name, market = futs[fut]
            df = fut.result()
            if df is None or len(df) < 250:
                continue
            fetched += 1
            bars.append(archive.bar_row(code, name, market, df))
            chips = twse if market == "TWSE" else tpex
            upd, sigs = process_stock(code, name, market, df, cfgs, open_by.get(code, {}), chips, env)
            updates.update(upd)
            new_sigs += sigs

    have = set(zip(ledger["strategy"], ledger["code"].astype(str), ledger["signal_date"]))
    new_sigs = [s for s in new_sigs if (s["strategy"], s["code"], s["signal_date"]) not in have]
    ledger = apply_updates(ledger, updates, new_sigs)
    ledger = fill_bench(ledger[COLS], env.get("twii_series"))
    ledger.to_csv(LEDGER, index=False, encoding="utf-8-sig")
    date_str = datetime.now().strftime("%Y-%m-%d")
    with open(os.path.join(PAPER_DIR, "PAPER_REPORT.md"), "w", encoding="utf-8") as fh:
        extra = regime.forward_lines(os.path.join(PAPER_DIR, "macro_log.csv"))
        extra += [""] + regime.macro_lines(env.get("macro")) + [""] + regime.evidence_lines()
        fh.write(build_report(ledger, date_str, extra))
    try:
        archive.save_daily(bars, stock_list)
    except Exception as e:          # the archive must never break the daily run
        print(f"⚠️ archive skipped: {type(e).__name__}: {e}")
    with open(LAST_RUN, "w", encoding="utf-8") as fh:
        json.dump(run_summary(env, new_sigs, ledger, len(stock_list), fetched), fh, ensure_ascii=False, indent=1)
    print(f"新訊號 {len(new_sigs)} 筆｜累計 {len(ledger)} 筆｜已存至 {PAPER_DIR}/")


if __name__ == "__main__":
    main()
