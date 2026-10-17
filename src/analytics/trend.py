import numpy as np
import pandas as pd
from src.db import get_conn, load_config


def compute(prices, fast, slow):
    df = prices.sort_values(["symbol", "date"]).copy()
    g = df.groupby("symbol")["close"]
    df["sma_fast"] = g.transform(lambda s: s.rolling(fast).mean())
    df["sma_slow"] = g.transform(lambda s: s.rolling(slow).mean())
    bull = (df["close"] > df["sma_fast"]) & (df["sma_fast"] > df["sma_slow"])
    bear = (df["close"] < df["sma_fast"]) & (df["sma_fast"] < df["sma_slow"])
    df["trend"] = np.where(bull, "bullish", np.where(bear, "bearish", "sideways"))
    df.loc[df["sma_slow"].isna(), "trend"] = None
    return df[["symbol", "date", "sma_fast", "sma_slow", "trend"]]


def run():
    cfg = load_config()
    conn = get_conn()
    prices = pd.read_sql("SELECT symbol, date, close FROM silver_daily_prices", conn)
    out = compute(prices, cfg["thresholds"]["trend_sma_fast"],
                  cfg["thresholds"]["trend_sma_slow"])
    conn.execute("DELETE FROM gold_trend")
    out.to_sql("gold_trend", conn, if_exists="append", index=False)
    conn.commit()
    print(f"gold_trend: {len(out)} rows")


if __name__ == "__main__":
    run()