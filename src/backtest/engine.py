import numpy as np
import pandas as pd
from src.db import get_conn

COLS = ["symbol", "signal_date", "entry_date", "entry_price",
        "exit_date", "exit_price", "exit_reason", "ret_pct"]


def load_data():
    conn = get_conn()
    try:
        stocks = pd.read_sql(
            "SELECT symbol FROM instruments WHERE kind='stock'", conn)["symbol"]
        px = pd.read_sql(
            "SELECT symbol, date, open, high, low, close, volume "
            "FROM silver_daily_prices", conn)
        ret = pd.read_sql(
            "SELECT symbol, date, pdh, avg_vol_20 FROM gold_returns", conn)
    finally:
        conn.close()
    px = px[px["symbol"].isin(stocks)]
    df = px.merge(ret, on=["symbol", "date"], how="left")
    return df.sort_values(["symbol", "date"]).reset_index(drop=True)


def simulate(sym, d, sig, hold_days, stop_pct, cost_pct, overlap=False):
    """Signal at close of day i -> enter at open of i+1 -> exit by close of i+hold_days."""
    o = d["open"].to_numpy()
    l = d["low"].to_numpy()
    c = d["close"].to_numpy()
    dates = d["date"].to_numpy()
    n = len(d)
    trades = []
    i = 0
    while i + hold_days <= n - 1:          # need a full holding window
        if not sig[i]:
            i += 1
            continue
        e = i + 1
        entry = o[e]
        if not entry > 0:                   # skips NaN or bad price
            i += 1
            continue
        last = i + hold_days
        exit_idx, exit_px, why = last, c[last], "time"
        if stop_pct > 0:
            stop_px = entry * (1 - stop_pct / 100)
            for j in range(e, last + 1):
                if o[j] <= stop_px:         # gapped below stop: exit at open
                    exit_idx, exit_px, why = j, o[j], "stop"
                    break
                if l[j] <= stop_px:         # touched stop during the day
                    exit_idx, exit_px, why = j, stop_px, "stop"
                    break
        ret = (exit_px / entry - 1) * 100 - 2 * cost_pct
        trades.append((sym, dates[i], dates[e], entry,
                       dates[exit_idx], exit_px, why, ret))
        i = i + 1 if overlap else exit_idx + 1
    return trades


def run_backtest(hold_days=5, stop_pct=3.0, cost_pct=0.1,
                 volume_multiple=1.5, buffer_pct=0.0):
    data = load_data()
    strat, base = [], []
    for sym, d in data.groupby("symbol"):
        d = d.reset_index(drop=True)
        sig = ((d["close"] > d["pdh"] * (1 + buffer_pct / 100)) &
               (d["volume"] > volume_multiple * d["avg_vol_20"])).to_numpy()
        strat += simulate(sym, d, sig, hold_days, stop_pct, cost_pct)
        # baseline: any day (after 20-day history exists), same exit rules
        any_day = d["avg_vol_20"].notna().to_numpy()
        base += simulate(sym, d, any_day, hold_days, stop_pct, cost_pct,
                         overlap=True)
    return pd.DataFrame(strat, columns=COLS), pd.DataFrame(base, columns=COLS)


if __name__ == "__main__":
    from src.backtest.metrics import summarize
    t, b = run_backtest()
    print("STRATEGY:", summarize(t))
    print("BASELINE:", summarize(b))