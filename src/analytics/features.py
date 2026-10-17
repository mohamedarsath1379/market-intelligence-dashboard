"""Per-symbol daily features (silver -> gold_features).

Every value on day T uses only data up to day T (no look-ahead).
"""
import numpy as np
import pandas as pd
from src.db import get_conn, load_config

COLS = ["symbol", "date", "open", "high", "low", "close", "prev_close",
        "pct_change", "gap_pct", "ret_from_open", "pdh", "pdl",
        "ret_5d", "ret_20d", "roc", "sma_20", "sma_50", "ma_alignment",
        "atr", "atr_pct", "volume", "rel_volume",
        "dist_pdh_pct", "dist_pdl_pct"]


def compute(px, atr_window=14, roc_window=10, volume_window=20):
    df = px.sort_values(["symbol", "date"]).reset_index(drop=True).copy()

    def gb(col):
        return df.groupby("symbol")[col]

    df["prev_close"] = gb("close").shift(1)
    df["pdh"] = gb("high").shift(1)                       # previous-day high
    df["pdl"] = gb("low").shift(1)                        # previous-day low
    df["pct_change"] = (df["close"] / df["prev_close"] - 1) * 100
    df["gap_pct"] = (df["open"] / df["prev_close"] - 1) * 100
    df["ret_from_open"] = (df["close"] / df["open"] - 1) * 100
    df["ret_5d"] = (df["close"] / gb("close").shift(5) - 1) * 100
    df["ret_20d"] = (df["close"] / gb("close").shift(20) - 1) * 100
    df["roc"] = (df["close"] / gb("close").shift(roc_window) - 1) * 100

    df["sma_20"] = gb("close").transform(lambda s: s.rolling(20).mean())
    df["sma_50"] = gb("close").transform(lambda s: s.rolling(50).mean())
    bull = (df["close"] > df["sma_20"]) & (df["sma_20"] > df["sma_50"])
    bear = (df["close"] < df["sma_20"]) & (df["sma_20"] < df["sma_50"])
    df["ma_alignment"] = np.where(bull, "bullish",
                                  np.where(bear, "bearish", "mixed"))
    df.loc[df["sma_50"].isna(), "ma_alignment"] = None

    # ATR: simple average of true range over atr_window days
    hl = df["high"] - df["low"]
    hc = (df["high"] - df["prev_close"]).abs()
    lc = (df["low"] - df["prev_close"]).abs()
    df["tr"] = pd.concat([hl, hc, lc], axis=1).max(axis=1, skipna=False)
    df["atr"] = gb("tr").transform(lambda s: s.rolling(atr_window).mean())
    df["atr_pct"] = df["atr"] / df["close"] * 100

    # relative volume vs the PREVIOUS volume_window days (excludes today)
    avg_vol = gb("volume").transform(
        lambda s: s.shift(1).rolling(volume_window).mean())
    df["rel_volume"] = (df["volume"] / avg_vol).replace([np.inf, -np.inf], np.nan)

    df["dist_pdh_pct"] = (df["close"] / df["pdh"] - 1) * 100
    df["dist_pdl_pct"] = (df["close"] / df["pdl"] - 1) * 100
    return df[COLS]


def run():
    cfg = load_config()
    a = cfg.get("analytics", {})
    conn = get_conn()
    px = pd.read_sql("SELECT * FROM silver_daily_prices", conn)
    out = compute(px, a.get("atr_window", 14), a.get("roc_window", 10),
                  a.get("volume_window", 20))
    conn.execute("DELETE FROM gold_features")
    out.to_sql("gold_features", conn, if_exists="append", index=False,
               chunksize=5000)
    conn.commit()
    print(f"gold_features: {len(out)} rows")


if __name__ == "__main__":
    run()