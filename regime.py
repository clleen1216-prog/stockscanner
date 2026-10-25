"""
regime.py - 宏觀「風險調節」層：Fed 淨流動性 + VIX，加上證據看板與前瞻驗證記錄。

設計原則（來自 2026-10-24 的檢驗結果）：
  * Fed 淨流動性（13 週變化）：S&P 500 / Nasdaq / 加權指數三個市場方向一致為正，但 t 值約 1.6，
    未達事先訂的 2.2 門檻 → 只當「風險調節」：流動性收縮時把部位縮小，絕不放大部位，也不加進任何選股分數。
  * VIX：常見的風險準則（不是經過檢驗的報酬預測）→ 同樣只縮小部位。
  * 13F 機構加碼：兩個訊號都未通過（t 約 0.4~0.5）→ 只當資訊（證據看板與資料匯出），不進任何分數或部位。
  * 規則固定、不調參。是否真的有用，由 paper/macro_log.csv 的前瞻驗證在「沒看過的新資料」上判定。
"""
import json
import math
import os
from datetime import datetime

import numpy as np
import pandas as pd

LOOKBACK_DAYS = 63                       # 13 週 ≈ 63 個交易日（與 fed_liquidity.py 的設定相同）
MIN_PERIODS = 12                         # 前瞻驗證至少 12 期（約 1 年）
T_REQUIRED = 2.2
LOG_EVERY_DAYS = 28
EVIDENCE_PATH = os.path.join("reports_us", "evidence.json")
MACRO_LOG = os.path.join("paper", "macro_log.csv")
LOG_COLS = ["date", "fed_expanding", "vix", "spx", "twii"]

# 部位縮放（只縮不放）：(VIX 上限, 標籤, 倍數)
VIX_BANDS = [(15, "低", 1.0), (20, "正常", 1.0), (30, "升高", 0.75), (40, "高", 0.5), (math.inf, "極端", 0.5)]
FED_CONTRACTING_MULT = 0.75

# 2026-10-24 手動檢驗結果（對應的 workflow 執行後會被真實結果覆蓋）
SEED_EVIDENCE = {
    "13f_growth": {"name": "13F 機構持股成長率（美股）", "periods": 20, "unit": "季", "mean": 0.0037, "t": 0.43,
                   "passed": False, "asof": "20261024", "source": "手動報告（wide 名單）"},
    "13f_breadth": {"name": "13F 加碼家數 − 減碼家數（美股）", "periods": 20, "unit": "季", "mean": 0.0047, "t": 0.51,
                    "passed": False, "asof": "20261024", "source": "手動報告（wide 名單）"},
    "fed_13w_spx": {"name": "Fed 淨流動性 13 週（S&P 500，月）", "periods": 167, "unit": "月", "mean": 0.0054, "t": 1.65,
                    "passed": False, "asof": "20261024", "source": "strategy_test.py（方向為正但未達 2.2）"},
    "fed_13w_qqq": {"name": "Fed 淨流動性 13 週（Nasdaq 100，月）", "periods": 167, "unit": "月", "mean": 0.0067, "t": 1.64,
                    "passed": False, "asof": "20261024", "source": "strategy_test.py"},
    "fed_13w_twii": {"name": "Fed 淨流動性 13 週（加權指數，月）", "periods": 161, "unit": "月", "mean": 0.0066, "t": 1.56,
                     "passed": False, "asof": "20261024", "source": "strategy_test.py"},
}


# ------------------------------------------------------------------ Fed 淨流動性
def fed_from_series(walcl, tga, rrp, today=None):
    """由三個 FRED 序列算出目前的淨流動性狀態。單位：十億美元。資料不足或單位異常回傳 None。"""
    import fed_liquidity as fl
    end = pd.Timestamp(today) if today is not None else pd.Timestamp.today().normalize()
    idx = pd.bdate_range(end=end, periods=400)
    liq = fl.build_liquidity(walcl, tga, rrp, idx).dropna(subset=["net"])
    if len(liq) <= LOOKBACK_DAYS + 5:
        return None
    last, prev = liq.iloc[-1], liq["net"].iloc[-1 - LOOKBACK_DAYS]
    if not np.isfinite(prev) or prev == 0:
        return None
    net = float(last["net"])
    return {"asof": liq.index[-1].strftime("%Y-%m-%d"), "net_bn": net, "chg13_bn": net - float(prev),
            "chg13_pct": net / float(prev) - 1, "expanding": bool(net > prev),
            "assets_bn": float(last["assets"]), "tga_bn": float(last["tga"]), "rrp_bn": float(last["rrp"]),
            "units_ok": bool(1000 <= net <= 12000)}


