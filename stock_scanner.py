"""
台股 SOP【高勝率主力佈局】掃描器 v2 - 統計證據 + 風險評估 + AI 洞察
流程：大盤環境 → 全市場 5 年回測(證據) → 機器學習驗證 → 今日候選股機率/風險/部位 → 報表
"""
import gc
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import analytics as an
import regime
from ai_insights import build_rule_insight, llm_summary

# ==============================================================================
# 0. 策略參數設定區
# ==============================================================================
CONFIG = {
    # --- 選股條件（與 v1 相同）---
    "min_price": 5.0,
    "min_avg_vol_20d": 300000,
    "max_avg_vol_20d": 30000000,
    "max_ma_spread": 0.05,
    "max_relative_high": 0.75,
    "max_workers": 12,
    "history_range": "5y",        # 回測所需歷史長度
    # --- 交易模擬 / 風控 ---
    "atr_stop_mult": 2.0,         # 停損 = 2 倍 ATR
    "min_stop_pct": 0.03,         # 停損距離下限 3%
    "max_stop_pct": 0.10,         # 停損距離上限 10%
    "target_R": 2.0,              # 停利 = 2R
    "hold_days": 20,              # 最長持有天數
    "account_risk_pct": 0.01,     # 單筆最大虧損占資金 1%
    "max_position_pct": 0.20,     # 單檔部位上限 20% 資金
    # --- 統計 / AI ---
    "baseline_per_stock": 6,      # 每檔抽幾筆隨機進場作對照
    "bayes_prior_strength": 15,   # 個股勝率向全市場收縮的強度
    "ml_min_samples": 300,
    "ml_shrink": 0.5,
    "llm_model": "claude-sonnet-5-5",
    "llm_top_n": 8,
    "report_dir": "reports",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}


def create_session():
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=0.3, status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry, pool_connections=20, pool_maxsize=20)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


# ==============================================================================
# 1. 宏觀環境
# ==============================================================================
def fetch_index_close(session, symbol, rng):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    res = session.get(url, headers=HEADERS, params={"range": rng, "interval": "1d"}, timeout=8)
    if res.status_code != 200:
        return None
    data = res.json()["chart"]["result"][0]
    s = pd.Series(
        data["indicators"]["quote"][0]["close"],
        index=pd.to_datetime(data["timestamp"], unit="s").normalize(),
    ).dropna()
    return s[~s.index.duplicated(keep="last")]


def check_market_environment(session):
    print("正在檢核大盤總體環境 (日盤季線 + 夜盤國際情緒)...")
    env = {
        "is_day_bullish": True, "night_pct": 0.0, "is_night_safe": True,
        "bull_by_date": None, "twii_ret": None, "twii_close": 0.0, "twii_ma60": 0.0,
        "twii_series": None,
    }
    try:
        twii = fetch_index_close(session, "^TWII", CONFIG["history_range"])
        if twii is not None and len(twii) > 60:
            ma60 = twii.rolling(60).mean()
            env["bull_by_date"] = (twii > ma60).astype(float).where(ma60.notna())
            env["twii_ret"] = twii.pct_change().dropna()
            env["twii_series"] = twii
            env["twii_close"], env["twii_ma60"] = float(twii.iloc[-1]), float(ma60.iloc[-1])
            env["is_day_bullish"] = env["twii_close"] > env["twii_ma60"]
    except Exception as e:
        print(f"⚠️ 日盤指數載入略過: {e}")

    try:
        gspc = fetch_index_close(session, "^GSPC", "5d")
        if gspc is not None and len(gspc) >= 2:
            env["night_pct"] = float((gspc.iloc[-1] / gspc.iloc[-2] - 1) * 100)
    except Exception:
        pass
    env["is_night_safe"] = env["night_pct"] >= -0.5

    print(f"   • 加權指數: {env['twii_close']:.2f} | 季線: {env['twii_ma60']:.2f} "
          f"[{'多頭 ✅' if env['is_day_bullish'] else '弱勢 ⚠️'}]")
    print(f"   • 隔夜 S&P500: {env['night_pct']:+.2f}% [{'安全 🟢' if env['is_night_safe'] else '重挫 🔴'}]\n")
    return env


