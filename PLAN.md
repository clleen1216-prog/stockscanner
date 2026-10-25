# Stockscanner v3 plan (short version)

Full plan with the evidence table and roadmap is in the shared document "Stockscanner v3: Strategy Reset & Set-and-Forget Plan". This file keeps the rules next to the code so they cannot drift.

## Position
- **Core:** automatic monthly purchase of a broad index fund. This is the default and the benchmark.
- **Satellite:** 0% until the gate below says GRADUATE, then 2% of the portfolio (5% maximum). One combined sleeve of V8 + V10 + V11, at most 10 open positions.
- **Lab:** everything else, paper only, rules frozen. No new variants until gate G1 resolves.

## Gate G1 (opens on or after 2027-04-22; first signals were 2026-10-22)
Needs at least 100 closed trades in the combined, capped portfolio and at least 40 distinct signal dates.

| Check | GRADUATE needs | If it fails |
|---|---|---|
| Average result per trade | above 0R after costs and fill haircuts | RETIRE |
| Significance | t of at least 1.65, trades grouped by signal date | CONTINUE once |
| Versus market | beats the TAIEX over the same holding windows | CONTINUE once |
| Versus random entry | beats random entries with the same exit rules on the same window | CONTINUE once |
| Market regime | at least 20 trades opened while TAIEX was above its 60-day average, average above 0R | CONTINUE once |

CONTINUE means one extension to 12 months, then GRADUATE or RETIRE. No third round.

## Pace warning
With 10 slots and an average hold of B trading days, about 10 / B trades finish per day. At B = 12 that is roughly 0.8 a day, so 100 closed trades may arrive only around April to May 2027. If G1 has not opened by 2027-10-22 the answer is RETIRE (not enough evidence). `paper/STATUS.md` shows the live pace estimate.

## After GRADUATE
Sleeve starts at 2%, rises to 5% only after 6 live months in line with paper. Fed liquidity and VIX only ever shrink size. Circuit breaker: halt if the sleeve falls 25% from its peak, or if average live result after 50 live trades is below -0.15R.

## Do not
- Change strategy rules after the `v3-frozen` tag.
- Add new variants before G1 resolves.
- Treat the three Taiwan strategies as independent proof (their signals overlap).
