import numpy as np
import pandas as pd
import pytest
from src.analytics import features, market_trend, contribution_points, breadth_detail


def make_prices(n=120, seed=1):
    """3 stocks + 1 index whose daily return is EXACTLY the weighted stock return."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2025-01-01", periods=n).strftime("%Y-%m-%d")
    w = {"A.NS": 0.5, "B.NS": 0.3, "C.NS": 0.2}
    rows, rets = [], {}
    for s in w:
        r = rng.normal(0.0005, 0.012, n)
        rets[s] = r
        close = 100 * np.cumprod(1 + r)
        prev = np.concatenate([[100], close[:-1]])
        for i in range(n):
            rows.append((s, dates[i], prev[i] * 1.001, max(close[i], prev[i]) * 1.004,
                         min(close[i], prev[i]) * 0.996, close[i], 1_000_000 + 1000 * i))
    idx_r = sum(w[s] * rets[s] for s in w)
    idx = 20000 * np.cumprod(1 + idx_r)
    idx_prev = np.concatenate([[20000], idx[:-1]])
    for i in range(n):
        rows.append(("^IDX", dates[i], idx_prev[i], max(idx[i], idx_prev[i]) * 1.003,
                     min(idx[i], idx_prev[i]) * 0.997, idx[i], 0))
    px = pd.DataFrame(rows, columns=["symbol", "date", "open", "high", "low", "close", "volume"])
    weights = pd.DataFrame({"index_name": "IDX", "symbol": list(w), "weight": list(w.values())})
    return px, weights


def test_features_match_hand_calculation():
    px, _ = make_prices()
    f = features.compute(px)
    a = px[px.symbol == "A.NS"].reset_index(drop=True)
    fa = f[f.symbol == "A.NS"].reset_index(drop=True)
    assert np.isnan(fa.loc[0, "pct_change"]) and np.isnan(fa.loc[0, "pdh"])
    for i in (1, 30, 99):
        assert fa.loc[i, "pct_change"] == pytest.approx((a.close[i] / a.close[i - 1] - 1) * 100)
        assert fa.loc[i, "pdh"] == pytest.approx(a.high[i - 1])
        assert fa.loc[i, "pdl"] == pytest.approx(a.low[i - 1])
    assert fa.loc[60, "sma_20"] == pytest.approx(a.close[41:61].mean())
    # relative volume excludes today
    assert fa.loc[60, "rel_volume"] == pytest.approx(a.volume[60] / a.volume[40:60].mean())


def test_no_lookahead_in_features():
    px, _ = make_prices()
    full = features.compute(px)
    cut = features.compute(px[px.date <= px.date.unique()[80]])
    d = px.date.unique()[80]
    cols = ["pct_change", "pdh", "sma_20", "sma_50", "atr", "rel_volume", "ret_5d"]
    a = full[(full.date == d)].sort_values("symbol")[cols].to_numpy()
    b = cut[(cut.date == d)].sort_values("symbol")[cols].to_numpy()
    assert np.allclose(a, b, equal_nan=True)


def test_contribution_points_explain_the_index_move():
    px, weights = make_prices()
    f = features.compute(px)
    d, s = contribution_points.compute(f, weights, {"IDX": "^IDX"}, weight_mode="constant")
    big = s.dropna(subset=["explained_pct"])
    assert len(big) > 50
    assert np.allclose(big.explained_pct, 100, atol=1e-6)      # exact weights -> 100%
    one = d[(d.date == d.date.iloc[200]) & (d.symbol == "A.NS")].iloc[0]
    prev_idx = f[(f.symbol == "^IDX") & (f.date == one.date)].prev_close.iloc[0]
    assert one.contrib_pts == pytest.approx(0.5 * one["pct_change"] / 100 * prev_idx)
    assert d.groupby("date").rank_pos.apply(lambda x: sorted(x) == [1, 2, 3]).all()


def test_trend_bullish_bearish_mixed_insufficient():
    base = dict(close=100, pdh=99, pdl=95, sma_20=98, sma_50=96, atr_pct=1.0,
                pct_change=0.5, ret_from_open=0.4, ret_5d=2.0, date="2026-01-01")
    bear = dict(close=90, pdh=99, pdl=95, sma_20=98, sma_50=102, atr_pct=1.0,
                pct_change=-1.0, ret_from_open=-0.6, ret_5d=-3.0, date="2026-01-02")
    mixed = dict(close=97, pdh=99, pdl=95, sma_20=96, sma_50=100, atr_pct=1.0,
                 pct_change=0.8, ret_from_open=0.5, ret_5d=-2.0, date="2026-01-03")
    insuff = dict(base, sma_50=np.nan, date="2026-01-04")
    r = market_trend.classify(pd.DataFrame([base, bear, mixed, insuff]))
    assert list(r.trend) == ["bullish", "bearish", "mixed", "insufficient data"]
    assert r.bull_votes[0] == 6 and r.bear_votes[1] == 6
    assert "SMA20" in r.conditions[0]


def _breadth_case(stock_moves, weights_list, index_close):
    dates = ["2026-01-01", "2026-01-02"]
    rows = []
    for k, (c1, c2) in enumerate(stock_moves):
        for d, c in zip(dates, (c1, c2)):
            rows.append((f"S{k}.NS", d, c, c, c, c, 1000))
    for d, c in zip(dates, index_close):
        rows.append(("^I", d, c, c, c, c, 0))
    px = pd.DataFrame(rows, columns=["symbol", "date", "open", "high", "low", "close", "volume"])
    f = features.compute(px)
    w = pd.DataFrame({"index_name": "I", "symbol": [f"S{k}.NS" for k in range(len(stock_moves))],
                      "weight": weights_list})
    d, s = contribution_points.compute(f, w, {"I": "^I"}, top_n=1, weight_mode="constant")
    b = breadth_detail.compute(f, w, {"I": "^I"}, s, d, narrow_share=50,
                               narrow_min_move=0.2, narrow_ratio=1.5, top_n=1)
    return b[b.date == "2026-01-02"].iloc[0]


def test_breadth_divergence_and_narrow_flag():
    # index +1%, 3 of 4 stocks fall, one 70%-weight heavyweight jumps 10%
    day2 = _breadth_case([(100, 110), (100, 99), (100, 99), (100, 99)],
                         [0.7, 0.1, 0.1, 0.1], (1000, 1010))
    assert day2.advances == 1 and day2.declines == 3
    assert day2.divergence == "index up, most stocks down"
    assert day2.narrow_flag.startswith("top 1 stocks explain")


def test_broad_move_is_not_flagged_narrow():
    # every stock -1%: the 70%-weight stock explains 70% of the move,
    # exactly its own weight share -> concentrated weights, NOT a narrow move
    day2 = _breadth_case([(100, 99), (100, 99), (100, 99), (100, 99)],
                         [0.7, 0.1, 0.1, 0.1], (1000, 990))
    assert day2.declines == 4 and day2.divergence == "none"
    assert day2.narrow_flag == "none"


def test_backcast_weights_match_a_fixed_share_index():
    """Index = sum(shares x price): back-cast weights must explain 100% of every move,
    while constant weights drift away."""
    rng = np.random.default_rng(7)
    n = 400
    dates = pd.bdate_range("2024-01-01", periods=n).strftime("%Y-%m-%d")
    syms = [f"S{i}.NS" for i in range(6)]
    P = {s: 100 * np.cumprod(1 + rng.normal(0.0003 + 0.0008 * (i % 3), 0.013, n))
         for i, s in enumerate(syms)}
    q = {s: 1.0 + i for i, s in enumerate(syms)}
    idx = sum(q[s] * P[s] for s in syms)
    rows = [(s, d, P[s][k], P[s][k], P[s][k], P[s][k], 1000)
            for s in syms for k, d in enumerate(dates)]
    rows += [("^I", d, idx[k], idx[k], idx[k], idx[k], 0) for k, d in enumerate(dates)]
    px = pd.DataFrame(rows, columns=["symbol", "date", "open", "high", "low", "close", "volume"])
    tot = sum(q[s] * P[s][-1] for s in syms)
    w = pd.DataFrame({"index_name": "I", "symbol": syms,
                      "weight": [q[s] * P[s][-1] / tot for s in syms]})
    f = features.compute(px)
    _, s_bc = contribution_points.compute(f, w, {"I": "^I"}, weight_mode="backcast")
    _, s_const = contribution_points.compute(f, w, {"I": "^I"}, weight_mode="constant")
    assert np.allclose(s_bc.dropna(subset=["explained_pct"]).explained_pct, 100, atol=1e-6)
    assert (s_const.explained_pct - 100).abs().max() > 1.0