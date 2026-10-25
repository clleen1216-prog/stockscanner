"""
digest.py - one short daily page: market state, today's paper signals, pipeline health.

Replaces the v1 scanner's daily grades. That scanner measured -0.22R (t = -6.22) against random entry, so it no
longer drives any decision. This file only READS paper/last_run.json and paper/ledger.csv (no network), so it
is fast and cannot fail because of a data source.
Output: reports/DIGEST.md (overwritten each run; git history keeps the old ones).
"""
import json
import os

import pandas as pd

LAST_RUN = os.path.join("paper", "last_run.json")
LEDGER = os.path.join("paper", "ledger.csv")
STATUS = os.path.join("paper", "STATUS.json")
OUT = os.path.join("reports", "DIGEST.md")
STRATS = ["V6", "V8", "V10", "V11"]
NEEDED = 100          # closed trades per strategy before the first verdict (see gate rules)


def build_digest(run, ledger, status=None):
    L = ["# Daily digest", "",
         "Paper trading only. No real money. Research, not investment advice.", ""]
    if not run:
        return "\n".join(L + ["**No run record found.** The daily job has not completed yet.", ""])
    L += [f"Last run finished: {run['finished_utc']} (UTC)", "", "## Market state",
          f"- TAIEX {run['twii_close']:.0f} vs 60-day average {run['twii_ma60']:.0f}: "
          f"**{'above (bull)' if run['twii_above_ma60'] else 'below (weak)'}**",
          f"- S&P 500 overnight: {run['sp500_overnight_pct']:+.2f}%"]
    mult = run.get("size_mult")
    L.append(f"- Macro position multiplier: x{mult} (only ever shrinks size)" if mult is not None
             else "- Macro position multiplier: unavailable, no adjustment")
    L += ["", "## Pipeline health"]
    fetched, listed = run.get("stocks_fetched", 0), run.get("stocks_listed", 0)
    L.append(f"- Price data: {fetched} of {listed} stocks usable")
    L.append("- Fed liquidity feed: OK" if run.get("fed_ok")
             else f"- Fed liquidity feed: **NOT WORKING** ({run.get('fed_error') or 'no reason recorded'})")
    L += ["", "## Paper strategies",
          f"A strategy needs {NEEDED} closed trades before any verdict. The decision rules are in PLAN.md; the monthly check writes paper/STATUS.md.", "",
          "| Strategy | Signals | Open | Closed | Progress |", "|---|---|---|---|---|"]
    for k in STRATS:
        g = ledger[ledger["strategy"] == k] if len(ledger) else ledger
        n_closed = int((g["status"] == "closed").sum()) if len(g) else 0
        n_open = int(g["status"].isin(["open", "pending"]).sum()) if len(g) else 0
        L.append(f"| {k} | {len(g)} | {n_open} | {n_closed} | {n_closed}/{NEEDED} |")
    if status:
        L += ["", "## Gate", f"- State: **{status['state']}** as of {status['asof']} ({status['reason']})",
              f"- Capped sleeve: {status['n_closed']} closed trades, {status['n_dates']} signal dates"]
    sigs = run.get("new_signals", [])
    L += ["", f"## New signals today ({len(sigs)}), simulated entry at next open"]
    if sigs:
        for k in STRATS:
            names = ", ".join(f"{s['code']} {s['name']}" for s in sigs if s["strategy"] == k)
            if names:
                L.append(f"- {k}: {names}")
        both = {}
        for s in sigs:
            both.setdefault(s["code"], set()).add(s["strategy"])
        dup = [c for c, v in both.items() if len(v) > 1]
        if dup:
            L.append(f"- Picked by more than one strategy (not independent evidence): {', '.join(sorted(dup))}")
    else:
        L.append("- None")
    L += ["", "Full detail: paper/PAPER_REPORT.md"]
    return "\n".join(L) + "\n"


def main():
    run = json.load(open(LAST_RUN, encoding="utf-8")) if os.path.exists(LAST_RUN) else None
    ledger = (pd.read_csv(LEDGER, encoding="utf-8-sig", dtype={"code": str})
              if os.path.exists(LEDGER) else pd.DataFrame(columns=["strategy", "status"]))
    status = json.load(open(STATUS, encoding="utf-8")) if os.path.exists(STATUS) else None
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(build_digest(run, ledger, status))
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