# ==============================================================================
# 2. 股票清單與三大法人
# ==============================================================================
def get_taiwan_stock_list():
    print("正在下載台股上市櫃股票清單...")
    stocks = []
    session = create_session()
    try:
        res = session.get("https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL", headers=HEADERS, timeout=10)
        if res.status_code == 200:
            for item in res.json():
                code, name = item.get("Code", ""), item.get("Name", "")
                if len(code) == 4 and code.isdigit() and "-DR" not in name:
                    stocks.append((code, name, "TWSE"))
        res = session.get("https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O", headers=HEADERS, timeout=10)
        if res.status_code == 200:
            for item in res.json():
                code, name = item.get("SecuritiesCompanyCode", ""), item.get("CompanyName", "")
                if len(code) == 4 and code.isdigit() and "-DR" not in name:
                    stocks.append((code, name, "TPEx"))
        print(f"成功取得 {len(stocks)} 檔股票代碼。")
        return stocks
    except Exception:
        return []


TW_TZ = timezone(timedelta(hours=8))
CHIP_DATES = {"TWSE": None, "TPEx": None}


def _num(x):
    try:
        return float(str(x).replace(",", "").strip())
    except Exception:
        return 0.0


def _find_col(fields, must):
    for i, f in enumerate(fields):
        if all(m in str(f) for m in must):
            return i
    return None


def parse_twse_t86(js):
    """證交所三大法人買賣超日報 (rwd T86)。欄位以名稱定位，找不到才用預設位置。"""
    out = {}
    if not js or js.get("stat") != "OK" or not js.get("data"):
        return out
    fields = js.get("fields", [])
    fi = _find_col(fields, ["外陸資買賣超"])
    ti = _find_col(fields, ["投信買賣超"])
    fi = 4 if fi is None else fi
    ti = 10 if ti is None else ti
    for row in js["data"]:
        if len(row) > max(fi, ti):
            out[str(row[0]).strip()] = {"foreign": _num(row[fi]), "trust": _num(row[ti])}
    return out


def parse_tpex_3insti(js):
    """櫃買中心三大法人買賣超日報。外資合計買賣超=第 11 欄、投信買賣超=第 14 欄。"""
    out = {}
    if not js:
        return out
    if js.get("tables"):
        rows = js["tables"][0].get("data", [])
    else:
        rows = js.get("aaData") or js.get("data") or []
    for row in rows:
        if len(row) > 13:
            out[str(row[0]).strip()] = {"foreign": _num(row[10]), "trust": _num(row[13])}
    return out


def fetch_institutional_data():
    print("正在下載三大法人最新買賣超資料...")
    session = create_session()
    twse, tpex = {}, {}
    now = datetime.now(TW_TZ)
    for back in range(0, 10):          # 當日資料尚未公布時，往前找最近的交易日
        day = now - timedelta(days=back)
        if day.weekday() >= 5:
            continue
        if not twse:
            try:
                r = session.get("https://www.twse.com.tw/rwd/zh/fund/T86", headers=HEADERS, timeout=15,
                                params={"date": day.strftime("%Y%m%d"), "selectType": "ALL", "response": "json"})
                if r.status_code == 200:
                    twse = parse_twse_t86(r.json())
                    if twse:
                        CHIP_DATES["TWSE"] = day.strftime("%Y-%m-%d")
            except Exception:
                pass
        if not tpex:
            roc = f"{day.year - 1911}/{day.month:02d}/{day.day:02d}"
            try:
                r = session.get("https://www.tpex.org.tw/web/stock/3insti/daily_trade/3itrade_hedge_result.php",
                                headers=HEADERS, timeout=15, params={"l": "zh-tw", "t": "D", "d": roc, "o": "json"})
                if r.status_code == 200:
                    tpex = parse_tpex_3insti(r.json())
                    if tpex:
                        CHIP_DATES["TPEx"] = day.strftime("%Y-%m-%d")
            except Exception:
                pass
        if twse and tpex:
            break
    print(f"法人資料：上市 {len(twse)} 檔（{CHIP_DATES['TWSE']}）、上櫃 {len(tpex)} 檔（{CHIP_DATES['TPEx']}）")
    if not twse and not tpex:
        print("⚠️ 未取得法人資料，A+ 評級將停用。")
    print()
    return twse, tpex


