def flags(ret, volume_multiple):
    """ret = gold_returns rows. Adds breakout / breakdown flags."""
    df = ret.copy()
    df["vol_ratio"] = df["volume"] / df["avg_vol_20"]
    vol_ok = df["volume"] > volume_multiple * df["avg_vol_20"]
    df["breakout"] = (df["close"] > df["pdh"]) & vol_ok
    df["breakdown"] = (df["close"] < df["pdl"]) & vol_ok
    return df