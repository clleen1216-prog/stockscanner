"""
paper_trade.py - 紙上交易（前瞻驗證）：不用真錢，每天記錄 V6 策略的訊號，並追蹤每筆的真實結果。
- 訊號日收盤後產生訊號 → 隔日開盤價「模擬進場」→ 停損 / 收盤跌破20MA / 最長60天 出場（含交易成本）
- 每次執行都用最新資料重新結算所有未結束的交易（可重複執行，不會重複記錄）
- 同時每天備份三大法人買賣超資料到 paper/chips/，累積之後可回測「法人連買」策略
輸出：paper/ledger.csv（逐筆紀錄）、paper/PAPER_REPORT.md（績效報告）
"""
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import numpy as np
import pandas as pd

import analytics as an
import research as rs
import stock_scanner as sc

PAPER_DIR = "paper"
LEDGER = os.path.join(PAPER_DIR, "ledger.csv")
MIN_CLOSED_FOR_VERDICT = 100
COLS = ["signal_date", "code", "name", "market", "status", "entry_date", "entry_price", "stop",
        "risk_frac", "exit_date", "exit_price", "exit_reason", "bars", "ret", "R",
        "last_close", "unreal_R", "chip_foreign_lots", "chip_trust_lots"]


def paper_cfg():
    v6 = next(o for n, o in rs.VARIANTS if n.startswith("V6"))      # 與研究報告的 V6 完全相同
    return {**sc.CONFIG, **v6, "skip_samples": True}


def resolve(d, i, cfg):
    """以最新資料重新模擬第 i 根 K 棒產生的訊號，回傳該筆交易目前狀態。"""
    n = len(d)
    j0 = i + 1
    if j0 >= n:
        return {"status": "pending"}
    o, h, l, c = d["Open"].values, d["High"].values, d["Low"].values, d["Close"].values
    r = an.simulate_trade(o, h, l, c, d["ATR14"].values, i, cfg, d["MA20"].values)
    if r is None:
        return {"status": "invalid"}
    entry, rf = float(o[j0]), r["risk_frac"]
    out = {"entry_date": d.index[j0].strftime("%Y-%m-%d"), "entry_price": round(entry, 2),
           "stop": round(entry * (1 - rf), 2), "risk_frac": round(rf, 4),
           "last_close": round(float(c[-1]), 2)}
    closed = r["reason"] != "time" or j0 + cfg["hold_days"] <= n
    if closed:
        out.update(status="closed", exit_date=d.index[j0 + r["bars"] - 1].strftime("%Y-%m-%d"),
                   exit_price=round(entry * (1 + r["ret"] + an.ROUND_TRIP_COST), 2),
                   exit_reason=r["reason"], bars=r["bars"], ret=round(r["ret"], 4), R=round(r["R"], 3))
    else:
        ur = float(c[-1]) / entry - 1 - an.ROUND_TRIP_COST
        out.update(status="open", bars=n - j0, unreal_R=round(ur / rf, 3))
    return out


def process_stock(code, name, market, df, cfg, open_rows, chips):
    d = an.add_indicators(df)
    s, _ = an.compute_signals(d, cfg)
    updates, new_sig = {}, None
    for sig_date in open_rows:                      # 更新這檔股票尚未結束的交易
        loc = d.index.get_indexer([pd.Timestamp(sig_date)])[0]
        if loc >= 0:
            updates[sig_date] = resolve(d, loc, cfg)
    last = d.iloc[-1]
    avg_vol = float(d["Volume"].iloc[-20:].mean())
    liquid = (last["Close"] >= cfg["min_price"] and cfg["min_avg_vol_20d"] <= avg_vol <= cfg["max_avg_vol_20d"]
              and np.isfinite(last["ATR14"]))
    if bool(s["entry"].iloc[-1]) and liquid and not open_rows:
        ch = chips.get(code)
        new_sig = {"signal_date": d.index[-1].strftime("%Y-%m-%d"), "code": code, "name": name.strip(),
                   "market": market, "status": "pending",
                   "chip_foreign_lots": int(ch["foreign"] / 1000) if ch else None,
                   "chip_trust_lots": int(ch["trust"] / 1000) if ch else None}
    return updates, new_sig


def apply_updates(ledger, updates_by_code, new_sigs):
    for (code, sig_date), upd in updates_by_code.items():
        m = (ledger["code"].astype(str) == code) & (ledger["signal_date"] == sig_date)
        for k, v in upd.items():
            ledger.loc[m, k] = v
    if new_sigs:
        add = pd.DataFrame(new_sigs, columns=COLS)
        ledger = pd.concat([ledger, add], ignore_index=True) if len(ledger) else add
    return ledger


