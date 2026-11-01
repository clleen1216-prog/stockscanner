# Gate status

**State: COLLECTING** (gate G1 not open yet)

As of 2026-11-01. Gate G1 opens on or after 2027-04-22 with at least 100 closed trades and 40 signal dates. Paper trading only.

## Progress
- Closed trades in the capped sleeve: **2 / 100**
- Distinct signal dates: **1 / 40**
- Open trades: 10

## Checks (what GRADUATE needs)
| Check | Result | Value |
|---|---|---|
| Average result per trade above 0R | not yet | -0.720R |
| Clustered t at least 1.65 | not yet | t = 0.00 |
| Beats the TAIEX over the same holding windows | not yet | -5.75% per trade |
| Beats random entry with the same exit rules | not yet | -0.720R vs -0.190R (coverage 100%) |
| At least 20 bull-regime trades with average above 0R | not yet | 0 trades |

Until the gate opens these checks are informational; the early numbers swing a lot on few trades.

## Sleeve rules (fixed)
- V8, V10 and V11 combined; the same stock and signal day counts once
- At most 10 open positions; the most liquid names (20-day turnover) fill free slots first
- Costs: 0.585% round trip plus 0.1% slippage; a gap-up open of 9% or more is treated as unfillable