def fed_state(session):
    try:
        import fed_liquidity as fl
        walcl, tga, rrp = (fl.fetch_fred(session, s) for s in ("WALCL", "WTREGEN", "RRPONTSYD"))
        return fed_from_series(walcl, tga, rrp)
    except Exception as e:
        print(f"⚠️ Fed 流動性資料略過：{type(e).__name__}: {e}")
        return None


# ------------------------------------------------------------------ VIX 與總覽
def vix_level(v):
    for cap, label, mult in VIX_BANDS:
        if v < cap:
            return label, mult
    return "極端", 0.5


def macro_overlay(fed, vix_value):
    """回傳部位倍數（<= 1）。資料缺漏時不調整，並在 notes 說明。"""
    mult, notes = 1.0, []
    if vix_value is not None and np.isfinite(vix_value):
        label, m = vix_level(vix_value)
        mult *= m
        notes.append(f"VIX {vix_value:.1f}（{label}）" + (f" → 部位 ×{m}" if m < 1 else " → 不調整"))
    else:
        notes.append("VIX 資料缺漏，不調整")
    if fed is None or not fed.get("units_ok", False):
        notes.append("Fed 流動性資料缺漏或單位異常，不調整")
    elif fed["expanding"]:
        notes.append("Fed 淨流動性擴張 → 不調整（不因擴張而加碼）")
    else:
        mult *= FED_CONTRACTING_MULT
        notes.append(f"Fed 淨流動性收縮 → 部位 ×{FED_CONTRACTING_MULT}")
    return {"size_mult": round(min(mult, 1.0), 3), "notes": notes}


def get_macro(session):
    """一次取得 Fed / VIX / 兩大指數收盤價，並算出部位倍數。任何一項失敗都不會讓主程式中斷。"""
    import stock_scanner as sc
    out = {"fed": fed_state(session), "vix": None, "spx": None, "twii": None}
    for key, sym in (("vix", "^VIX"), ("spx", "^GSPC"), ("twii", "^TWII")):
        try:
            s = sc.fetch_index_close(session, sym, "1mo")
            out[key] = float(s.iloc[-1]) if s is not None and len(s) else None
        except Exception:
            out[key] = None
    out.update(macro_overlay(out["fed"], out["vix"]))
    return out


def macro_lines(m):
    """報告用的條列（Markdown）。"""
    if not m:
        return ["- 宏觀風險調節：資料暫時無法取得，部位不調整。"]
    L = []
    f = m.get("fed")
    if f and f.get("units_ok"):
        L.append(f"- Fed 淨流動性 ${f['net_bn']/1000:.2f}T（{f['asof']}）：**{'擴張' if f['expanding'] else '收縮'}**，"
                 f"13 週變化 {f['chg13_pct']*100:+.1f}%（資產 {f['assets_bn']/1000:.2f}T − TGA {f['tga_bn']/1000:.2f}T − 逆回購 {f['rrp_bn']/1000:.2f}T）")
    else:
        L.append("- Fed 淨流動性：資料缺漏或單位異常，未採用。")
    L.append(f"- 宏觀部位倍數 **×{m['size_mult']}**：" + "；".join(m["notes"]))
    L.append("- 這是「只縮不放」的風險調節，不是選股訊號：Fed 13 週訊號尚未通過檢驗（見證據看板）。")
    return L


# ------------------------------------------------------------------ 證據看板
def _num(x):
    try:
        x = float(x)
        return x if math.isfinite(x) else None
    except Exception:
        return None


def load_evidence(path=EVIDENCE_PATH):
    data = {k: dict(v) for k, v in SEED_EVIDENCE.items()}
    try:
        with open(path, encoding="utf-8") as fh:
            data.update(json.load(fh))
    except Exception:
        pass
    return data


def update_evidence(key, path=EVIDENCE_PATH, **fields):
    """各檢驗腳本跑完後呼叫，把最新結果寫進 evidence.json（會覆蓋同名的手動種子資料）。"""
    cur = {}
    try:
        with open(path, encoding="utf-8") as fh:
            cur = json.load(fh)
    except Exception:
        pass
    for k in ("mean", "t"):
        if k in fields:
            fields[k] = _num(fields[k])
    fields["passed"] = bool(fields.get("passed", False))
    cur[key] = fields
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(cur, fh, ensure_ascii=False, indent=1)