def build_report(ledger, date_str):
    closed = ledger[ledger["status"] == "closed"].copy()
    opn = ledger[ledger["status"] == "open"]
    pend = ledger[ledger["status"] == "pending"]
    L = [f"# 紙上交易報告 {date_str}", "",
         "策略：V6（上升趨勢整理突破 + 收盤跌破 20MA 出場）。**純模擬，沒有使用真錢**。",
         "回測期望值 +0.14R（全期間）、+0.04R（最近 30%）— 這份紙上交易要驗證它在「沒看過的新資料」上是否成立。", "",
         "## 目前狀態",
         f"- 累計訊號 {len(ledger)} 筆｜已結束 {len(closed)}｜持有中 {len(opn)}｜待隔日進場 {len(pend)}"]
    if len(closed):
        c = closed.assign(ret=closed["ret"].astype(float), R=closed["R"].astype(float),
                          bars=closed["bars"].astype(float), date=pd.to_datetime(closed["signal_date"]))
        sm = an.summarize(c)
        L += ["", "## 已結束交易（含交易成本）",
              f"- 筆數 **{sm['n']}**｜勝率 **{sm['win_rate']*100:.1f}%**（95% 區間 {sm['ci_lo']*100:.1f}%~{sm['ci_hi']*100:.1f}%）",
              f"- 平均每筆 **{sm['expectancy_R']:+.2f}R**（t={sm['t_stat']:.2f}）｜累計 {c['R'].sum():+.1f}R｜"
              f"獲利因子 {sm['profit_factor']:.2f}｜平均持有 {sm['avg_bars']:.1f} 天",
              f"- 出場原因：" + "、".join(f"{k} {v}" for k, v in closed["exit_reason"].value_counts().items())]
    L += ["", "## 判定（事先訂定，不看結果調整）"]
    if len(closed) < MIN_CLOSED_FOR_VERDICT:
        L.append(f"- ⏳ 樣本不足：需要至少 {MIN_CLOSED_FOR_VERDICT} 筆已結束交易才下結論，目前 {len(closed)} 筆。")
    else:
        ok = sm["expectancy_R"] > 0 and sm["t_stat"] >= 1.65
        L.append("- ✅ 前瞻結果為正且達顯著，可考慮「極小額」實測。" if ok else
                 "- ❌ 前瞻結果未達標（期望值 ≤ 0 或不顯著），建議放棄此策略。")
    if len(opn):
        L += ["", "## 持有中"] + [
            f"- {r.code} {r['name']}｜進場 {r.entry_date} @ {r.entry_price}｜停損 {r.stop}｜"
            f"目前 {r.last_close}｜未實現 {float(r.unreal_R):+.2f}R" for _, r in opn.iterrows()]
    if len(pend):
        L += ["", "## 今日新訊號（隔日開盤模擬進場）"] + [f"- {r.code} {r['name']}（{r.market}）" for _, r in pend.iterrows()]
    L += ["", "## 注意", "- 這是模擬，真實交易會有滑價、漲跌停鎖死買不到等問題，結果通常更差。",
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


def main():
    sc.CONFIG["history_range"] = "2y"
    cfg = paper_cfg()
    os.makedirs(PAPER_DIR, exist_ok=True)
    ledger = (pd.read_csv(LEDGER, encoding="utf-8-sig", dtype={"code": str}) if os.path.exists(LEDGER)
              else pd.DataFrame(columns=COLS))
    for c in COLS:
        if c not in ledger.columns:
            ledger[c] = None
    ledger = ledger[COLS].astype(object)      # 全部用 object，避免空欄位被推成 float 後寫入字串失敗

    session = sc.create_session()
    stock_list = sc.get_taiwan_stock_list()
    if not stock_list:
        print("❌ 無法取得股票清單。")
        return
    twse, tpex = sc.fetch_institutional_data()
    save_chips(twse, tpex)

    pending_rows = ledger[ledger["status"].isin(["pending", "open"])]
    open_by_code = {}
    for _, r in pending_rows.iterrows():
        open_by_code.setdefault(str(r["code"]), []).append(r["signal_date"])

    updates_by_code, new_sigs = {}, []
    with ThreadPoolExecutor(max_workers=sc.CONFIG["max_workers"]) as ex:
        futs = {}
        for code, name, market in stock_list:
            futs[ex.submit(sc.fetch_stock_kline, session, code, market)] = (code, name, market)
        for k, fut in enumerate(as_completed(futs), 1):
            if k % 200 == 0:
                print(f"進度 {k}/{len(stock_list)}")
            code, name, market = futs[fut]
            df = fut.result()
            if df is None or len(df) < 250:
                continue
            chips = twse if market == "TWSE" else tpex
            upd, sig = process_stock(code, name, market, df, cfg, open_by_code.get(code, []), chips)
            for sd, u in upd.items():
                updates_by_code[(code, sd)] = u
            if sig:
                new_sigs.append(sig)

    have = set(zip(ledger["code"].astype(str), ledger["signal_date"]))
    new_sigs = [s for s in new_sigs if (s["code"], s["signal_date"]) not in have]
    ledger = apply_updates(ledger, updates_by_code, new_sigs)
    # 新訊號當天無法進場 → 保持 pending，等下一個交易日更新
    ledger = ledger[COLS]
    ledger.to_csv(LEDGER, index=False, encoding="utf-8-sig")
    date_str = datetime.now().strftime("%Y-%m-%d")
    with open(os.path.join(PAPER_DIR, "PAPER_REPORT.md"), "w", encoding="utf-8") as fh:
        fh.write(build_report(ledger, date_str))
    print(f"新訊號 {len(new_sigs)} 筆｜累計 {len(ledger)} 筆｜已存至 {PAPER_DIR}/")


if __name__ == "__main__":
    main()
