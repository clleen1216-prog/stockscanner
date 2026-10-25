"""
portfolio_sim.py - the combined, capped satellite portfolio that gate.py judges.

V8, V10 and V11 fire on overlapping stocks, so they are not three independent proofs. And a person cannot
hand-trade five new names a day. So the thing that gets proven is ONE sleeve:
  * the same stock signalled on the same day by several strategies counts once,
  * at most CAP positions are open at any time,
  * when more signals arrive than free slots, the most liquid stocks (highest 20-day turnover) are taken first.
These rules were fixed before any trade closed. Do not tune them.
"""
import pandas as pd

CAP = 10
COMBINED = ("V8", "V10", "V11")


def select_trades(ledger, cap=CAP, strategies=COMBINED):
    """Return the trades the capped sleeve would have taken (open and closed), one row per stock-signal."""
    cols = list(ledger.columns) + ["strategies"]
    if len(ledger) == 0:
        return pd.DataFrame(columns=cols)
    g = ledger[ledger["strategy"].isin(strategies) & ledger["status"].isin(["open", "closed"])].copy()
    if g.empty:
        return pd.DataFrame(columns=cols)
    g["entry_date"] = pd.to_datetime(g["entry_date"])
    g["exit_date"] = pd.to_datetime(g["exit_date"])
    g["turnover20"] = pd.to_numeric(g["turnover20"] if "turnover20" in g else pd.Series(index=g.index, dtype=float),
                                    errors="coerce")
    g["code"] = g["code"].astype(str)
    key = ["code", "signal_date"]
    g["strategies"] = g.groupby(key)["strategy"].transform(lambda s: "+".join(sorted(set(s))))
    g = g.sort_values(["strategy"]).drop_duplicates(key, keep="first")
    g["_rank"] = -g["turnover20"].fillna(-1.0)          # missing turnover ranks last
    g = g.sort_values(["entry_date", "_rank", "code"])
    taken, active = [], []
    for day, grp in g.groupby("entry_date", sort=True):
        active = [e for e in active if e >= day]          # a trade still holds its slot on its exit day
        free = cap - len(active)
        for idx, row in grp.iterrows():
            if free <= 0:
                break
            taken.append(idx)
            active.append(row["exit_date"] if pd.notna(row["exit_date"]) else pd.Timestamp.max)
            free -= 1
    return g.loc[taken].drop(columns="_rank")


def closed_only(sel):
    c = sel[sel["status"] == "closed"].copy()
    for col in ("R", "ret", "bars", "bench_ret"):
        c[col] = pd.to_numeric(c[col], errors="coerce")
    return c


def throughput(sel, cap=CAP):
    """Rough pace: with CAP slots and an average holding of B trading days, about CAP / B trades finish a day."""
    c = closed_only(sel)
    if len(c) < 5 or c["bars"].mean() <= 0:
        return None
    return cap / float(c["bars"].mean())