# ==============================================================================
# 3. 日 K（還原權息，回測才準）
# ==============================================================================
def fetch_stock_kline(session, code, market="TWSE"):
    suffix = ".TW" if market == "TWSE" else ".TWO"
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{code}{suffix}"
    params = {"range": CONFIG["history_range"], "interval": "1d", "events": "history"}
    try:
        res = session.get(url, headers=HEADERS, params=params, timeout=10)
        if res.status_code != 200:
            return None
        result = res.json()["chart"]["result"][0]
        q = result["indicators"]["quote"][0]
        adj = (result["indicators"].get("adjclose") or [{}])[0].get("adjclose")
        df = pd.DataFrame(
            {"Open": q["open"], "High": q["high"], "Low": q["low"], "Close": q["close"], "Volume": q["volume"]},
            index=pd.to_datetime(result["timestamp"], unit="s").normalize(),
        )
        if adj is not None and len(adj) == len(df):
            df["Adj"] = adj
        df = df.dropna()
        df = df[~df.index.duplicated(keep="last")]
        if "Adj" in df.columns:
            factor = df["Adj"] / df["Close"]
            for col in ("Open", "High", "Low", "Close"):
                df[col] = df[col] * factor
            df = df.drop(columns="Adj")
        return df
    except Exception:
        return None


# ==============================================================================
# 4. 單檔分析：回溯歷史(證據) + 今日狀態
# ==============================================================================
def analyze_stock(session, stock_info, market_env):
    code, name, market = stock_info
    df = fetch_stock_kline(session, code, market)
    if df is None or len(df) < 180:
        return None

    d = an.add_indicators(df)
    s, f = an.compute_signals(d, CONFIG)
    trades, samples, baseline = an.collect_history(code, d, s, f, CONFIG, market_env["bull_by_date"])

    last = d.iloc[-1]
    avg_vol = float(d["Volume"].iloc[-20:].mean())
    liquid_now = (
        last["Close"] >= CONFIG["min_price"]
        and CONFIG["min_avg_vol_20d"] <= avg_vol <= CONFIG["max_avg_vol_20d"]
    )

    current = None
    if liquid_now and bool(s["setup"].iloc[-1]) and np.isfinite(last["ATR14"]):
        feat = f.iloc[-1].to_dict()
        feat["bull"] = float(market_env["is_day_bullish"])
        vol_ann, max_dd, beta = an.stock_risk_stats(d, market_env["twii_ret"])
        current = {
            "code": code, "name": name.strip(), "market": market,
            "close": float(last["Close"]), "low": float(last["Low"]),
            "body": float(abs(last["Close"] - last["Open"])),
            "is_entry": bool(s["entry"].iloc[-1]), "trig_count": int(s["trig_count"].iloc[-1]),
            "atr": float(last["ATR14"]), "ma60": float(last["MA60"]),
            "avg_vol_lots": int(avg_vol / 1000), "feat": feat,
            "vol_ann": vol_ann, "max_dd": max_dd, "beta": beta,
        }
    return {"code": code, "trades": trades, "samples": samples, "baseline": baseline, "current": current}


