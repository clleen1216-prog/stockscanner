"""
random_baseline.py - "would random entries have done as well?" for the capped sleeve, on the SAME dates.

For every signal date that has a closed trade in the capped sleeve, take every liquid stock that day, pretend it was
bought at the next open, and run it through exactly the same fill rules, costs and exit rule (paper_trade.resolve).
The average result is the random-entry benchmark that gate.py compares against. Monthly job: it downloads prices.
Output: paper/random_baseline.csv with columns date, n, mean_R.
"""
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import pandas as pd

import analytics as an
import paper_trade as pt
import portfolio_sim as ps
import stock_scanner as sc

OUT = os.path.join("paper", "random_baseline.csv")


def random_rows(dfs, dates, cfg, base=None):
    """dfs: {code: price DataFrame}. dates: signal dates (strings). Returns a DataFrame date, n, mean_R."""
    base = base or sc.CONFIG
    want = [pd.Timestamp(d) for d in dates]
    acc = {d: [] for d in want}
    for code, df in dfs.items():
        d = an.add_indicators(df)
        vol20 = d["Volume"].rolling(20).mean()
        locs = d.index.get_indexer(want)
        for day, i in zip(want, locs):
            if i < 0 or not np.isfinite(d["ATR14"].iloc[i]):
                continue
            liquid = (d["Close"].iloc[i] >= base["min_price"]
                      and base["min_avg_vol_20d"] <= vol20.iloc[i] <= base["max_avg_vol_20d"])
            if not liquid:
                continue
            r = pt.resolve(d, int(i), cfg)
            if r.get("status") == "closed":          # unfinished and unfillable trades are excluded, as in the sleeve
                acc[day].append(float(r["R"]))
    rows = [{"date": day.strftime("%Y-%m-%d"), "n": len(v), "mean_R": float(np.mean(v))}
            for day, v in acc.items() if v]
    return pd.DataFrame(rows, columns=["date", "n", "mean_R"]).sort_values("date").reset_index(drop=True)


def main():
    sc.CONFIG["history_range"] = "2y"
    ledger = pd.read_csv(pt.LEDGER, encoding="utf-8-sig", dtype={"code": str})
    closed = ps.closed_only(ps.select_trades(ledger))
    dates = sorted(set(closed["signal_date"].astype(str)))
    if not dates:
        print("No closed sleeve trades yet; nothing to compare against.")
        return
    cfg = pt.strategy_cfgs()["V8"]            # V8, V10 and V11 share one exit rule
    session = sc.create_session()
    stock_list = sc.get_taiwan_stock_list()
    dfs = {}
    with ThreadPoolExecutor(max_workers=sc.CONFIG["max_workers"]) as ex:
        futs = {ex.submit(sc.fetch_stock_kline, session, c, m): c for c, _, m in stock_list}
        for fut in as_completed(futs):
            df = fut.result()
            if df is not None and len(df) >= 250:
                dfs[futs[fut]] = df
    out = random_rows(dfs, dates, cfg)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    out.to_csv(OUT, index=False)
    print(f"Random-entry baseline for {len(out)} of {len(dates)} signal dates from {len(dfs)} stocks.")


if __name__ == "__main__":
    main()
