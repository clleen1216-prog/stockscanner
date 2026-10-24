"""
thirteenf.py - 13F「聰明錢加碼」是否預測股票未來一季報酬？（資料：SEC EDGAR 13F 季度資料集，免費）

做法（事先訂定，不看結果調整）：
  1. 每季取「兩季都有申報的機構」(排除新成立/停止申報的機構造成的假變化)，彙總每檔股票的持股變化：
       growth  = 持股股數成長率；  breadth = (加碼家數 − 減碼家數) / (加碼家數 + 減碼家數)
  2. 資料公開日 = 季底後 45 天（法定申報期限）；隔一個交易日收盤進場，持有 63 個交易日（約一季）
  3. 每季把股票依訊號分五等份，比較「最高 20%」相對「全體平均」的報酬 → 得到每季一個「超額報酬」
  4. 通過 = 至少 12 季、平均超額報酬 > 0、跨季 t >= 2.2、至少 60% 的季度為正、前半與後半期平均都 > 0
SEC 要求請求要帶可聯絡的 User-Agent：請在 GitHub 設定 SEC_USER_AGENT 變數（姓名 + email）。
"""
import io
import os
import re
import sys
import time
import zipfile
from datetime import datetime

import numpy as np
import pandas as pd

import analytics as an
import stock_scanner as sc
import us_data as us

PAGE_URL = "https://www.sec.gov/data-research/sec-markets-data/form-13f-data-sets"
HOLD = 63
LAG_DAYS = 45
MIN_QUARTERS = 12
T_REQUIRED = 2.2
MIN_COVERAGE = 0.5
MIN_HOLDERS = 20
STOP = {"INC", "CORP", "CORPORATION", "CO", "COMPANY", "LTD", "LIMITED", "PLC", "HOLDINGS", "HLDGS", "HLDG",
        "GROUP", "THE", "CLASS", "CL", "COM", "COMMON", "STOCK", "SHS", "ORD", "NEW", "DEL", "LP", "LLC", "SA",
        "NV", "AG", "INCORPORATED", "ADR", "SPONSORED", "CAP", "STK", "A", "B", "C"}
BAD_TITLE = ("PUT", "CALL", "NOTE", "PFD", "PREF", "WARRANT", "DEBENT", "BOND", "ETF", "UNIT", "RIGHT", "FUND", "TR UNIT")
MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]


# ---------------------------------------------------------------- SEC 資料集連結
def parse_dataset_links(html):
    urls = re.findall(r'href="([^"]+form13f[^"]*\.zip)"', html, re.I)
    out = []
    for u in dict.fromkeys(urls):
        out.append(u if u.startswith("http") else "https://www.sec.gov" + (u if u.startswith("/") else "/" + u))
    return out


def link_sort_key(url):
    f = url.lower().rsplit("/", 1)[-1]
    years = re.findall(r"20\d\d", f)
    y = int(max(years)) if years else 0
    q = re.search(r"q([1-4])", f)
    if q:
        m = int(q.group(1)) * 3
    else:
        ms = [MONTHS.index(x) + 1 for x in re.findall("|".join(MONTHS), f)]
        m = ms[-1] if ms else 0
    return (y, m)


# ---------------------------------------------------------------- 讀取一季資料
def _cols(df_header, wanted, where):
    up = {c.upper(): c for c in df_header}
    missing = [w for w in wanted if w not in up]
    if missing:
        raise ValueError(f"{where} 缺少欄位 {missing}；實際欄位：{list(df_header)[:20]}")
    return [up[w] for w in wanted]


def _open(z, name):
    for n in z.namelist():
        if n.upper().endswith(name):
            return z.open(n)
    raise ValueError(f"壓縮檔內找不到 {name}：{z.namelist()[:10]}")


def read_submissions(z):
    head = pd.read_csv(_open(z, "SUBMISSION.TSV"), sep="\t", nrows=0).columns
    cols = _cols(head, ["ACCESSION_NUMBER", "SUBMISSIONTYPE", "CIK", "PERIODOFREPORT"], "SUBMISSION.tsv")
    sub = pd.read_csv(_open(z, "SUBMISSION.TSV"), sep="\t", dtype=str, usecols=cols)
    sub.columns = ["acc", "type", "cik", "period"]
    sub = sub[sub["type"].str.upper() == "13F-HR"]                    # 只用原始申報
    sub["period"] = pd.to_datetime(sub["period"], errors="coerce", format="mixed")
    return sub.dropna(subset=["period"])