# ==============================================================================
# 5. 候選股評估：機率 → 期望值 → 風險 → 部位 → 評級
# ==============================================================================
def evaluate_candidate(cur, ctx):
    env, evidence, ml, trades_df = ctx["env"], ctx["evidence"], ctx["ml"], ctx["trades_df"]
    chip_map = ctx["twse_chips"] if cur["market"] == "TWSE" else ctx["tpex_chips"]
    chips = chip_map.get(cur["code"])
    chip_ok = chips is not None
    chips = chips or {"foreign": 0, "trust": 0}
    foreign_lots, trust_lots = int(chips["foreign"] / 1000), int(chips["trust"] / 1000)
    inst_buy = chip_ok and (chips["foreign"] > 0 or chips["trust"] > 0)

    # 證據母體：同環境(多/空頭)下的全市場歷史；樣本太少就退回全樣本
    reg = evidence["regime"][bool(env["is_day_bullish"])]
    pool = reg if reg["n"] >= 30 else evidence["overall"]

    g = trades_df[trades_df["code"] == cur["code"]] if len(trades_df) else trades_df
    n_s = len(g)
    w_s = int((g["ret"] > 0).sum()) if n_s else 0
    prior = pool["win_rate"] if pool["n"] else 0.5
    p_bayes = an.blend_probability(w_s, n_s, prior, CONFIG["bayes_prior_strength"])
    p_ml = an.predict_ml(ml, cur["feat"], CONFIG)
    p_final = (p_bayes + p_ml) / 2 if p_ml is not None else p_bayes

    ev_R = p_final * pool["avg_win_R"] + (1 - p_final) * pool["avg_loss_R"]

    # 停損/目標/部位
    risk_frac = an.stop_fraction(cur["atr"], cur["close"], CONFIG)
    stop = cur["close"] * (1 - risk_frac)
    target = cur["close"] * (1 + risk_frac * CONFIG["target_R"])
    kelly = an.kelly_fraction(p_final, pool["avg_win_R"], pool["avg_loss_R"])
    risk_used = min(CONFIG["account_risk_pct"], 0.5 * kelly)
    position = min(risk_used / risk_frac, CONFIG["max_position_pct"])
    if not evidence["validated"]:
        position *= 0.5
    # 宏觀風險調節（Fed 流動性 + VIX）：只縮小、不放大；不影響評級與勝率估計
    macro_mult = min(float((env.get("macro") or {}).get("size_mult", 1.0)), 1.0)
    position *= macro_mult

    turnover_m = cur["avg_vol_lots"] * 1000 * cur["close"] / 1e6
    r_score, r_label = an.risk_score(
        cur["atr"] / cur["close"], cur["max_dd"], cur["beta"], turnover_m,
        env["is_day_bullish"], env["is_night_safe"], pool["n"])

    # 評級
    if not cur["is_entry"]:
        grade, suggestion = "Watch", "➖ 列入觀察名單 (等待突破訊號)"
    elif not env["is_day_bullish"]:
        grade, suggestion = "C", "⚠️ 建議觀望 (大盤季線下偏弱)"
    elif not env["is_night_safe"]:
        grade, suggestion = "B-", "🚨 延後進場 (夜盤/美股重挫，防開低回檔)"
    elif ev_R <= 0 or p_final < 0.45:
        grade, suggestion = "C", "⛔ 統計期望值不佳，不建議進場"
    elif (evidence["validated"] and p_final >= 0.55 and ev_R >= 0.3
          and r_score < 60 and inst_buy and pool["n"] >= 30):
        grade, suggestion = "A+", "🔥 強烈建議進場 (勝率/期望值/風險/籌碼皆通過)"
    elif evidence["validated"] and p_final >= 0.50 and ev_R >= 0.15 and r_score < 70:
        grade, suggestion = "A", "✅ 建議進場 (統計優勢成立)"
    else:
        grade, suggestion = "B", "👍 可小部位試單 (證據不足或風險偏高，縮小部位)"

    out = {
        "code": cur["code"], "name": cur["name"], "market": cur["market"],
        "close": round(cur["close"], 2), "is_entry": cur["is_entry"],
        "grade": grade, "suggestion": suggestion, "trig_count": cur["trig_count"],
        "win_prob": round(p_final, 3), "win_prob_bayes": round(p_bayes, 3),
        "win_prob_ml": round(p_ml, 3) if p_ml is not None else None,
        "ev_R": round(ev_R, 2),
        "stock_hist_n": n_s, "stock_hist_wr": round(w_s / n_s, 3) if n_s else 0.0,
        "evidence_n": pool["n"], "evidence_label": an.evidence_strength(pool["n"]),
        "regime_wr_pct": round(pool["win_rate"] * 100, 1),
        "regime_ci_lo": round(pool["ci_lo"] * 100, 1), "regime_ci_hi": round(pool["ci_hi"] * 100, 1),
        "risk_score": r_score, "risk_label": r_label,
        "atr_pct": round(cur["atr"] / cur["close"] * 100, 2),
        "max_dd_1y": round(cur["max_dd"] * 100, 1), "beta": round(cur["beta"], 2),
        "vol_ann_pct": round(cur["vol_ann"] * 100, 1), "turnover_m": round(turnover_m, 1),
        "stop_price": round(stop, 2), "stop_pct": round(risk_frac * 100, 1),
        "target_price": round(target, 2),
        "risk_pct_used": round(risk_used * macro_mult * 100, 2), "position_pct": round(position * 100, 1),
        "macro_mult": macro_mult,
        "ma_spread_pct": round(cur["feat"]["spread"] * 100, 2),
        "vol_ratio": round(cur["feat"]["vol_ratio"], 2),
        "dist_high_pct": round(cur["feat"]["dist_high"] * 100, 1),
        "rsi": round(cur["feat"]["rsi"], 1),
        "avg_vol_lots": cur["avg_vol_lots"],
        "foreign_lots": foreign_lots if chip_ok else None,
        "trust_lots": trust_lots if chip_ok else None, "chip_ok": chip_ok,
        "entry_k_half": round(cur["low"] + cur["body"] / 2, 2),
        "stop_loss_ma60": round(cur["ma60"], 2),
    }
    out["insights"] = build_rule_insight(out, env, evidence)
    if macro_mult < 1:
        out["insights"].append(f"宏觀風險調節：部位 ×{macro_mult}（{'；'.join(env['macro']['notes'])}）。")
    if not chip_ok:
        out["insights"].append("籌碼：未取得此股的法人資料，A+ 評級不適用。")
    return out


