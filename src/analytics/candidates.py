"""Candidate scoring and rankings (rule-based, every component visible).

Bullish components (bearish = mirror image), each worth 1 point:
  RS vs sector index  : 5-day normalised relative strength > +threshold  (if a sector index exists)
  RS vs Nifty 50      : 5-day normalised relative strength > +threshold
  price level         : breakout confirmed, or retest held above PDH
  volume              : relative volume >= multiple
  stock trend         : SMA alignment bullish (close > SMA20 > SMA50)
  index trend         : trend of the stock's sector index (or Nifty 50) is bullish
A setup qualifies when its score >= candidate_min_score. The score is NOT a
probability of profit. If any essential input is missing the row gets no score.
"""
import numpy as np
import pandas as pd
from src.db import get_conn, load_config

BULL_LEVELS = ["breakout confirmed", "retest held (above PDH)"]
BEAR_LEVELS = ["breakdown confirmed", "retest held (below PDL)"]
ESSENTIAL = ["rs_nifty_z", "rel_volume", "ma_alignment", "idx_trend", "event"]


def score(d, z_thr=0.5, vol_mult=1.5):
    d = d.copy()
    ok = d[ESSENTIAL].notna().all(axis=1)
    sector_present = d["rs_sector_z"].notna()
    vol_ok = d["rel_volume"] >= vol_mult
    bull = pd.DataFrame({
        "rs_sector": d["rs_sector_z"] > z_thr, "rs_nifty": d["rs_nifty_z"] > z_thr,
        "level": d["event"].isin(BULL_LEVELS), "volume": vol_ok,
        "trend": d["ma_alignment"] == "bullish", "idx_trend": d["idx_trend"] == "bullish"})
    bear = pd.DataFrame({
        "rs_sector": d["rs_sector_z"] < -z_thr, "rs_nifty": d["rs_nifty_z"] < -z_thr,
        "level": d["event"].isin(BEAR_LEVELS), "volume": vol_ok,
        "trend": d["ma_alignment"] == "bearish", "idx_trend": d["idx_trend"] == "bearish"})
    d["max_score"] = 5 + sector_present.astype(int)
    d["bull_score"] = np.where(ok, bull.sum(axis=1), np.nan)
    d["bear_score"] = np.where(ok, bear.sum(axis=1), np.nan)
    d["data_status"] = np.where(ok, "ok", "missing data")
    return d, bull, bear


def _text(row, flags, side):
    box = lambda b: "[x]" if b else "[ ]"
    parts = []
    if pd.notna(row["rs_sector_z"]):
        parts.append(f"{box(flags['rs_sector'])} RS vs {row['sector']} {row['rs_sector_z']:+.1f}z")
    parts.append(f"{box(flags['rs_nifty'])} RS vs Nifty 50 {row['rs_nifty_z']:+.1f}z")
    parts.append(f"{box(flags['level'])} level: {row['event']}")
    parts.append(f"{box(flags['volume'])} volume {row['rel_volume']:.1f}x")
    parts.append(f"{box(flags['trend'])} stock trend {row['ma_alignment']}")
    parts.append(f"{box(flags['idx_trend'])} index trend {row['idx_trend']}")
    return "; ".join(parts)


def _against(row, side, z_thr):
    opp = "bearish" if side == "bull" else "bullish"
    lv = BEAR_LEVELS if side == "bull" else BULL_LEVELS
    sign = -1 if side == "bull" else 1
    out = []
    if pd.notna(row["rs_sector_z"]) and sign * row["rs_sector_z"] > z_thr:
        out.append(f"RS vs {row['sector']} {row['rs_sector_z']:+.1f}z")
    if sign * row["rs_nifty_z"] > z_thr:
        out.append(f"RS vs Nifty 50 {row['rs_nifty_z']:+.1f}z")
    if row["event"] in lv:
        out.append(row["event"])
    if row["event"] in ("failed breakout", "failed breakdown"):
        out.append(row["event"])
    if row["ma_alignment"] == opp:
        out.append(f"stock trend {opp}")
    if row["idx_trend"] == opp:
        out.append(f"index trend {opp}")
    return "; ".join(out) if out else "none"


def add_text(d, bull, bear, min_score, z_thr):
    d = d.copy()
    for col in ["bull_components", "bull_against", "bear_components", "bear_against"]:
        d[col] = None
    for side, flags in (("bull", bull), ("bear", bear)):
        idx = d.index[d[f"{side}_score"] >= min_score]
        d.loc[idx, f"{side}_components"] = [_text(d.loc[i], flags.loc[i], side) for i in idx]
        d.loc[idx, f"{side}_against"] = [_against(d.loc[i], side, z_thr) for i in idx]
    return d


