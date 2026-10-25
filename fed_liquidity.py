"""
fed_liquidity.py - 聯準會流動性是否預測 S&P 500 未來 20 日報酬？（資料：FRED 免費公開資料）
淨流動性 = 聯準會總資產 (WALCL) − 財政部 TGA 帳戶 (WTREGEN) − 隔夜逆回購 (RRPONTSYD)

事先訂定的檢驗（不看結果調整）：
  5 個訊號：淨流動性 4 週/13 週/26 週變化 > 0、逆回購 13 週下降、Fed 總資產 13 週上升
  以「不重疊的 20 個交易日區塊」比較 訊號開啟 vs 關閉 的未來 20 日報酬
  通過 = 兩組各 >= 40 個區塊、開啟組平均較高、前半與後半期都較高、Welch t >= 2.5
  為避免偷看未來：週資料(週三數值，週四晚公布)延後 2 天才可使用；逆回購延後 1 天。
"""
import io
import os
from datetime import datetime

import numpy as np
import pandas as pd

import analytics as an
import stock_scanner as sc
import us_data as us

FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={}"
START = "2010-01-01"
FWD = 20
T_REQUIRED = 2.5
MIN_BLOCKS = 40
SIGNALS = [
    ("淨流動性 4 週上升", "net", 20, "up"),
    ("淨流動性 13 週上升", "net", 63, "up"),
    ("淨流動性 26 週上升", "net", 126, "up"),
    ("隔夜逆回購 13 週下降", "rrp", 63, "down"),
    ("Fed 總資產 13 週上升", "assets", 63, "up"),
]


def fetch_fred(session, sid):
    r = session.get(FRED_URL.format(sid), headers=sc.HEADERS, timeout=40)
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text))
    df.columns = ["date", "value"]                     # 欄名新舊版不同，用位置
    df["date"] = pd.to_datetime(df["date"])
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df.dropna().set_index("date")["value"]


def build_liquidity(walcl, tga, rrp, index):
    """把三個序列對齊到交易日，並加上公布延遲，回傳單位為「十億美元」的資料表。"""
    def asof(series, lag_days):
        s = series.copy()
        s.index = s.index + pd.Timedelta(days=lag_days)
        s = s[~s.index.duplicated(keep="last")].sort_index()
        return s.reindex(s.index.union(index)).sort_index().ffill().reindex(index)
    w = asof(walcl, 2) / 1000.0          # 百萬 → 十億
    t = asof(tga, 2) / 1000.0
    r = asof(rrp, 1).fillna(0.0)         # RRPONTSYD 本來就是十億；2013 年以前沒有資料視為 0
    return pd.DataFrame({"assets": w, "tga": t, "rrp": r, "net": w - t - r})


def make_signals(liq):
    out = {}
    for name, col, lb, direction in SIGNALS:
        ch = liq[col].diff(lb)
        sig = (ch > 0) if direction == "up" else (ch < 0)
        out[name] = sig.where(ch.notna())
    return out


def evaluate(spx, liq):
    """回傳每個訊號的統計。spx 為指數收盤價序列（日資料）。"""
    spx = spx[spx.index >= START]
    liq = liq.reindex(spx.index)
    fwd = spx.shift(-(FWD + 1)) / spx.shift(-1) - 1          # 訊號當天收盤後，隔天收盤進場、持有 20 日
    sigs = make_signals(liq)
    rows = []
    for name, sig in sigs.items():
        d = pd.DataFrame({"sig": sig, "fwd": fwd}).dropna()
        d = d.iloc[::FWD]                                      # 不重疊區塊
        on, off = d[d["sig"].astype(bool)]["fwd"], d[~d["sig"].astype(bool)]["fwd"]
        half = len(d) // 2
        halves = []
        for part in (d.iloc[:half], d.iloc[half:]):
            a = part[part["sig"].astype(bool)]["fwd"]
            b = part[~part["sig"].astype(bool)]["fwd"]
            halves.append((a.mean() - b.mean()) if len(a) >= 5 and len(b) >= 5 else np.nan)
        t = an.welch_t(on, off) if len(on) > 1 and len(off) > 1 else 0.0
        excess = (on.mean() - off.mean()) if len(on) and len(off) else 0.0
        passed = bool(len(on) >= MIN_BLOCKS and len(off) >= MIN_BLOCKS and excess > 0
                      and all(h > 0 for h in halves if not np.isnan(h)) and not any(np.isnan(h) for h in halves)
                      and t >= T_REQUIRED)
        rows.append({"name": name, "n_on": len(on), "n_off": len(off),
                     "mean_on": on.mean() if len(on) else np.nan, "mean_off": off.mean() if len(off) else np.nan,
                     "hit_on": (on > 0).mean() if len(on) else np.nan, "hit_off": (off > 0).mean() if len(off) else np.nan,
                     "excess": excess, "t": t, "h1": halves[0], "h2": halves[1], "passed": passed})
    return rows


def timing_backtest(spx, liq, signal_name):
    """持有 S&P 500 vs 只在訊號開啟時持有（其餘持現金=0%）。訊號延後 2 天才動作，不含交易成本。"""
    spx = spx[spx.index >= START]
    liq = liq.reindex(spx.index)
    sig = make_signals(liq)[signal_name].shift(2).fillna(False).astype(bool)
    ret = spx.pct_change().fillna(0.0)
    strat = ret.where(sig, 0.0)
    years = max((spx.index[-1] - spx.index[0]).days / 365.25, 1e-9)

    def stats(r):
        eq = (1 + r).cumprod()
        return {"cagr": eq.iloc[-1] ** (1 / years) - 1, "maxdd": float((1 - eq / eq.cummax()).max())}
    return {"hold": stats(ret), "timing": stats(strat), "exposure": float(sig.mean()),
            "switches": int((sig != sig.shift(1)).sum() - 1)}