def iter_infotable(z, chunk=1_000_000):
    f = _open(z, "INFOTABLE.TSV")
    head = pd.read_csv(f, sep="\t", nrows=0).columns
    want = ["ACCESSION_NUMBER", "NAMEOFISSUER", "TITLEOFCLASS", "CUSIP", "SSHPRNAMT", "SSHPRNAMTTYPE", "PUTCALL"]
    cols = _cols(head, want, "INFOTABLE.tsv")
    f = _open(z, "INFOTABLE.TSV")
    for ch in pd.read_csv(f, sep="\t", dtype=str, usecols=cols, chunksize=chunk):
        ch.columns = ["acc", "name", "title", "cusip", "shares", "unit", "putcall"]
        ch = ch[(ch["unit"].fillna("").str.upper() == "SH") & ch["putcall"].isna()]
        t = ch["title"].fillna("").str.upper()
        ch = ch[~t.apply(lambda s: any(b in s for b in BAD_TITLE))]
        ch = ch.assign(shares=pd.to_numeric(ch["shares"], errors="coerce")).dropna(subset=["shares"])
        yield ch


def name_table(z):
    """最新一季的 (CUSIP, 發行人名稱, 持有機構數)，用來把 CUSIP 對到股票代號。"""
    parts = []
    for ch in iter_infotable(z):
        parts.append(ch.groupby(["cusip", "name"]).size().rename("holders").reset_index())
    t = pd.concat(parts).groupby(["cusip", "name"], as_index=False)["holders"].sum()
    return t


def load_quarter(z, cusips):
    """回傳 (期末日, DataFrame[cik, cusip, shares])；只保留 cusips 內的股票。"""
    sub = read_submissions(z)
    if sub.empty:
        raise ValueError("SUBMISSION.tsv 內沒有 13F-HR 申報")
    period = sub["period"].mode().iloc[0]
    acc2cik = sub[sub["period"] == period].drop_duplicates("acc").set_index("acc")["cik"]
    parts = []
    for ch in iter_infotable(z):
        ch = ch[ch["cusip"].isin(cusips) & ch["acc"].isin(acc2cik.index)]
        if len(ch):
            ch = ch.assign(cik=ch["acc"].map(acc2cik))
            parts.append(ch.groupby(["cik", "cusip"], as_index=False)["shares"].sum())
    if not parts:
        return period, pd.DataFrame(columns=["cik", "cusip", "shares"])
    h = pd.concat(parts).groupby(["cik", "cusip"], as_index=False)["shares"].sum()
    return pd.Timestamp(period), h


# ---------------------------------------------------------------- 名稱 → 代號
def name_key(name):
    s = re.sub(r"[^A-Z0-9 ]", " ", str(name).upper().replace("&", " AND "))
    return " ".join([t for t in s.split() if t not in STOP][:3])


def build_mapping(names, universe):
    """names: DataFrame[cusip,name,holders]；universe: [(ticker, name)]。只保留一對一、不含糊的配對。"""
    tk = {}
    for sym, nm in universe:
        tk.setdefault(name_key(nm), []).append(sym)
    names = names.assign(key=names["name"].map(name_key))
    best = names.sort_values("holders", ascending=False).drop_duplicates("key")   # 同名稱取最多機構持有的 CUSIP
    mapping = {}
    for _, r in best.iterrows():
        syms = tk.get(r["key"], [])
        if len(syms) == 1 and r["key"]:
            mapping[r["cusip"]] = syms[0]
    return mapping


# ---------------------------------------------------------------- 訊號與檢驗
def quarter_signals(prev, cur):
    F = set(prev["cik"]) & set(cur["cik"])
    if len(F) < 50:
        return None
    p = prev[prev["cik"].isin(F)].set_index(["cik", "cusip"])["shares"].rename("p")
    c = cur[cur["cik"].isin(F)].set_index(["cik", "cusip"])["shares"].rename("c")
    j = pd.concat([p, c], axis=1).fillna(0.0)
    d = j["c"] - j["p"]
    g = j.groupby(level="cusip")
    old, new = g["p"].sum(), g["c"].sum()
    inc, dec = (d > 0).groupby(level="cusip").sum(), (d < 0).groupby(level="cusip").sum()
    holders = (j["c"] > 0).groupby(level="cusip").sum()
    out = pd.DataFrame({"growth": (new - old) / old.where(old > 0),
                        "breadth": (inc - dec) / (inc + dec).where((inc + dec) > 0),
                        "holders": holders})
    return out[(out["holders"] >= MIN_HOLDERS) & old.reindex(out.index).gt(0)]


def forward_return(close, entry_date, hold=HOLD):
    i = close.index.searchsorted(entry_date)
    if i + hold >= len(close):
        return np.nan
    return float(close.iloc[i + hold] / close.iloc[i] - 1)