def evidence_lines(path=EVIDENCE_PATH):
    ev = load_evidence(path)
    L = ["## 證據看板（這些訊號是否通過我們事先訂的檢驗）",
         "| 訊號 | 期數 | 平均超額 | t 值 | 結果 | 日期 / 來源 |", "|---|---|---|---|---|---|"]
    for v in ev.values():
        mean = "—" if v.get("mean") is None else f"{v['mean']*100:+.2f}%"
        t = "—" if v.get("t") is None else f"{v['t']:.2f}"
        L.append(f"| {v.get('name', '?')} | {v.get('periods', '—')}{v.get('unit', '')} | {mean} | {t} | "
                 f"{'✅ 通過' if v.get('passed') else '❌ 未通過'} | {v.get('asof', '—')} / {v.get('source', '')} |")
    L += ["", "- 未通過的訊號只當資訊或風險調節，不進入選股分數。通過與否都需要用之後的新資料再確認。"]
    return L


# ------------------------------------------------------------------ 前瞻驗證（固定規則，不調參）
def verdict(xs):
    xs = [float(x) for x in xs]
    n = len(xs)
    if n < 2:
        return {"n": n, "mean": 0.0, "t": 0.0, "pos": 0.0, "h1": 0.0, "h2": 0.0, "ok": False}
    a = np.array(xs)
    sd = a.std(ddof=1)
    t = float(a.mean() / (sd / math.sqrt(n))) if sd > 0 else 0.0
    h = n // 2
    h1, h2 = float(a[:h].mean()), float(a[h:].mean())
    pos = float((a > 0).mean())
    ok = bool(n >= MIN_PERIODS and a.mean() > 0 and t >= T_REQUIRED and pos >= 0.6 and h1 > 0 and h2 > 0)
    return {"n": n, "mean": float(a.mean()), "t": t, "pos": pos, "h1": h1, "h2": h2, "ok": ok}


def log_macro(macro, path=MACRO_LOG, today=None):
    """約每 28 天記一筆：Fed 狀態 + 當日 S&P 500 / 加權指數收盤。回傳是否有新增。"""
    if not macro or not macro.get("fed") or not macro["fed"].get("units_ok"):
        return False
    if not (macro.get("spx") and macro.get("twii")):
        return False
    today = pd.Timestamp(today) if today is not None else pd.Timestamp.today().normalize()
    df = pd.read_csv(path) if os.path.exists(path) else pd.DataFrame(columns=LOG_COLS)
    if len(df) and (today - pd.Timestamp(df["date"].iloc[-1])).days < LOG_EVERY_DAYS:
        return False
    row = {"date": today.strftime("%Y-%m-%d"), "fed_expanding": int(macro["fed"]["expanding"]),
           "vix": macro.get("vix"), "spx": macro["spx"], "twii": macro["twii"]}
    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)[LOG_COLS]
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    df.to_csv(path, index=False)
    return True


def forward_results(path=MACRO_LOG):
    """每一期超額報酬 = 方向 × (該期報酬 − 平均報酬)，方向 = 流動性擴張 +1、收縮 −1。"""
    if not os.path.exists(path):
        return {}
    df = pd.read_csv(path)
    out = {}
    for col, label in (("spx", "S&P 500"), ("twii", "加權指數")):
        if len(df) < 2:
            out[label] = verdict([])
            continue
        px = df[col].astype(float).values
        rets = px[1:] / px[:-1] - 1
        sign = np.where(df["fed_expanding"].values[:-1] == 1, 1.0, -1.0)
        out[label] = verdict(sign * (rets - rets.mean()))
    return out


def forward_lines(path=MACRO_LOG):
    res = forward_results(path)
    n_log = len(pd.read_csv(path)) if os.path.exists(path) else 0
    L = ["## 宏觀前瞻驗證（Fed 13 週流動性，規則固定、不調參）",
         f"- 已記錄 {n_log} 筆快照（約每 {LOG_EVERY_DAYS} 天一筆）；需要 {MIN_PERIODS} 期（約一年）才判定。"
         "規則：流動性擴張做多、收縮做空，與平均報酬比較。"]
    if res:
        L += ["| 市場 | 完成期數 | 平均超額 | t 值 | 為正比例 | 判定 |", "|---|---|---|---|---|---|"]
        for label, v in res.items():
            status = ("✅ 通過（新資料）" if v["ok"] else "❌ 未通過（新資料）") if v["n"] >= MIN_PERIODS \
                else f"⏳ 樣本不足（{v['n']}/{MIN_PERIODS}）"
            L.append(f"| {label} | {v['n']} | {v['mean']*100:+.2f}% | {v['t']:.2f} | {v['pos']*100:.0f}% | {status} |")
    return L
