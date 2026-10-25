"""
gate.py - the pre-registered decision gate. Reads the ledger, writes paper/STATUS.md and paper/STATUS.json.

Rules (fixed before any trade closed; PLAN.md has the same text):
  G1 opens when ALL of: today >= 2027-04-22, >= 100 closed trades in the capped sleeve, >= 40 distinct signal dates.
  GRADUATE needs every check to pass; mean <= 0 -> RETIRE; any other failure -> CONTINUE once (to 2027-10-22),
  then GRADUATE or RETIRE. Not enough evidence by 2027-10-22 -> RETIRE. A final answer is stored and never
  recomputed, so a later fluke cannot flip it.
"""
import json
import math
import os
from datetime import datetime, timezone

import numpy as np
import pandas as pd

import portfolio_sim as ps

LEDGER = os.path.join("paper", "ledger.csv")
BASELINE = os.path.join("paper", "random_baseline.csv")
STATE = os.path.join("paper", "gate_state.json")
STATUS_MD = os.path.join("paper", "STATUS.md")
STATUS_JSON = os.path.join("paper", "STATUS.json")

G1_DATE = pd.Timestamp("2027-04-22")
FINAL_DATE = pd.Timestamp("2027-10-22")
MIN_CLOSED = 100
MIN_DATES = 40
T_REQUIRED = 1.65
MIN_BULL_TRADES = 20
MIN_BASELINE_COVERAGE = 0.9     # share of signal dates the random-entry baseline must cover


def clustered_t(values, clusters):
    """t-statistic of the mean with standard errors clustered by signal date (trades on one day move together)."""
    x = np.asarray(values, dtype=float)
    n = len(x)
    cl = pd.Series(clusters).astype(str).values
    g = len(set(cl))
    if n < 3 or g < 2:
        return 0.0
    dev = x - x.mean()
    sums = pd.Series(dev).groupby(cl).sum().values
    var = (g / (g - 1)) * float((sums ** 2).sum()) / n ** 2
    return float(x.mean() / math.sqrt(var)) if var > 0 else 0.0


def baseline_for(sel_closed, baseline_df):
    """Mean R of random entries over the same signal dates, and the share of dates covered."""
    dates = sorted(set(sel_closed["signal_date"].astype(str)))
    if baseline_df is None or len(baseline_df) == 0 or not dates:
        return None, 0.0
    b = baseline_df.copy()
    b["date"] = b["date"].astype(str)
    b = b[b["date"].isin(dates)]
    if b.empty or b["n"].sum() == 0:
        return None, 0.0
    return float((b["mean_R"] * b["n"]).sum() / b["n"].sum()), len(b) / len(dates)


def evaluate(sel, baseline_df):
    """All numbers and pass/fail checks for the closed trades of the capped sleeve."""
    c = ps.closed_only(sel)
    n = len(c)
    out = {"n_closed": n, "n_open": int((sel["status"] == "open").sum()) if len(sel) else 0,
           "n_dates": int(c["signal_date"].nunique()) if n else 0}
    out["mean_R"] = float(c["R"].mean()) if n else 0.0
    out["win_rate"] = float((c["ret"] > 0).mean()) if n else 0.0
    out["t_clustered"] = clustered_t(c["R"], c["signal_date"]) if n else 0.0
    ex = (c["ret"] - c["bench_ret"]).dropna()
    out["excess_vs_taiex"] = float(ex.mean()) if len(ex) else None
    out["bench_n"] = int(len(ex))
    base, cov = baseline_for(c, baseline_df)
    out["baseline_R"], out["baseline_coverage"] = base, cov
    bull = c[c["bull"].astype(str).str.lower().isin(["true", "1", "1.0"])]
    out["bull_n"] = int(len(bull))
    out["bull_mean_R"] = float(bull["R"].mean()) if len(bull) else None
    checks = [
        ("Average result per trade above 0R", out["mean_R"] > 0, f"{out['mean_R']:+.3f}R"),
        (f"Clustered t at least {T_REQUIRED}", out["t_clustered"] >= T_REQUIRED, f"t = {out['t_clustered']:.2f}"),
        ("Beats the TAIEX over the same holding windows",
         out["excess_vs_taiex"] is not None and out["excess_vs_taiex"] > 0,
         "n/a" if out["excess_vs_taiex"] is None else f"{out['excess_vs_taiex'] * 100:+.2f}% per trade"),
        ("Beats random entry with the same exit rules",
         base is not None and cov >= MIN_BASELINE_COVERAGE and out["mean_R"] > base,
         "baseline missing" if base is None else f"{out['mean_R']:+.3f}R vs {base:+.3f}R (coverage {cov * 100:.0f}%)"),
        (f"At least {MIN_BULL_TRADES} bull-regime trades with average above 0R",
         out["bull_n"] >= MIN_BULL_TRADES and out["bull_mean_R"] is not None and out["bull_mean_R"] > 0,
         f"{out['bull_n']} trades" + ("" if out["bull_mean_R"] is None else f", {out['bull_mean_R']:+.3f}R")),
    ]
    out["checks"] = [{"name": a, "pass": bool(b), "value": v} for a, b, v in checks]
    out["all_pass"] = all(x["pass"] for x in out["checks"])
    return out


