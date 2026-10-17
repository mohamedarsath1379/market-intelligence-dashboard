"""Relative strength over several periods, vs every index a stock belongs to.

rs   = stock % return over n days - benchmark % return over the same n days
rs_z = rs / (sd of daily excess return over the last rs_vol_window days x sqrt(n))
       -> a normalised score, so 1-day and 20-day numbers can be compared.
Only data up to each date is used (no look-ahead).
"""
import numpy as np
import pandas as pd
from src.db import get_conn, load_config


def _long(wide, col):
    return wide.reset_index().melt(id_vars="date", var_name="symbol", value_name=col)


def compute(feat, weights, index_syms, periods=(1, 5, 20), vol_window=60,
            history_days=100000, broad_index="NIFTY50"):
    """Every stock is compared with the broad index (even if it is not a member of
    it) and with each sector index it belongs to."""
    all_stocks = list(weights["symbol"].unique())
    close = feat.pivot(index="date", columns="symbol", values="close").sort_index()
    daily = (close / close.shift(1) - 1) * 100
    keep = set(close.index[-history_days:])
    parts = []
    for name, isym in index_syms.items():
        if isym not in close.columns:
            continue
        listed = (all_stocks if name == broad_index
                  else list(weights.loc[weights["index_name"] == name, "symbol"]))
        members = [s for s in listed if s in close.columns]
        if not members:
            continue
        excess = daily[members].sub(daily[isym], axis=0)
        sd = excess.rolling(vol_window, min_periods=max(10, int(vol_window * 0.6))).std()
        for n in periods:
            ret_n = (close / close.shift(n) - 1) * 100
            stock_ret = ret_n[members]
            rs = stock_ret.sub(ret_n[isym], axis=0)
            z = rs / (sd * np.sqrt(n))
            x = _long(stock_ret, "stock_ret")
            x = x.merge(_long(rs, "rs"), on=["date", "symbol"])
            x = x.merge(_long(z, "rs_z"), on=["date", "symbol"])
            x["bench_ret"] = x["date"].map(ret_n[isym])
            x["period"] = n
            x["benchmark"] = name
            x = x[x["date"].isin(keep)].dropna(subset=["stock_ret", "bench_ret"])
            parts.append(x[["symbol", "date", "period", "benchmark",
                            "stock_ret", "bench_ret", "rs", "rs_z"]])
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def run():
    cfg = load_config()
    a = cfg.get("analytics", {})
    conn = get_conn()
    feat = pd.read_sql("SELECT symbol, date, close FROM gold_features", conn)
    weights = pd.read_sql("SELECT index_name, symbol FROM silver_index_weights", conn)
    syms = {n: c["yf_symbol"] for n, c in cfg["indices"].items()}
    out = compute(feat, weights, syms, tuple(a.get("rs_periods", [1, 5, 20])),
                  a.get("rs_vol_window", 60), a.get("rs_history_days", 100000),
                  a.get("broad_index", "NIFTY50"))
    conn.execute("DELETE FROM gold_rs_multi")
    out.to_sql("gold_rs_multi", conn, if_exists="append", index=False, chunksize=5000)
    conn.commit()
    print(f"gold_rs_multi: {len(out)} rows")


if __name__ == "__main__":
    run()