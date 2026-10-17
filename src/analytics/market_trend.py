"""Bullish / bearish / sideways / mixed classification for each index.

Six votes (+1 bullish, -1 bearish, 0 neutral):
  1 move vs previous close   2 move vs today's open   3 position vs PDH/PDL
  4 close vs SMA20           5 SMA20 vs SMA50         6 5-day return
Rules (configurable):
  bullish : bull votes >= min_votes and bear votes <= 1
  bearish : bear votes >= min_votes and bull votes <= 1
  mixed   : at least 2 bull AND 2 bear votes (signals conflict)
  sideways: everything else
  insufficient data: any needed input is missing (never forced)
"""
import numpy as np
import pandas as pd
from src.db import get_conn, load_config

NEEDED = ["pct_change", "ret_from_open", "pdh", "pdl", "sma_20", "sma_50", "ret_5d"]
SIGN = {1: "+", -1: "-", 0: "0"}


def _sgn(series, thr=0.0):
    return np.where(series > thr, 1, np.where(series < -thr, -1, 0))


def classify(f, flat=0.1, min_votes=4):
    d = f.reset_index(drop=True).copy()
    v = pd.DataFrame({
        "prev_close": _sgn(d["pct_change"], flat),
        "open": _sgn(d["ret_from_open"], flat),
        "levels": np.where(d["close"] > d["pdh"], 1,
                           np.where(d["close"] < d["pdl"], -1, 0)),
        "sma20": _sgn(d["close"] - d["sma_20"]),
        "cross": _sgn(d["sma_20"] - d["sma_50"]),
        "ret5": _sgn(d["ret_5d"], flat),
    })
    ok = d[NEEDED].notna().all(axis=1).to_numpy()
    bull = (v > 0).sum(axis=1).to_numpy()
    bear = (v < 0).sum(axis=1).to_numpy()
    trend = np.select(
        [~ok, (bull >= min_votes) & (bear <= 1), (bear >= min_votes) & (bull <= 1),
         (bull >= 2) & (bear >= 2)],
        ["insufficient data", "bullish", "bearish", "mixed"], default="sideways")

    texts = []
    for i, r in d.iterrows():
        if not ok[i]:
            texts.append("not enough history for all conditions")
            continue
        lvl = ("above PDH" if v.at[i, "levels"] == 1 else
               "below PDL" if v.at[i, "levels"] == -1 else "inside PDH-PDL")
        parts = [
            f"vs prev close {r['pct_change']:+.2f}% ({SIGN[v.at[i, 'prev_close']]})",
            f"vs open {r['ret_from_open']:+.2f}% ({SIGN[v.at[i, 'open']]})",
            f"close {lvl} ({SIGN[v.at[i, 'levels']]})",
            f"close {'above' if v.at[i, 'sma20'] > 0 else 'below'} SMA20 ({SIGN[v.at[i, 'sma20']]})",
            f"SMA20 {'above' if v.at[i, 'cross'] > 0 else 'below'} SMA50 ({SIGN[v.at[i, 'cross']]})",
            f"5-day {r['ret_5d']:+.2f}% ({SIGN[v.at[i, 'ret5']]})",
        ]
        if pd.notna(r.get("atr_pct", np.nan)):
            parts.append(f"volatility: ATR {r['atr_pct']:.1f}% of price (context only)")
        texts.append("; ".join(parts))
    return pd.DataFrame({"date": d["date"], "trend": trend,
                         "bull_votes": bull, "bear_votes": bear,
                         "conditions": texts})


def run():
    cfg = load_config()
    a = cfg.get("analytics", {})
    conn = get_conn()
    feat = pd.read_sql("SELECT * FROM gold_features", conn)
    parts = []
    for name, c in cfg["indices"].items():
        f = feat[feat["symbol"] == c["yf_symbol"]].sort_values("date")
        if f.empty:
            print(f"[warn] no index data for {name}")
            continue
        r = classify(f, a.get("trend_flat_pct", 0.1), a.get("trend_min_votes", 4))
        r.insert(0, "index_name", name)
        parts.append(r)
    out = pd.concat(parts, ignore_index=True)
    conn.execute("DELETE FROM gold_market_trend")
    out.to_sql("gold_market_trend", conn, if_exists="append", index=False)
    conn.commit()
    print(f"gold_market_trend: {len(out)} rows")


if __name__ == "__main__":
    run()