def decide(today, ev, prior=None):
    """Pure state machine. Returns (state, reason, final)."""
    today = pd.Timestamp(today)
    if prior and prior.get("final"):
        return prior["final"], f"decided on {prior.get('decided')}: stored, not recomputed", True
    ready = today >= G1_DATE and ev["n_closed"] >= MIN_CLOSED and ev["n_dates"] >= MIN_DATES
    if not ready:
        if today >= FINAL_DATE:
            return "RETIRE", "month 12 reached without enough closed trades or signal dates", True
        return "COLLECTING", "gate G1 not open yet", False
    if ev["baseline_R"] is None or ev["baseline_coverage"] < MIN_BASELINE_COVERAGE:
        if today >= FINAL_DATE:
            return "RETIRE", "month 12 reached and the random-entry comparison could not be built", True
        return "COLLECTING", "waiting for the monthly random-entry baseline to cover these dates", False
    if ev["all_pass"]:
        return "GRADUATE", "every check passed", True
    if ev["mean_R"] <= 0:
        return "RETIRE", "average result per trade is not above 0R", True
    if today < FINAL_DATE:
        return "CONTINUE", "positive but not every check passed: one extension to 2027-10-22", False
    return "RETIRE", "month 12 reached and not every check passed", True


def load_state():
    if os.path.exists(STATE):
        with open(STATE, encoding="utf-8") as fh:
            return json.load(fh)
    return {}


def build_status(today, ev, state, reason, sel, pace):
    L = ["# Gate status", "",
         f"**State: {state}** ({reason})", "",
         f"As of {pd.Timestamp(today):%Y-%m-%d}. Gate G1 opens on or after {G1_DATE:%Y-%m-%d} with at least "
         f"{MIN_CLOSED} closed trades and {MIN_DATES} signal dates. Paper trading only.", "",
         "## Progress",
         f"- Closed trades in the capped sleeve: **{ev['n_closed']} / {MIN_CLOSED}**",
         f"- Distinct signal dates: **{ev['n_dates']} / {MIN_DATES}**",
         f"- Open trades: {ev['n_open']}"]
    if pace:
        left = max(MIN_CLOSED - ev["n_closed"], 0)
        L.append(f"- Pace: about {pace:.2f} trades finish per trading day with {ps.CAP} slots, "
                 f"so roughly {math.ceil(left / pace) if left else 0} more trading days to {MIN_CLOSED} closed trades")
    L += ["", "## Checks (what GRADUATE needs)", "| Check | Result | Value |", "|---|---|---|"]
    for k in ev["checks"]:
        L.append(f"| {k['name']} | {'pass' if k['pass'] else 'not yet' if state in ('COLLECTING',) else 'fail'} | {k['value']} |")
    L += ["", "Until the gate opens these checks are informational; the early numbers swing a lot on few trades.",
          "", "## Sleeve rules (fixed)",
          f"- V8, V10 and V11 combined; the same stock and signal day counts once",
          f"- At most {ps.CAP} open positions; the most liquid names (20-day turnover) fill free slots first",
          "- Costs: 0.585% round trip plus 0.1% slippage; a gap-up open of 9% or more is treated as unfillable"]
    return "\n".join(L) + "\n"


def main(today=None):
    today = pd.Timestamp(today) if today is not None else pd.Timestamp(datetime.now(timezone.utc).date())
    ledger = (pd.read_csv(LEDGER, encoding="utf-8-sig", dtype={"code": str})
              if os.path.exists(LEDGER) else pd.DataFrame(columns=["strategy", "status", "code", "signal_date"]))
    baseline = pd.read_csv(BASELINE) if os.path.exists(BASELINE) else None
    sel = ps.select_trades(ledger)
    ev = evaluate(sel, baseline)
    prior = load_state()
    state, reason, final = decide(today, ev, prior)
    if final and not prior.get("final"):
        with open(STATE, "w", encoding="utf-8") as fh:
            json.dump({"final": state, "decided": f"{today:%Y-%m-%d}", "reason": reason}, fh, indent=1)
    os.makedirs("paper", exist_ok=True)
    with open(STATUS_MD, "w", encoding="utf-8") as fh:
        fh.write(build_status(today, ev, state, reason, sel, ps.throughput(sel)))
    with open(STATUS_JSON, "w", encoding="utf-8") as fh:
        json.dump({"state": state, "reason": reason, "asof": f"{today:%Y-%m-%d}", **{
            k: ev[k] for k in ("n_closed", "n_open", "n_dates", "mean_R", "t_clustered")}}, fh, indent=1)
    print(f"Gate state: {state} ({reason}); closed {ev['n_closed']}/{MIN_CLOSED}")


if __name__ == "__main__":
    main()
