"""Index contribution in % and in index POINTS.

contrib_pct = weight x stock % change
contrib_pts = weight x stock % change / 100 x previous index close
share_of_move_pct = contrib_pts / actual index point change x 100

weight_mode:
  backcast (default): today's weights rolled back with price ratios (fixed share
      counts), so the weight used on each day is close to that day's real weight.
  constant: today's weights on every day (kept for comparison/tests).
Weights are still approximate (market-cap based), not official free-float weights.
explained_pct shows how much of the real index move our weights explain.
"""
import numpy as np
import pandas as pd
from src.db import get_conn, load_config


def backcast_weights(close, w0):
    """Weight each stock had at the PREVIOUS close, assuming fixed share counts."""
    q = w0.reindex(close.columns) / close.ffill().iloc[-1]
    val = close.shift(1) * q
    return val.div(val.sum(axis=1), axis=0)


def compute(feat, weights, index_syms, top_n=3, min_move_pct=0.05,
            weight_mode="backcast"):
    stocks = feat[["symbol", "date", "pct_change"]].dropna()
    detail, summary = [], []
    for name, isym in index_syms.items():
        ix = feat[feat["symbol"] == isym][["date", "close", "prev_close"]].dropna()
        if ix.empty:
            continue
        ix = ix.assign(index_pts=ix["close"] - ix["prev_close"],
                       index_pct=(ix["close"] / ix["prev_close"] - 1) * 100)
        ix = ix.rename(columns={"prev_close": "idx_prev"})[
            ["date", "idx_prev", "index_pts", "index_pct"]]
        w = weights[weights["index_name"] == name][["symbol", "weight"]]
        if weight_mode == "backcast":
            members = w.set_index("symbol")["weight"]
            close = (feat[feat["symbol"].isin(members.index)]
                     .pivot(index="date", columns="symbol", values="close")
                     .sort_index())
            wide = backcast_weights(close, members)
            wl = (wide.reset_index()
                  .melt(id_vars="date", var_name="symbol", value_name="weight")
                  .dropna(subset=["weight"]))
            m = stocks.merge(wl, on=["symbol", "date"]).merge(ix, on="date")
        else:
            m = stocks.merge(w, on="symbol").merge(ix, on="date")
        m["contrib_pct"] = m["weight"] * m["pct_change"]
        m["contrib_pts"] = m["weight"] * m["pct_change"] / 100 * m["idx_prev"]
        big = m["index_pct"].abs() >= min_move_pct
        m["share_of_move_pct"] = np.where(big, m["contrib_pts"] / m["index_pts"] * 100,
                                          np.nan)
        m["rank_pos"] = (m.groupby("date")["contrib_pts"]
                         .rank(ascending=False, method="first").astype(int))
        m.insert(0, "index_name", name)
        detail.append(m[["index_name", "date", "symbol", "weight", "pct_change",
                         "contrib_pct", "contrib_pts", "share_of_move_pct",
                         "rank_pos"]])
        for date, g in m.groupby("date"):
            pts = float(g["index_pts"].iloc[0])
            explained = float(g["contrib_pts"].sum())
            top = (g["contrib_pts"].nlargest(top_n) if pts >= 0
                   else g["contrib_pts"].nsmallest(top_n))
            ok = abs(float(g["index_pct"].iloc[0])) >= min_move_pct
            summary.append((name, date, pts, explained,
                            explained / pts * 100 if ok else np.nan,
                            float(top.sum()),
                            float(top.sum()) / pts * 100 if ok else np.nan))
    d = pd.concat(detail, ignore_index=True) if detail else pd.DataFrame()
    s = pd.DataFrame(summary, columns=["index_name", "date", "index_pts",
                                       "explained_pts", "explained_pct",
                                       "top_n_pts", "top_n_share_pct"])
    return d, s


def run():
    cfg = load_config()
    a = cfg.get("analytics", {})
    conn = get_conn()
    feat = pd.read_sql("SELECT * FROM gold_features", conn)
    weights = pd.read_sql("SELECT index_name, symbol, weight FROM silver_index_weights", conn)
    syms = {n: c["yf_symbol"] for n, c in cfg["indices"].items()}
    d, s = compute(feat, weights, syms, a.get("narrow_top_n", 3),
                   weight_mode=a.get("weight_mode", "backcast"))
    conn.execute("DELETE FROM gold_contrib_points")
    conn.execute("DELETE FROM gold_contrib_summary")
    d.to_sql("gold_contrib_points", conn, if_exists="append", index=False, chunksize=5000)
    s.to_sql("gold_contrib_summary", conn, if_exists="append", index=False)
    conn.commit()
    print(f"gold_contrib_points: {len(d)} rows | gold_contrib_summary: {len(s)} rows "
          f"| weight mode: {a.get('weight_mode', 'backcast')}")


if __name__ == "__main__":
    run()