def build_report(rows, liq, spx, date_str, units_ok, timing):
    n_years = (spx.index[-1] - spx[spx.index >= START].index[0]).days / 365.25
    L = [f"# 聯準會流動性檢驗 {date_str}", "",
         f"資料：FRED（免費）。S&P 500 指數自 {START} 起共 {n_years:.0f} 年。淨流動性 = Fed 總資產 − TGA − 隔夜逆回購。", "",
         "**通過標準（事先訂定）**：訊號開啟/關閉各 ≥ 40 個不重疊的 20 日區塊、開啟組未來 20 日報酬較高、"
         f"前後半期都較高、Welch t ≥ {T_REQUIRED}（同時測 5 個訊號，已提高門檻）。", "",
         "| 訊號 | 開啟 n | 關閉 n | 開啟平均 20 日報酬 | 關閉平均 20 日報酬 | 差距 | t 值 | 前半期差距 | 後半期差距 | 結果 |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        f = lambda x: "—" if pd.isna(x) else f"{x*100:+.2f}%"
        L.append(f"| {r['name']} | {r['n_on']} | {r['n_off']} | {f(r['mean_on'])} | {f(r['mean_off'])} | {f(r['excess'])} | "
                 f"{r['t']:.2f} | {f(r['h1'])} | {f(r['h2'])} | {'✅ 通過' if r['passed'] else '❌ 未通過'} |")
    win = [r for r in rows if r["passed"]]
    L += ["", "## 結論"]
    L += ([f"- 通過檢驗：{'、'.join(w['name'] for w in win)}。仍需用之後的新資料再確認。"] if win else
          ["- **沒有任何訊號通過檢驗**：沒有可靠證據顯示 Fed 流動性變化能預測 S&P 500 未來 20 日報酬。"])
    if timing:
        L += ["", f"## 擇時對照：「{timing['name']}」（只在訊號開啟時持有 S&P 500，其餘持現金，不含交易成本）",
              f"- 一直持有：年化 {timing['hold']['cagr']*100:.1f}%、最大回撤 {timing['hold']['maxdd']*100:.0f}%",
              f"- 依訊號進出：年化 {timing['timing']['cagr']*100:.1f}%、最大回撤 {timing['timing']['maxdd']*100:.0f}%、"
              f"持有時間 {timing['exposure']*100:.0f}%、進出 {timing['switches']} 次"]
    last = liq.dropna().iloc[-1]
    L += ["", "## 目前讀數（十億美元）",
          f"- Fed 總資產 {last['assets']:,.0f}｜TGA {last['tga']:,.0f}｜隔夜逆回購 {last['rrp']:,.0f}｜淨流動性 {last['net']:,.0f}",
          f"- 淨流動性近 13 週變化 {liq['net'].diff(63).iloc[-1]:+,.0f}",
          f"- 單位檢查：{'通過（淨流動性在合理範圍）' if units_ok else '⚠️ 淨流動性數值不在合理範圍，FRED 單位可能不同，請不要採信本報告'}"]
    L += ["", "## 注意事項",
          "- 只有約 15 年、少數幾次流動性循環（量化寬鬆、縮表、2023 年 TGA 與逆回購大變動），真正獨立的觀察很少，統計檢定力低。",
          "- 同一段時間大盤主要受企業獲利、利率與 AI 行情影響，流動性只是其中一個解釋，相關不等於因果。",
          "- 不含交易成本與稅，擇時對照只是示意。",
          "- 僅供研究學習，非投資建議。"]
    return "\n".join(L)


def main():
    session = us.us_session()
    spx = sc.fetch_index_close(session, "^GSPC", "max")
    if spx is None or len(spx) < 1000:
        print("❌ 無法取得 S&P 500 長期資料。")
        return
    walcl, tga, rrp = (fetch_fred(session, s) for s in ("WALCL", "WTREGEN", "RRPONTSYD"))
    print(f"FRED 讀取完成：WALCL {len(walcl)} 筆、WTREGEN {len(tga)} 筆、RRPONTSYD {len(rrp)} 筆")
    spx = spx[spx.index >= START]
    liq = build_liquidity(walcl, tga, rrp, spx.index)
    last_net = float(liq["net"].dropna().iloc[-1])
    units_ok = 1000 <= last_net <= 12000
    rows = evaluate(spx, liq)
    best = max(rows, key=lambda r: r["t"])
    timing = timing_backtest(spx, liq, best["name"]) | {"name": best["name"]}
    os.makedirs("reports_us", exist_ok=True)
    try:
        import regime
        regime.update_evidence(
            "fed_liquidity_welch", name=f"Fed 流動性 5 訊號中最強：{best['name']}（20 日區塊，S&P 500）",
            periods=best["n_on"] + best["n_off"], unit="區塊", mean=best["excess"], t=best["t"],
            passed=any(r["passed"] for r in rows), asof=datetime.now().strftime("%Y%m%d"),
            source=f"fed_liquidity.py（門檻 t≥{T_REQUIRED}）")
    except Exception as e:
        print(f"⚠️ 證據看板更新略過：{type(e).__name__}: {e}")
    path = os.path.join("reports_us", f"fed_liquidity_{datetime.now().strftime('%Y%m%d')}.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(build_report(rows, liq, spx, datetime.now().strftime("%Y%m%d"), units_ok, timing))
    for r in rows:
        print(f"{r['name']}: 差距 {r['excess']*100:+.2f}% t={r['t']:.2f} {'✅' if r['passed'] else '—'}")
    print(f"📁 {path}")


if __name__ == "__main__":
    main()