def build_rankings(d, last, contrib_last, min_score, top=10):
    """d: scored rows for the latest date. Returns the gold_rankings frame."""
    rows = []

    def add(name, index_name, frame, value_col, detail_col=None, n=top):
        for k, (_, r) in enumerate(frame.head(n).iterrows(), 1):
            rows.append((last, name, index_name, k, r["symbol"],
                         None if pd.isna(r[value_col]) else float(r[value_col]),
                         r[detail_col] if detail_col else None))

    ok = d[d["data_status"] == "ok"].copy()
    ok["bench"] = ok["sector"].fillna("NIFTY50")
    for bench, g in ok.groupby("bench"):
        col = "rs_sector_z" if bench != "NIFTY50" else "rs_nifty_z"
        g = g.dropna(subset=[col])
        add("rs_strongest", bench, g.sort_values(col, ascending=False), col)
        add("rs_weakest", bench, g.sort_values(col), col)
    q = ok[ok["bull_score"] >= min_score].sort_values(
        ["bull_score", "rs_nifty_z"], ascending=[False, False])
    add("bullish_setup", None, q, "bull_score", "bull_components")
    q = ok[ok["bear_score"] >= min_score].sort_values(
        ["bear_score", "rs_nifty_z"], ascending=[False, True])
    add("bearish_setup", None, q, "bear_score", "bear_components")
    add("aligned_bullish", None, ok[ok["bull_score"] == ok["max_score"]],
        "bull_score", "bull_components")
    add("aligned_bearish", None, ok[ok["bear_score"] == ok["max_score"]],
        "bear_score", "bear_components")
    for iname, g in contrib_last.groupby("index_name"):
        add("contrib_positive", iname, g.sort_values("contrib_pts", ascending=False),
            "contrib_pts", n=5)
        add("contrib_negative", iname, g.sort_values("contrib_pts"), "contrib_pts", n=5)
    return pd.DataFrame(rows, columns=["date", "ranking_name", "index_name", "rank_pos",
                                       "symbol", "value", "detail"])


def run():
    cfg = load_config()
    a = cfg.get("analytics", {})
    broad = a.get("broad_index", "NIFTY50")
    z_thr, min_score = a.get("rs_z_threshold", 0.5), a.get("candidate_min_score", 4)
    mult = cfg["thresholds"]["breakout_volume_multiple"]
    conn = get_conn()
    weights = pd.read_sql("SELECT index_name, symbol FROM silver_index_weights", conn)
    stocks = sorted(weights["symbol"].unique())
    sector = (weights[weights["index_name"] != broad]
              .drop_duplicates("symbol").set_index("symbol")["index_name"])
    lv = pd.read_sql("SELECT symbol, date, event, rel_volume FROM gold_levels", conn)
    ft = pd.read_sql("SELECT symbol, date, ma_alignment FROM gold_features", conn)
    rs = pd.read_sql("SELECT symbol, date, benchmark, rs_z FROM gold_rs_multi WHERE period=5", conn)
    tr = pd.read_sql("SELECT index_name, date, trend FROM gold_market_trend", conn)

    d = lv[lv["symbol"].isin(stocks)].merge(ft, on=["symbol", "date"], how="left")
    d["sector"] = d["symbol"].map(sector)
    d["trend_index"] = d["sector"].fillna(broad)
    d = d.merge(rs[rs["benchmark"] == broad][["symbol", "date", "rs_z"]]
                .rename(columns={"rs_z": "rs_nifty_z"}), on=["symbol", "date"], how="left")
    rs_s = rs.rename(columns={"rs_z": "rs_sector_z", "benchmark": "sector"})
    d = d.merge(rs_s, on=["symbol", "date", "sector"], how="left")
    d = d.merge(tr.rename(columns={"index_name": "trend_index", "trend": "idx_trend"}),
                on=["trend_index", "date"], how="left")
    d = d.reset_index(drop=True)

    d, bull, bear = score(d, z_thr, mult)
    d = add_text(d, bull, bear, min_score, z_thr)
    cols = ["symbol", "date", "sector", "bull_score", "bear_score", "max_score",
            "data_status", "bull_components", "bull_against",
            "bear_components", "bear_against"]
    conn.execute("DELETE FROM gold_candidates")
    d[cols].to_sql("gold_candidates", conn, if_exists="append", index=False, chunksize=5000)

    # rankings for the latest market date; stocks without that date are STALE and excluded
    cfg_syms = {n: c["yf_symbol"] for n, c in cfg["indices"].items()}
    ix = pd.read_sql("SELECT date FROM gold_features WHERE symbol=?", conn,
                     params=(cfg_syms[broad],))
    last = ix["date"].max()
    today = d[d["date"] == last]
    stale = sorted(set(stocks) - set(today["symbol"]))
    contrib = pd.read_sql("SELECT index_name, symbol, contrib_pts FROM gold_contrib_points "
                          "WHERE date=?", conn, params=(last,))
    rk = build_rankings(today, last, contrib, min_score)
    conn.execute("DELETE FROM gold_rankings")
    rk.to_sql("gold_rankings", conn, if_exists="append", index=False)
    conn.commit()
    nb = int((today["bull_score"] >= min_score).sum())
    nr = int((today["bear_score"] >= min_score).sum())
    print(f"gold_candidates: {len(d)} rows | {last}: bullish setups {nb}, bearish setups {nr}, "
          f"no score (missing data) {int((today['data_status'] != 'ok').sum())}, "
          f"stale stocks excluded {len(stale)}")


if __name__ == "__main__":
    run()