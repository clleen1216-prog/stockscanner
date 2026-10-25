"""
heartbeat.py - weekly dead-man's switch. Exits 1 (so the workflow opens an issue) when the pipeline looks stale
or the ledger looks corrupt. Also touches paper/HEARTBEAT.txt so the repository always has fresh activity
(GitHub disables scheduled workflows in public repos after 60 days without activity).
"""
import json
import os
import sys
from datetime import datetime, timezone

import pandas as pd

LAST_RUN = os.path.join("paper", "last_run.json")
LEDGER = os.path.join("paper", "ledger.csv")
BEAT = os.path.join("paper", "HEARTBEAT.txt")
MAX_AGE_DAYS = 4          # a Sunday check must still see Friday's run (Fri 09:30 UTC to Sun is about 2.5 days)
MAX_PENDING_DAYS = 6      # a pending trade enters at the next open; older than this means resolution is stuck
MIN_FETCH_RATIO = 0.5     # fewer usable stocks than this means a data source broke


def check(last_run, ledger, now):
    """Return a list of human-readable problems (empty list = healthy)."""
    problems = []
    if not last_run:
        return ["paper/last_run.json is missing: the daily job has never completed."]
    finished = datetime.strptime(last_run["finished_utc"], "%Y-%m-%dT%H:%M:%SZ")
    age = (now - finished).total_seconds() / 86400
    if age > MAX_AGE_DAYS:
        problems.append(f"Last successful daily run was {age:.1f} days ago (limit {MAX_AGE_DAYS}).")
    listed, fetched = last_run.get("stocks_listed", 0), last_run.get("stocks_fetched", 0)
    if listed == 0 or fetched / listed < MIN_FETCH_RATIO:
        problems.append(f"Only {fetched} of {listed} stocks had usable price data: a data source may have changed.")
    if not last_run.get("fed_ok"):
        problems.append(f"Fed liquidity feed is not working: {last_run.get('fed_error') or 'no reason recorded'}")
    if len(ledger):
        key = ["strategy", "code", "signal_date"]
        dup = int(ledger.duplicated(subset=key).sum())
        if dup:
            problems.append(f"Ledger has {dup} duplicated (strategy, code, signal_date) rows.")
        pend = ledger[ledger["status"] == "pending"]
        if len(pend):
            oldest = (pd.Timestamp(now.date()) - pd.to_datetime(pend["signal_date"]).min()).days
            if oldest > MAX_PENDING_DAYS:
                problems.append(f"A trade has been pending for {oldest} days: resolution looks stuck.")
    return problems


def main():
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    run = json.load(open(LAST_RUN, encoding="utf-8")) if os.path.exists(LAST_RUN) else None
    ledger = (pd.read_csv(LEDGER, encoding="utf-8-sig", dtype={"code": str})
              if os.path.exists(LEDGER) else pd.DataFrame())
    problems = check(run, ledger, now)
    os.makedirs(os.path.dirname(BEAT), exist_ok=True)
    with open(BEAT, "w", encoding="utf-8") as fh:
        fh.write(f"{now:%Y-%m-%dT%H:%M:%SZ} {'OK' if not problems else 'PROBLEMS'}\n")
    if problems:
        print("HEARTBEAT FAILED:\n- " + "\n- ".join(problems))
        sys.exit(1)
    print("Heartbeat OK.")


if __name__ == "__main__":
    main()
