"""Price-level events on COMPLETED daily candles (no intraday data needed).

event (first match wins):
  failed breakout / failed breakdown : yesterday was a confirmed break and today's
                                       close is back on the other side of that level
  breakout confirmed / breakdown confirmed : close beyond PDH/PDL AND relative volume
                                       >= multiple
  retest held (above PDH) / (below PDL) : within `window` days after a confirmed
                                       break, price came back to the broken level
                                       (within tolerance) and closed beyond it again
  breakout/breakdown on low volume   : crossed the level but volume did not confirm
  ... (volume unknown)               : crossed the level, no volume baseline yet
  none
Opening-range levels need intraday candles and are NOT available here.
"""
import numpy as np
import pandas as pd
from src.db import get_conn, load_config

COLS = ["symbol", "date", "open", "close", "prev_close", "pdh", "pdl", "status",
        "dist_pdh_pct", "dist_pdl_pct", "rel_volume", "event", "confirmed"]


def compute(feat, vol_mult=1.5, window=5, tol_pct=0.3):
    d = feat.sort_values(["symbol", "date"]).reset_index(drop=True).copy()

    def shifted(col, n=1):
        return d.groupby("symbol")[col].shift(n)

    vol_known = d["rel_volume"].notna()
    vol_ok = d["rel_volume"] >= vol_mult
    brk = d["close"] > d["pdh"]
    brd = d["close"] < d["pdl"]
    brk_c, brd_c = brk & vol_ok, brd & vol_ok
    d["_brk_c"], d["_brd_c"] = brk_c.astype(int), brd_c.astype(int)

    d["_lvl_up"] = np.where(brk_c, d["pdh"], np.nan)
    d["_lvl_dn"] = np.where(brd_c, d["pdl"], np.nan)
    lvl_up = d.groupby("symbol")["_lvl_up"].transform(lambda s: s.shift(1).ffill(limit=window))
    lvl_dn = d.groupby("symbol")["_lvl_dn"].transform(lambda s: s.shift(1).ffill(limit=window))
    tol = tol_pct / 100
    retest_up = (lvl_up.notna() & (d["low"] <= lvl_up * (1 + tol)) &
                 (d["close"] > lvl_up) & (d["prev_close"] > lvl_up))
    retest_dn = (lvl_dn.notna() & (d["high"] >= lvl_dn * (1 - tol)) &
                 (d["close"] < lvl_dn) & (d["prev_close"] < lvl_dn))

    prev_brk_c = shifted("_brk_c").fillna(0).astype(bool)
    prev_brd_c = shifted("_brd_c").fillna(0).astype(bool)
    failed_up = prev_brk_c & (d["close"] < shifted("pdh"))
    failed_dn = prev_brd_c & (d["close"] > shifted("pdl"))

    d["event"] = np.select(
        [failed_up, failed_dn, brk_c, brd_c, retest_up, retest_dn,
         brk & vol_known, brd & vol_known, brk, brd],
        ["failed breakout", "failed breakdown", "breakout confirmed",
         "breakdown confirmed", "retest held (above PDH)", "retest held (below PDL)",
         "breakout on low volume", "breakdown on low volume",
         "breakout (volume unknown)", "breakdown (volume unknown)"],
        default="none")
    d["status"] = np.where(brk, "above PDH", np.where(brd, "below PDL", "inside"))
    d.loc[d["pdh"].isna(), "status"] = None
    d["confirmed"] = d["event"].isin(["breakout confirmed", "breakdown confirmed"]).astype(int)
    return d[COLS]


def run():
    cfg = load_config()
    a = cfg.get("analytics", {})
    conn = get_conn()
    feat = pd.read_sql("SELECT * FROM gold_features", conn)
    stocks = pd.read_sql("SELECT symbol FROM instruments WHERE kind='stock'", conn)["symbol"]
    feat = feat[feat["symbol"].isin(stocks)]
    out = compute(feat, cfg["thresholds"]["breakout_volume_multiple"],
                  a.get("retest_window", 5), a.get("retest_tolerance_pct", 0.3))
    conn.execute("DELETE FROM gold_levels")
    out.to_sql("gold_levels", conn, if_exists="append", index=False, chunksize=5000)
    conn.commit()
    print(f"gold_levels: {len(out)} rows | events today: "
          f"{out[out['date'] == out['date'].max()]['event'].value_counts().to_dict()}")


if __name__ == "__main__":
    run()