"""us_data.py - 美股資料：S&P 500 成分股、日K（還原權息）、市場環境（S&P 500 指數 vs 200 日均線）"""
import io

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import stock_scanner as sc

CSV_URL = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv"
WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"

US_CONFIG = {
    **sc.CONFIG,
    "min_price": 5.0,
    "min_avg_vol_20d": 300000,       # 股數
    "max_avg_vol_20d": 10**10,
    "round_trip_cost": 0.001,        # 來回 0.1%：價差與滑價（美股無證交稅、多數券商免佣）
    "history_range": "5y",
    "report_dir": "reports_us",
}


def _norm(sym):
    return str(sym).strip().replace(".", "-")        # Yahoo 用 BRK-B，不是 BRK.B


def get_sp500_list(session):
    """回傳 [(ticker, name)]。先用 GitHub 上維護的 CSV，失敗再用維基百科。"""
    try:
        r = session.get(CSV_URL, headers=sc.HEADERS, timeout=20)
        if r.status_code == 200:
            df = pd.read_csv(io.StringIO(r.text))
            out = [(_norm(s), str(n).strip()) for s, n in zip(df["Symbol"], df["Name"])]
            if len(out) > 400:
                return out
    except Exception:
        pass
    try:
        r = session.get(WIKI_URL, headers=sc.HEADERS, timeout=20)
        df = pd.read_html(io.StringIO(r.text))[0]
        out = [(_norm(s), str(n).strip()) for s, n in zip(df["Symbol"], df["Security"])]
        if len(out) > 400:
            return out
    except Exception:
        pass
    return []


def fetch_us_kline(session, symbol, rng="5y"):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    try:
        res = session.get(url, headers=sc.HEADERS, timeout=12,
                          params={"range": rng, "interval": "1d", "events": "history"})
        if res.status_code != 200:
            return None
        result = res.json()["chart"]["result"][0]
        q = result["indicators"]["quote"][0]
        adj = (result["indicators"].get("adjclose") or [{}])[0].get("adjclose")
        df = pd.DataFrame(
            {"Open": q["open"], "High": q["high"], "Low": q["low"], "Close": q["close"], "Volume": q["volume"]},
            index=pd.to_datetime(result["timestamp"], unit="s").normalize())
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


def us_environment(session, rng="5y"):
    """市場多空：S&P 500 指數是否在 200 日均線之上（美股慣用的長期趨勢線）。"""
    env = {"bull_by_date": None, "spx": None, "is_bull": True}
    try:
        spx = sc.fetch_index_close(session, "^GSPC", rng)
        if spx is not None and len(spx) > 200:
            ma200 = spx.rolling(200).mean()
            env["bull_by_date"] = (spx > ma200).astype(float).where(ma200.notna())
            env["spx"] = spx
            env["is_bull"] = bool(spx.iloc[-1] > ma200.iloc[-1])
    except Exception as e:
        print(f"⚠️ S&P 500 指數載入略過: {e}")
    return env


# ==============================================================================
# 寬名單：全美股普通股 → 以最近 20 日成交金額取前 3000 檔
# ==============================================================================
US_WIDE_CONFIG = {
    **US_CONFIG,
    "round_trip_cost": 0.002,        # 寬名單含中小型股，價差較大，成本抓 0.2%（S&P 500 版為 0.1%）
    "wide_universe_size": 3000,
    "min_dollar_vol": 5_000_000,     # 20 日平均成交金額下限（美元）
    "max_workers": 8,                # 檔數多，降低併發避免被 Yahoo 限流
    "report_dir": "reports_us",
}

NASDAQ_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"
OTHER_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"
BAD_NAME_WORDS = ("warrant", " rights", " right ", "units", "preferred", "notes", "debenture",
                  "subordinated", "% ", " fund", " etn")


def us_session():
    """較有耐心的連線：遇到 429/5xx 會等待後重試。"""
    s = requests.Session()
    retry = Retry(total=5, backoff_factor=1.0, status_forcelist=[429, 500, 502, 503, 504])
    ad = HTTPAdapter(max_retries=retry, pool_connections=20, pool_maxsize=20)
    s.mount("https://", ad)
    s.mount("http://", ad)
    return s


def _ok_symbol(sym):
    if not sym or "$" in sym:
        return False
    if "-" in sym:
        base, suffix = sym.split("-", 1)
        if suffix not in ("A", "B", "C"):         # 只保留 A/B/C 股別（BRK-B）；排除權證/單位/特別股
            return False
        return base.isalpha() and 1 <= len(base) <= 5
    if not sym.isalpha() or len(sym) > 5:
        return False
    if len(sym) == 5 and sym[-1] in "WRU":         # 5 碼且結尾 W/R/U：權證、權利、單位
        return False
    return True


def parse_symbol_directory(text, kind):
    """解析 Nasdaq Trader 的 nasdaqlisted / otherlisted。只留一般普通股（排除 ETF、測試、權證、特別股…）。"""
    out = []
    for line in text.splitlines()[1:]:
        c = line.split("|")
        if len(c) < 7 or line.startswith("File Creation"):
            continue
        if kind == "nasdaq":
            sym, name, test, status, etf = c[0], c[1], c[3], c[4], c[6]
            if status.strip() != "N":
                continue
        else:
            sym, name, etf, test = c[0], c[1], c[4], c[6]
        if etf.strip() != "N" or test.strip() != "N":
            continue
        low = " " + name.lower() + " "
        if any(w in low for w in BAD_NAME_WORDS):
            continue
        sym = sym.strip().replace(".", "-").replace("/", "-")
        if _ok_symbol(sym):
            out.append((sym, name.strip()))
    return out


def get_us_universe(session):
    syms, seen = [], set()
    for url, kind in ((NASDAQ_URL, "nasdaq"), (OTHER_URL, "other")):
        try:
            r = session.get(url, headers=sc.HEADERS, timeout=30)
            if r.status_code == 200:
                for sym, name in parse_symbol_directory(r.text, kind):
                    if sym not in seen:
                        seen.add(sym)
                        syms.append((sym, name))
        except Exception:
            pass
    return syms


def select_liquid(raw, n, min_price, min_dollar_vol):
    """從已下載的資料中，依最近 20 日平均成交金額取前 n 檔（排除已下市/停止更新、低價、低流動性）。"""
    if not raw:
        return []
    latest = max(df.index[-1] for df in raw.values())
    rows = []
    for sym, df in raw.items():
        if len(df) < 250 or df.index[-1] < latest - pd.Timedelta(days=10):
            continue
        px = float(df["Close"].iloc[-1])
        dv = float((df["Close"] * df["Volume"]).iloc[-20:].mean())
        if px >= min_price and dv >= min_dollar_vol:
            rows.append((dv, sym))
    rows.sort(reverse=True)
    return [sym for _, sym in rows[:n]]