def evaluate(signals, mapping, closes, signal_names=("growth", "breadth")):
    """signals: {期末日: DataFrame}；closes: {代號: 收盤價序列}。回傳每個訊號、每季的超額報酬。"""
    res = {s: [] for s in signal_names}
    for period, sig in sorted(signals.items()):
        entry = pd.Timestamp(period) + pd.Timedelta(days=LAG_DAYS + 1)
        sig = sig.copy()
        sig["ticker"] = sig.index.map(mapping)
        sig = sig.dropna(subset=["ticker"]).drop_duplicates("ticker")
        sig["ret"] = sig["ticker"].map(lambda t: forward_return(closes[t], entry) if t in closes else np.nan)
        sig = sig.dropna(subset=["ret"])
        if len(sig) < 100:
            continue
        for s in signal_names:
            x = sig.dropna(subset=[s])
            if len(x) < 100:
                continue
            top = x[x[s] >= x[s].quantile(0.8)]
            res[s].append({"period": pd.Timestamp(period), "n": len(x),
                           "excess": float(top["ret"].mean() - x["ret"].mean())})
    return res


def summarize_signal(rows):
    if not rows:
        return {"quarters": 0, "mean": np.nan, "t": 0.0, "pos": np.nan, "h1": np.nan, "h2": np.nan, "passed": False}
    e = np.array([r["excess"] for r in rows])
    n = len(e)
    sd = e.std(ddof=1) if n > 1 else 0.0
    t = float(e.mean() / (sd / np.sqrt(n))) if sd > 0 else 0.0
    h = n // 2
    h1, h2 = (e[:h].mean(), e[h:].mean()) if h >= 3 else (np.nan, np.nan)
    passed = bool(n >= MIN_QUARTERS and e.mean() > 0 and t >= T_REQUIRED and (e > 0).mean() >= 0.6
                  and not np.isnan(h1) and h1 > 0 and h2 > 0)
    return {"quarters": n, "mean": float(e.mean()), "t": t, "pos": float((e > 0).mean()), "h1": h1, "h2": h2, "passed": passed}


def build_report(res, coverage, n_universe, n_matched, date_str, universe_kind):
    L = [f"# 13F 聰明錢加碼檢驗 {date_str}", "",
         f"名單：{'S&P 500 現有成分股' if universe_kind == 'sp500' else '美股流動性前段普通股'}，共 {n_universe} 檔，"
         f"成功對到 13F 代號 {n_matched} 檔（{coverage*100:.0f}%）。", "",
         f"**通過標準（事先訂定）**：至少 {MIN_QUARTERS} 季、平均超額報酬 > 0、跨季 t ≥ {T_REQUIRED}、"
         "至少 60% 的季度為正、前後半期平均都 > 0。超額報酬 = 訊號最高 20% 股票未來 63 個交易日報酬 − 全體平均。", "",
         "| 訊號 | 季數 | 平均每季超額報酬 | t 值 | 為正的季度比例 | 前半期 | 後半期 | 結果 |", "|---|---|---|---|---|---|---|---|"]
    names = {"growth": "機構持股成長率", "breadth": "加碼家數 − 減碼家數"}
    f = lambda x: "—" if pd.isna(x) else f"{x*100:+.2f}%"
    summ = {k: summarize_signal(v) for k, v in res.items()}
    for k, s in summ.items():
        pos_txt = "—" if pd.isna(s["pos"]) else "%.0f%%" % (s["pos"] * 100)
        verdict = "✅ 通過" if s["passed"] else "❌ 未通過"
        L.append(f"| {names.get(k, k)} | {s['quarters']} | {f(s['mean'])} | {s['t']:.2f} | "
                 f"{pos_txt} | {f(s['h1'])} | {f(s['h2'])} | {verdict} |")
    win = [names[k] for k, s in summ.items() if s["passed"]]
    L += ["", "## 結論",
          (f"- 通過檢驗：{'、'.join(win)}。仍需用之後的新資料再確認。" if win else
           "- **沒有任何訊號通過檢驗**：沒有可靠證據顯示「13F 機構加碼」能預測之後一季的相對報酬。")]
    for k, rows in res.items():
        if rows:
            L += ["", f"### {names.get(k, k)}：逐季超額報酬"] + \
                 [f"- {r['period']:%Y-%m-%d} 季（{r['n']} 檔）：{r['excess']*100:+.2f}%" for r in rows]
    L += ["", "## 注意事項",
          "- 季數很少（最多約 17 季），統計檢定力低；通過與否都不要過度解讀。",
          "- 13F 只含美股多頭持股、季底快照，公開時已延遲最多 45 天；本檢驗以季底後 45 天為資料公開日（偏保守，但部分機構會延遲申報）。",
          "- CUSIP 與股票代號是用「發行人名稱」比對（免費資料沒有直接對照表），不含糊的才保留；覆蓋率見上方。",
          "- 只回測現有成分股/現在流動性高的股票，存在倖存者偏差。",
          "- 僅供研究學習，非投資建議。"]
    return "\n".join(L)