# ==============================================================================
# 6. 報表
# ==============================================================================
def pct(x):
    return f"{x * 100:.1f}%"


def verdict_text(ev):
    ov = ev["overall"]
    if ev["validated"]:
        return "✅ 通過統計驗證（顯著優於隨機進場）"
    if ov["n"] >= 30 and ov["expectancy_R"] < 0 and ev["edge_vs_random"] < 0 and ev["p_vs_random"] < 0.05:
        return "❌ 策略顯著劣於隨機進場，不建議依此交易"
    return "⚠️ 未通過統計驗證（優勢不顯著），部位減半"


def build_markdown(env, evidence, ml, picks, ai_text, date_str):
    ov, bs, oos, ins = evidence["overall"], evidence["baseline"], evidence["out_of_sample"], evidence["in_sample"]
    L = [f"# 台股掃描報告 {date_str}", ""]
    L += ["## 1. 大盤環境",
          f"- 加權指數 {env['twii_close']:.0f} / 季線 {env['twii_ma60']:.0f}："
          f"{'多頭 ✅' if env['is_day_bullish'] else '弱勢 ⚠️'}",
          f"- 隔夜 S&P500 {env['night_pct']:+.2f}%：{'安全' if env['is_night_safe'] else '重挫警示'}"]
    L += regime.macro_lines(env.get("macro")) + [""]

    L += ["## 2. 策略統計證據（全市場 5 年回測，含交易成本）",
          f"- 歷史訊號 **{ov['n']}** 次｜勝率 **{pct(ov['win_rate'])}**（95% 區間 {pct(ov['ci_lo'])}~{pct(ov['ci_hi'])}）",
          f"- 期望值 **{ov['expectancy_R']:+.2f}R**（t={ov['t_stat']:.2f}）｜獲利因子 {ov['profit_factor']:.2f}"
          f"｜平均持有 {ov['avg_bars']:.1f} 天｜R 曲線最大回撤 {ov['max_dd_R']:.1f}R",
          f"- 對照組（隨機進場 {bs['n']} 次）勝率 {pct(bs['win_rate'])}，策略優勢 "
          f"{evidence['edge_vs_random'] * 100:+.1f} 個百分點，p 值 {evidence['p_vs_random']:.4f}",
          f"- 樣本內 勝率 {pct(ins['win_rate'])}（n={ins['n']}）→ 樣本外 勝率 {pct(oos['win_rate'])}（n={oos['n']}）",
          f"- 多頭環境 勝率 {pct(evidence['regime'][True]['win_rate'])}（n={evidence['regime'][True]['n']}）｜"
          f"空頭環境 勝率 {pct(evidence['regime'][False]['win_rate'])}（n={evidence['regime'][False]['n']}）",
          f"- 機器學習：{ml.get('status', '—')}"
          + (f"；測試期前 25% 高分訊號勝率 {pct(ml['top_quartile_win'])}（整體 {pct(ml['test_base_rate'])}）"
             if ml.get("valid") else ""),
          f"- **結論：{verdict_text(evidence)}**", ""]

    L += ["## 3. 今日標的"]
    entries = [p for p in picks if p["is_entry"]]
    if not entries:
        L += ["今日無符合進場條件之標的。", ""]
    else:
        L += ["| 標的 | 評級 | 勝率 | 期望值 | 風險 | 停損 | 目標 | 建議部位 |", "|---|---|---|---|---|---|---|---|"]
        for p in entries:
            L.append(f"| {p['code']} {p['name']} | {p['grade']} | {round(p['win_prob'] * 100)}% | {p['ev_R']:+.2f}R | "
                     f"{p['risk_score']}({p['risk_label']}) | ${p['stop_price']} | ${p['target_price']} | {p['position_pct']}% |")
        L.append("")
        for p in entries:
            L += [f"### {p['code']} {p['name']}（{p['grade']}）— {p['suggestion']}"] + [f"- {x}" for x in p["insights"]] + [""]

    watch = [p for p in picks if not p["is_entry"]]
    if watch:
        L += [f"## 4. 觀察名單（{len(watch)} 檔，型態成立但尚未突破）",
              ", ".join(f"{p['code']} {p['name']}" for p in watch), ""]

    if ai_text:
        L += ["## 5. Claude AI 解讀", ai_text, ""]

    L += regime.evidence_lines() + [""]
    L += ["## 注意事項",
          "- 回測使用「目前仍上市櫃」的股票，存在倖存者偏差，實際勝率可能偏低。",
          "- 過去表現不代表未來；勝率為估計值而非保證。請自行評估並控管部位。",
          "- 本報告僅供研究學習，非投資建議。"]
    return "\n".join(L)


