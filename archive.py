"""
archive.py - point-in-time data archive.

Every report so far tests only stocks that are listed and liquid TODAY (survivorship bias). The only fix is data
collected going forward: one compressed file per trading day with every stock's last bar, plus the full list of
listed codes that day (including stocks with no usable price). In a year this is an unbiased test set.

Layout: data/daily/YYYY-MM-DD.csv.gz   (about 60 KB a day, roughly 15 MB a year; my estimate)
"""
import os

import pandas as pd

OUT_DIR = os.path.join("data", "daily")
COLUMNS = ["date", "code", "name", "market", "open", "high", "low", "close", "volume", "has_price"]


def bar_row(code, name, market, df):
    """Last bar of one stock as a dict."""
    last = df.iloc[-1]
    return {"date": df.index[-1].strftime("%Y-%m-%d"), "code": str(code), "name": str(name).strip(),
            "market": market, "open": round(float(last["Open"]), 4), "high": round(float(last["High"]), 4),
            "low": round(float(last["Low"]), 4), "close": round(float(last["Close"]), 4),
            "volume": int(last["Volume"]), "has_price": True}


def save_daily(bars, stock_list, out_dir=OUT_DIR):
    """Write today's file once. Returns the path written, or None when there is nothing new to write.
    The file's date is the most common bar date, so a late or holiday run does not mislabel the day."""
    if not bars:
        return None
    df = pd.DataFrame(bars)
    day = df["date"].mode().iloc[0]
    path = os.path.join(out_dir, f"{day}.csv.gz")
    if os.path.exists(path):
        return None                                   # already archived: running twice changes nothing
    df = df[df["date"] == day]
    have = set(df["code"])
    missing = [{"date": day, "code": str(c), "name": str(n).strip(), "market": m, "open": None, "high": None,
                "low": None, "close": None, "volume": None, "has_price": False}
               for c, n, m in stock_list if str(c) not in have]
    out = pd.concat([df, pd.DataFrame(missing, columns=COLUMNS)], ignore_index=True)[COLUMNS]
    out = out.sort_values("code").reset_index(drop=True)
    os.makedirs(out_dir, exist_ok=True)
    out.to_csv(path, index=False, compression="gzip")
    return path
