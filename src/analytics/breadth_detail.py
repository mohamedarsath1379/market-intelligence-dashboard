"""Market breadth, breadth divergence and narrow-move flag per index and day.

divergence : index up but most stocks down (or the reverse)
narrow_flag: the top-N contributors explain >= narrow_share_pct of a move of at
             least narrow_min_move_pct, AND they explain at least narrow_ratio times
             their own share of index weight (so a move that is only concentrated
             because the weights are concentrated is NOT flagged).
"""
import numpy as np
import pandas as pd
from src.db import get_conn, load_config


def _top_weight_share(contrib_idx, summary_idx, top_n):
    pts = summary_idx.set_index("date")["index_pts"]
    out = {}
    for date, g in contrib_idx.groupby("date"):
        p = pts.get(date, np.nan)
        if pd.isna(p) or g["weight"].sum() == 0:
            continue
        top = g.nlargest(top_n, "contrib_pts") if p >= 0 else g.nsmallest(top_n, "contrib_pts")
        out[date] = top["weight"].sum() / g["weight"].sum() * 100
    return pd.Series(out, name="top_n_weight_pct").rename_axis("date").reset_index()


def compute(feat, weights, index_syms, summary, contrib, narrow_share=50.0,
            narrow_min_move=0.2, narrow_ratio=1.5, top_n=3):
    out = []
    for name, isym in index_syms.items():
        members = weights.loc[weights["index_name"] == name, "symbol"]
        f = feat[feat["symbol"].isin(members)].dropna(subset=["pct_change"]).copy()
        if f.empty:
            continue
        f["adv"] = (f["pct_change"] > 0).astype(float)
        f["dec"] = (f["pct_change"] < 0).astype(float)
        f["unch"] = (f["pct_change"] == 0).astype(float)
        f["above_open"] = (f["close"] > f["open"]).astype(float)
        f["a20"] = np.where(f["sma_20"].notna(), (f["close"] > f["sma_20"]).astype(float), np.nan)
        f["a50"] = np.where(f["sma_50"].notna(), (f["close"] > f["sma_50"]).astype(float), np.nan)
        g = f.groupby("date")
        b = pd.DataFrame({
            "n": g.size(),
            "advances": g["adv"].sum().astype(int),
            "declines": g["dec"].sum().astype(int),
            "unchanged": g["unch"].sum().astype(int),
            "pct_above_open": g["above_open"].mean() * 100,
            "pct_above_sma20": g["a20"].mean() * 100,
            "pct_above_sma50": g["a50"].mean() * 100,
        }).reset_index()
        b["adv_pct"] = b["advances"] / b["n"] * 100
        b["dec_pct"] = b["declines"] / b["n"] * 100
        b["unch_pct"] = b["unchanged"] / b["n"] * 100
        b["ad_ratio"] = b["advances"] / b["declines"].replace(0, np.nan)
        ix = feat[feat["symbol"] == isym][["date", "pct_change"]].rename(
            columns={"pct_change": "index_pct"})
        b = b.merge(ix, on="date", how="left")
        s = summary[summary["index_name"] == name]
        b = b.merge(s[["date", "top_n_share_pct"]], on="date", how="left")
        tw = _top_weight_share(contrib[contrib["index_name"] == name], s, top_n)
        b = b.merge(tw, on="date", how="left")
        b["divergence"] = np.select(
            [(b["index_pct"] > 0) & (b["dec_pct"] > 50),
             (b["index_pct"] < 0) & (b["adv_pct"] > 50)],
            ["index up, most stocks down", "index down, most stocks up"],
            default="none")
        ratio = b["top_n_share_pct"] / b["top_n_weight_pct"]
        narrow = ((b["index_pct"].abs() >= narrow_min_move)
                  & (b["top_n_share_pct"] >= narrow_share)
                  & (ratio >= narrow_ratio)).to_numpy()
        b["narrow_flag"] = [
            f"top {top_n} stocks explain {sh:.0f}% of the move ({wt:.0f}% of weight)"
            if flag else "none"
            for sh, wt, flag in zip(b["top_n_share_pct"], b["top_n_weight_pct"], narrow)]
        b.insert(0, "index_name", name)
        out.append(b.drop(columns=["top_n_share_pct", "top_n_weight_pct"]))
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame()


def run():
    cfg = load_config()
    a = cfg.get("analytics", {})
    conn = get_conn()
    feat = pd.read_sql("SELECT * FROM gold_features", conn)
    weights = pd.read_sql("SELECT index_name, symbol, weight FROM silver_index_weights", conn)
    summary = pd.read_sql("SELECT * FROM gold_contrib_summary", conn)
    contrib = pd.read_sql("SELECT index_name, date, symbol, weight, contrib_pts "
                          "FROM gold_contrib_points", conn)
    syms = {n: c["yf_symbol"] for n, c in cfg["indices"].items()}
    out = compute(feat, weights, syms, summary, contrib,
                  a.get("narrow_share_pct", 50), a.get("narrow_min_move_pct", 0.2),
                  a.get("narrow_ratio", 1.5), a.get("narrow_top_n", 3))
    cols = ["index_name", "date", "n", "advances", "declines", "unchanged",
            "adv_pct", "dec_pct", "unch_pct", "ad_ratio", "pct_above_open",
            "pct_above_sma20", "pct_above_sma50", "index_pct", "divergence",
            "narrow_flag"]
    conn.execute("DELETE FROM gold_breadth_detail")
    out[cols].to_sql("gold_breadth_detail", conn, if_exists="append", index=False)
    conn.commit()
    print(f"gold_breadth_detail: {len(out)} rows")


if __name__ == "__main__":
    run()