# ==============================================================================
# 7. 主程式
# ==============================================================================
def main():
    print("==========================================")
    print(" 台股 SOP 掃描器 v2：統計證據 + 風險評估 + AI")
    print("==========================================")
    session = create_session()
    env = check_market_environment(session)
    try:
        env["macro"] = regime.get_macro(session)
        print("宏觀風險調節：" + "；".join(env["macro"]["notes"]) + f" → 部位倍數 ×{env['macro']['size_mult']}\n")
    except Exception as e:
        env["macro"] = None
        print(f"⚠️ 宏觀風險調節略過：{type(e).__name__}: {e}\n")
    stock_list = get_taiwan_stock_list()
    if not stock_list:
        print("❌ 無法取得股票清單，請稍後再試。")
        return
    twse_chips, tpex_chips = fetch_institutional_data()

    total = len(stock_list)
    print(f"開始掃描與回測，共 {total} 檔（需下載 5 年資料，請耐心等待）...\n")
    all_trades, all_samples, all_base, currents = [], [], [], []
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=CONFIG["max_workers"]) as ex:
        futures = [ex.submit(analyze_stock, session, st, env) for st in stock_list]
        for k, fut in enumerate(as_completed(futures), 1):
            if k % 100 == 0 or k == total:
                print(f"進度: {k}/{total} ({k / total * 100:.1f}%)")
            r = fut.result()
            if r:
                all_trades += r["trades"]
                all_samples += r["samples"]
                all_base += r["baseline"]
                if r["current"]:
                    currents.append(r["current"])
    print(f"\n掃描完畢，耗時 {time.time() - t0:.1f} 秒｜歷史訊號 {len(all_trades)} 筆｜今日型態成立 {len(currents)} 檔")

    empty = ["ret", "R", "bars", "reason", "risk_frac", "code", "date", "bull"]
    trades_df = pd.DataFrame(all_trades, columns=empty if not all_trades else None)
    base_df = pd.DataFrame(all_base, columns=empty if not all_base else None)
    evidence = an.build_evidence(trades_df, base_df)
    ml = an.train_model(pd.DataFrame(all_samples), CONFIG) if all_samples else {"valid": False, "status": "無訓練樣本"}

    ov = evidence["overall"]
    print("\n" + "=" * 65)
    print(f"📊 策略證據：{ov['n']} 次訊號｜勝率 {pct(ov['win_rate'])}｜期望值 {ov['expectancy_R']:+.2f}R"
          f"｜隨機進場勝率 {pct(evidence['baseline']['win_rate'])}｜p={evidence['p_vs_random']:.4f}")
    print(f"🤖 機器學習：{ml.get('status')}")
    print(f"{verdict_text(evidence)}")
    print("=" * 65)

    ctx = {"env": env, "evidence": evidence, "ml": ml, "trades_df": trades_df,
           "twse_chips": twse_chips, "tpex_chips": tpex_chips}
    picks = [evaluate_candidate(c, ctx) for c in currents]
    order = {"A+": 0, "A": 1, "B": 2, "B-": 3, "C": 4, "Watch": 5}
    picks.sort(key=lambda p: (order[p["grade"]], -p["ev_R"]))

    for p in picks:
        if p["is_entry"]:
            print(f"\n🔥 [{p['code']}] {p['name']} ({p['market']}) 評級 {p['grade']} — {p['suggestion']}")
            for line in p["insights"]:
                print(f"   • {line}")
    if not any(p["is_entry"] for p in picks):
        print("\n今日無符合進場條件之標的，請保持耐心。")

    ai_text = llm_summary([p for p in picks if p["is_entry"]], env, evidence, ml,
                          CONFIG["llm_model"], CONFIG["llm_top_n"])
    if ai_text:
        print("\n🧠 Claude 解讀：\n" + ai_text)

    os.makedirs(CONFIG["report_dir"], exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d")
    if picks:
        rows = [{**{k: v for k, v in p.items() if k != "insights"}, "insights": " | ".join(p["insights"])} for p in picks]
        pd.DataFrame(rows).to_csv(os.path.join(CONFIG["report_dir"], f"smart_stock_report_{date_str}.csv"),
                                  index=False, encoding="utf-8-sig")
    with open(os.path.join(CONFIG["report_dir"], f"report_{date_str}.md"), "w", encoding="utf-8") as fh:
        fh.write(build_markdown(env, evidence, ml, picks, ai_text, date_str))
    print(f"\n📁 報表已存檔至 {CONFIG['report_dir']}/ (CSV + Markdown)")

    del all_trades, all_samples, all_base, currents
    gc.collect()


if __name__ == "__main__":
    main()