# ---------------------------------------------------------------- 下載與主程式
def sec_headers():
    ua = os.environ.get("SEC_USER_AGENT", "").strip()
    if not ua:
        print("⚠️ 未設定 SEC_USER_AGENT（姓名 + email），SEC 可能拒絕請求。請見說明。")
        ua = "stock-research-script (set SEC_USER_AGENT)"
    return {"User-Agent": ua, "Accept-Encoding": "gzip, deflate"}


def download_zip(session, url, path):
    for attempt in range(3):
        r = session.get(url, headers=sec_headers(), timeout=300, stream=True)
        if r.status_code == 200:
            with open(path, "wb") as fh:
                for chunk in r.iter_content(1 << 20):
                    fh.write(chunk)
            return True
        print(f"  下載失敗 HTTP {r.status_code}：{url}")
        time.sleep(3 * (attempt + 1))
    return False


def main():
    kind = (sys.argv[1] if len(sys.argv) > 1 else os.environ.get("US_UNIVERSE", "sp500")).strip().lower()
    kind = kind if kind in ("sp500", "wide") else "sp500"
    n_quarters = int(os.environ.get("N_QUARTERS", "22"))
    session = us.us_session()

    cfg = dict(us.US_WIDE_CONFIG if kind == "wide" else us.US_CONFIG)
    universe = us.get_us_universe(session) if kind == "wide" else us.get_sp500_list(session)
    if not universe:
        print("❌ 無法取得股票清單。")
        return
    print(f"名單 {len(universe)} 檔，下載價格...")
    from us_research import download
    raw, _ = download(session, universe, cfg, "")
    keep = us.select_liquid(raw, cfg.get("wide_universe_size", 3000), cfg["min_price"],
                            cfg.get("min_dollar_vol", 5_000_000)) if kind == "wide" else [s for s, d in raw.items() if len(d) >= 250]
    closes = {s: raw[s]["Close"] for s in keep}
    uni = [(s, n) for s, n in universe if s in closes]
    print(f"價格可用 {len(closes)} 檔")

    r = session.get(PAGE_URL, headers=sec_headers(), timeout=60)
    links = sorted(parse_dataset_links(r.text), key=link_sort_key)[-n_quarters:]
    print(f"找到 13F 資料集 {len(links)} 個：{[l.rsplit('/', 1)[-1] for l in links]}")
    if not links:
        print("❌ 在 SEC 頁面找不到 13F 資料集連結（頁面格式可能已改變，或請求被拒絕）。")
        return

    os.makedirs("tmp13f", exist_ok=True)
    last_path = os.path.join("tmp13f", "latest.zip")
    if not download_zip(session, links[-1], last_path):
        return
    with zipfile.ZipFile(last_path) as z:
        names = name_table(z)
    mapping = build_mapping(names, uni)
    coverage = len(set(mapping.values())) / max(len(uni), 1)
    print(f"CUSIP 對照：{len(mapping)} 個 CUSIP → {len(set(mapping.values()))} 檔股票（覆蓋率 {coverage*100:.0f}%）")
    if coverage < MIN_COVERAGE:
        print("❌ 覆蓋率低於 50%，結果不可靠，停止。")
        return
    cusips = set(mapping)

    signals, prev = {}, None
    for i, url in enumerate(links, 1):
        path = os.path.join("tmp13f", f"q{i}.zip")
        if i == len(links):
            path = last_path
        elif not download_zip(session, url, path):
            continue
        try:
            with zipfile.ZipFile(path) as z:
                period, holdings = load_quarter(z, cusips)
        except Exception as e:
            print(f"  第 {i} 個檔案讀取失敗：{e}")
            continue
        finally:
            if path != last_path and os.path.exists(path):
                os.remove(path)
        print(f"  {period:%Y-%m-%d}：{holdings['cik'].nunique()} 家機構、{len(holdings)} 筆持股")
        if prev is not None and prev[0] < period:
            s = quarter_signals(prev[1], holdings)
            if s is not None:
                signals[period] = s
        prev = (period, holdings)
    res = evaluate(signals, mapping, closes)
    date_str = datetime.now().strftime("%Y%m%d")
    os.makedirs("reports_us", exist_ok=True)
    out = os.path.join("reports_us", f"thirteenf_{kind}_{date_str}.md")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(build_report(res, coverage, len(uni), len(set(mapping.values())), date_str, kind))
    print(f"📁 {out}")


if __name__ == "__main__":
    main()
