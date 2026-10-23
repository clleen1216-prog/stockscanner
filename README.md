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

`.github/workflows/scan.yml` runs the scan every weekday at 17:30 Taiwan time and commits the CSV into `reports/`. You can also trigger it manually from the **Actions** tab.

## Settings

Edit the `CONFIG` block at the top of `stock_scanner.py` (minimum price, volume limits, MA spread, etc.).

## Disclaimer

For learning and research only. This is not investment advice. Data comes from free public sources and may be delayed or incomplete.
