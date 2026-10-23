"""us_data.py - 美股資料：S&P 500 成分股、日K（還原權息）、市場環境（S&P 500 指數 vs 200 日均線）"""
import io

import pandas as pd

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
