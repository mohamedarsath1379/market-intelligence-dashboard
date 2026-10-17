# Market Intelligence Dashboard (NSE, end-of-day)

An end-of-day market analysis tool for Indian equities (Nifty 50 and Nifty Pharma). Each day after market close it answers:

- What moved the index, and by how much? (contribution = weight x stock move)
- How broad was the move? (advances vs declines)
- Which stocks are stronger or weaker than their index? (relative strength)
- Which stocks crossed the previous day's high or low, and was volume behind it?
- Did these setups work in historical data? (backtest against a random baseline)

**This is an analysis and screening tool. It is not investment advice, and it does not generate buy/sell signals.**

## Features

| Page | What it shows |
|---|---|
| Home | Daily snapshot: index moves, trend, breadth, confirmed breakouts/breakdowns, gainers/losers, top contributors/draggers |
| Market Overview | Index cards, heatmap (box size = weight, colour = move), rebased performance chart |
| Index Drivers | Contribution bar chart and breadth history for a chosen index and date |
| Stock Scanner | Setups vs watchlist, each with its evidence and "against" line; simple breakout list; relative strength table |
| Stock Detail | Candlestick chart with SMA 20/50, PDH/PDL lines, volume, setup score, recent level events |
| Backtest | Simple breakout rule tested on history |
| Setup Backtest | The scanner's own setups tested with next-day-open entry, costs and a random baseline |

A Telegram bot sends one end-of-day summary and never sends the same day twice. It does not send while the market is still open.

## Data flow

```
Yahoo Finance + niftyindices.com constituent lists
        |
   BRONZE  raw downloads (data/raw, bronze_daily_prices), never edited
        |
   SILVER  validated prices (duplicates and bad rows removed), index weights
        |
   GOLD    analytics tables (returns, trend, contribution, breadth, relative
           strength, level events, candidate scores, rankings)
        |
   Streamlit dashboard + Telegram alert
```

Storage is a single SQLite file (`data/market.db`). The pipeline rebuilds it.

## How the numbers are calculated

- **Daily return**: close / previous close - 1.
- **PDH / PDL**: previous day's high and low.
- **Trend**: bullish if close > SMA 20 > SMA 50, bearish if close < SMA 20 < SMA 50, otherwise sideways.
- **Contribution**: index weight x stock % move. Weights are approximate (see Limits), so contributions do not add up exactly to the official index move.
- **Breadth**: number of index stocks up vs down.
- **Relative strength**: stock return minus benchmark return over 1, 5 and 20 days. The 5-day score is also normalised (z-score) by recent volatility so stocks can be compared.
- **Relative volume**: today's volume / average of the previous 20 days (today excluded).
- **Level events**: a *confirmed* breakout is a close above PDH with relative volume at or above 1.5x (breakdown is the mirror image). Crosses on low volume are labelled as such and not treated as signals. Retests and failed breakouts are also detected.
- **Setup score**: one point each for RS vs sector, RS vs Nifty 50, a confirmed level event, volume, stock trend, and index trend (max 5 or 6). It is a checklist, **not a probability of profit**.
- **Setup vs watchlist**: a setup needs score >= 4 and a same-direction confirmed level event. Everything else with a good score goes to the watchlist.

Every value on day T uses only data up to the close of day T (code reviewed for look-ahead).

## Backtest result (stated honestly)

Rule: the scanner's setups (score >= 4 plus a confirmed breakout/breakdown). The signal is known at the close, entry is the **next day's open**, exit after 5 days or a 3% stop, 0.1% cost per side. The baseline picks a **random stock on the same signal date**, in the same direction, with the same hold, stop and cost.

| | Bullish | Bearish |
|---|---|---|
| Trades | 3,589 | 1,932 |
| Win rate | 40.3% | 38.1% |
| Avg return per trade | -0.268% | -0.592% |
| Profit factor | 0.83 | 0.64 |
| Random stocks, same dates | -0.079% | -0.459% |
| Edge vs random | -0.189% | -0.133% |

**Conclusion: on this data the setups did not beat random entries.** The likely reason is that the signal fires on the day of the move, so the next-day-open entry is late. The tool is therefore useful for explaining and screening the market, not as an entry rule. It can test any other rule the same way.

## Limits

- End-of-day data only, from Yahoo Finance (sometimes delayed or incomplete for the latest day).
- Index weights are approximate (market-cap based), not official free-float weights.
- Uses the current index stock list, so stocks that left the index are missing (survivorship bias flatters results).
- About 4 years of history. Costs are estimates. Dividends are ignored.
- Trades on the same date are correlated, so "beat X% of random runs" is a guide, not a formal statistical test.
- Bearish backtest results measure the price falling. Shorting stocks overnight in India needs futures.
- Past results do not predict future results.

## Run it

```bash
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt

python -m src.pipeline         # download, validate, analyse, alert
python -m src.pipeline analytics   # skip the download
streamlit run dashboard/app.py
python -m pytest -q tests
```

Optional Telegram alert: create a `.env` file in the project root (never commit it):

```
TELEGRAM_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

Test the message without sending: `python -m src.alerts.telegram --dry`.

## Project structure

```
config.yaml            indices, thresholds, backtest defaults
db/schema.sql          bronze, silver and gold tables
src/ingestion/         constituents, prices (bronze), validate (silver)
src/analytics/         returns, trend, contribution, breadth, relative strength,
                       features, level events, candidates, scanner
src/backtest/          simple engine and the setup backtest
src/alerts/telegram.py end-of-day summary, no duplicate sends
src/pipeline.py        runs everything in order
dashboard/             Streamlit app and pages
tests/                 hand-checked calculations
```

## Disclaimer

For education and analysis only. Nothing here is investment advice or a recommendation to buy or sell any security.