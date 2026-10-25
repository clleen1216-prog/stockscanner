# Taiwan Stock Scanner v3 (paper-trading research pipeline)

**Status (v3, Phase 0 done):** the original v1 scanner was measured at -0.22R against random entry, so it no longer drives anything. The repo now runs one daily job that paper-trades three Taiwan strategies (V8, V10, V11, with V6 as a control) and builds a short digest. Nothing here trades real money. Rules for when a strategy may earn real money are in [PLAN.md](PLAN.md).

## What runs by itself
| When | Workflow | What it does |
|---|---|---|
| Weekdays 17:30 Taipei | `daily.yml` | updates `paper/ledger.csv`, writes `paper/PAPER_REPORT.md` and `reports/DIGEST.md`, commits once |
| Sundays 10:00 Taipei | `heartbeat.yml` | checks the pipeline is fresh and healthy, opens a `pipeline-failure` issue if not, commits a timestamp |
| Manual only | `research.yml`, `us_research.yml`, `thirteenf.yml`, `fed_liquidity.yml`, `legacy_scan.yml` | finished experiments, kept reproducible |

If something breaks you get a GitHub issue labelled `pipeline-failure` (turn on email notifications for issues). Otherwise do nothing.

## Read this
- `reports/DIGEST.md`: market state, pipeline health, today's simulated signals.
- `paper/PAPER_REPORT.md`: full paper-trading statistics.

## Tests
`python -m unittest discover -s tests -v` (offline, no network). Also runs on GitHub via the Tests workflow.

---

# Original v1 documentation (kept for reference)

# Taiwan Stock SOP Scanner

A Python scanner for Taiwan-listed (TWSE) and OTC (TPEx) stocks. It looks for stocks that are building a base: tangled moving averages, shrinking volume, and a possible breakout, then checks the market and institutional buying before suggesting an entry.

## What it checks

1. **Market environment**: TAIEX vs its 60-day MA, plus the overnight S&P 500 move.
2. **Technical setup**: MA5/10/20/60 spread under 5%, price not near the 1-year high, volume contraction.
3. **Entry triggers**: volume surge, 20-day high breakout, strong candle body (2 of 3 needed).
4. **Chips**: foreign investor and investment trust net buy/sell.
5. **Grades**: A+ (strong), B (small trial), B- (wait, overnight risk), C (market weak), Watch.

## Run it

```bash
pip install -r requirements.txt
python stock_scanner.py
```

Reports are saved to `reports/smart_stock_report_YYYYMMDD.csv`.

## Run it automatically on GitHub

In v3 the v1 scan is manual only (`legacy_scan.yml`). The daily schedule is `daily.yml`.

## Settings

Edit the `CONFIG` block at the top of `stock_scanner.py` (minimum price, volume limits, MA spread, etc.).

## Disclaimer

For learning and research only. This is not investment advice. Data comes from free public sources and may be delayed or incomplete.

## Macro risk layer: Fed liquidity + VIX (`regime.py`)

Added after the 2026-10-24 research. It follows what the tests showed, not what looked appealing:

| Piece | How it is used | Why |
|---|---|---|
| Fed net liquidity (assets − TGA − reverse repo), 13-week change | **Shrinks** position size ×0.75 when contracting. Never enlarges, never changes grades or win-rate estimates. | Pointed the right way in S&P 500, Nasdaq and TAIEX tests but did not pass the bar (t ≈ 1.6 vs 2.2). |
| VIX | Position ×0.75 at 20–30, ×0.5 above 30. Never enlarges. | Common risk guideline, not a tested return forecast. |
| 13F institutional adds (US only) | **Information only**: evidence board plus `reports_us/thirteenf_latest_*.csv`. Not in any score or position. | Both signals failed (t 0.43 / 0.51). The Taiwan scanner has no 13F data. |

Combined multiplier is at most 1.0 (worst case ×0.375). The rules are fixed; do not tune them to history.

### Proving it on new data
- `paper_trade.py` stores one snapshot about every 28 days in `paper/macro_log.csv` (Fed state + S&P 500 + TAIEX close) and judges the fixed 13-week rule after 12 periods with the same bar as the other tests (≥12 periods, mean > 0, t ≥ 2.2, ≥60% positive, both halves > 0).
- Every new paper-trade signal also records the Fed state (`fed_expanding`, `vix_close` in `paper/ledger.csv`), so `PAPER_REPORT.md` shows whether trades opened in contracting liquidity really did worse.
- `reports_us/evidence.json` is the evidence board shown in the daily report. `thirteenf.py` and `fed_liquidity.py` overwrite their rows with real results each time they run; until then, rows come from the manual 2026-10-24 tests.

### Tests
`python -m unittest discover -s tests -v` (offline, uses fake data). Also runs on GitHub via the Tests workflow.

### Honest status
The daily scan's own report currently says the base Taiwan strategy is significantly worse than random entry, so no candidate reaches grade A. The macro layer only reduces risk on whatever the scanner shows; it does not turn that strategy into an edge.
