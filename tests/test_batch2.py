import numpy as np
import pandas as pd
import pytest
from src.analytics import features, rs_multi, levels_events, candidates
from tests.test_analytics import make_prices


def test_rs_multi_matches_hand_calculation_and_has_no_lookahead():
    px, weights = make_prices(n=160)
    f = features.compute(px)
    syms = {"IDX": "^IDX"}
    out = rs_multi.compute(f, weights, syms, periods=(1, 5), vol_window=30)
    close = f.pivot(index="date", columns="symbol", values="close").sort_index()
    dates = list(close.index)
    i = 100
    a5 = (close["A.NS"] / close["A.NS"].shift(5) - 1) * 100
    x5 = (close["^IDX"] / close["^IDX"].shift(5) - 1) * 100
    daily_a = (close["A.NS"] / close["A.NS"].shift(1) - 1) * 100
    daily_x = (close["^IDX"] / close["^IDX"].shift(1) - 1) * 100
    sd = (daily_a - daily_x).iloc[i - 29:i + 1].std()
    row = out[(out.symbol == "A.NS") & (out.date == dates[i]) & (out.period == 5)].iloc[0]
    assert row.rs == pytest.approx(a5.iloc[i] - x5.iloc[i])
    assert row.rs_z == pytest.approx((a5.iloc[i] - x5.iloc[i]) / (sd * np.sqrt(5)))
    # truncating the future must not change the value on that date
    f_cut = features.compute(px[px.date <= dates[i]])
    out_cut = rs_multi.compute(f_cut, weights, syms, periods=(1, 5), vol_window=30)
    row2 = out_cut[(out_cut.symbol == "A.NS") & (out_cut.date == dates[i]) & (out_cut.period == 5)].iloc[0]
    assert row2.rs_z == pytest.approx(row.rs_z)


def _series(day25, day26, n_flat=25):
    rows = []
    dates = pd.bdate_range("2026-01-01", periods=n_flat + 2).strftime("%Y-%m-%d")
    for k in range(n_flat):
        rows.append(("X.NS", dates[k], 100, 101, 99, 100, 1000))
    for k, spec in ((n_flat, day25), (n_flat + 1, day26)):
        rows.append(("X.NS", dates[k], spec["open"], spec["high"], spec["low"],
                     spec["close"], spec["volume"]))
    px = pd.DataFrame(rows, columns=["symbol", "date", "open", "high", "low", "close", "volume"])
    out = levels_events.compute(features.compute(px), vol_mult=1.5, window=5, tol_pct=0.3)
    return out.iloc[-2]["event"], out.iloc[-1]["event"]


def test_level_events():
    brk = dict(open=101, high=103.5, low=101, close=103, volume=3000)
    # breakout on strong volume, then price falls back under the broken level
    assert _series(brk, dict(open=102, high=102, low=99.5, close=100, volume=1000)) == \
        ("breakout confirmed", "failed breakout")
    # breakout, then pullback to the level that holds
    assert _series(brk, dict(open=103, high=103, low=101.1, close=102.5, volume=1000)) == \
        ("breakout confirmed", "retest held (above PDH)")
    # same cross but on ordinary volume is NOT confirmed
    weak = dict(brk, volume=1000)
    assert _series(weak, dict(open=102, high=103, low=102, close=102.5, volume=1000))[0] == \
        "breakout on low volume"
    # breakdown
    dn = dict(open=99, high=99, low=96.5, close=97, volume=3000)
    assert _series(dn, dict(open=98, high=100.5, low=98, close=100, volume=1000)) == \
        ("breakdown confirmed", "failed breakdown")


def _row(**kw):
    base = dict(symbol="S.NS", sector="NIFTYPHARMA", rs_sector_z=1.0, rs_nifty_z=1.0,
                event="breakout confirmed", rel_volume=2.0, ma_alignment="bullish",
                idx_trend="bullish")
    base.update(kw)
    return base


def test_candidate_scores_components_and_missing_data():
    d = pd.DataFrame([
        _row(),                                              # everything bullish
        _row(rs_sector_z=np.nan, sector=None),               # no sector index
        _row(rel_volume=np.nan),                             # essential input missing
        _row(rs_sector_z=-1.2, rs_nifty_z=-0.9, event="breakdown confirmed",
             ma_alignment="bearish", idx_trend="bearish"),   # everything bearish
        _row(ma_alignment="bearish"),                        # bullish but trend disagrees
    ])
    s, bull, bear = candidates.score(d, z_thr=0.5, vol_mult=1.5)
    assert list(s.bull_score[[0, 1, 3, 4]]) == [6, 5, 1, 5]
    assert list(s.bear_score[[0, 3]]) == [1, 6]
    assert list(s.max_score) == [6, 5, 6, 6, 6]
    assert np.isnan(s.bull_score[2]) and s.data_status[2] == "missing data"
    t = candidates.add_text(s, bull, bear, min_score=4, z_thr=0.5)
    assert t.bull_components[0].count("[x]") == 6
    assert t.bull_components[2] is None                       # no text without a score
    assert "stock trend bearish" in t.bull_against[4]         # contradicting evidence shown
    assert t.bull_against[0] == "none"
    assert t.bear_components[3].count("[x]") == 6


def test_every_stock_is_compared_with_the_broad_index():
    """A stock that is only in a sector index must still get RS vs the broad index."""
    px, weights = make_prices(n=120)
    px = px.replace({"^IDX": "^SECTOR"})
    broad = px[px.symbol == "^SECTOR"].assign(symbol="^BROAD")
    px = pd.concat([px, broad], ignore_index=True)
    w = pd.DataFrame({"index_name": ["SECTOR", "SECTOR", "SECTOR", "BROAD"],
                      "symbol": ["A.NS", "B.NS", "C.NS", "A.NS"],
                      "weight": [0.5, 0.3, 0.2, 1.0]})
    f = features.compute(px)
    out = rs_multi.compute(f, w, {"SECTOR": "^SECTOR", "BROAD": "^BROAD"},
                           periods=(5,), vol_window=30, broad_index="BROAD")
    last = out.date.max()
    got = out[out.date == last].groupby("symbol").benchmark.apply(lambda x: sorted(x)).to_dict()
    assert got["A.NS"] == ["BROAD", "SECTOR"]
    assert got["B.NS"] == ["BROAD", "SECTOR"]      # B is NOT in the broad index list
    assert got["C.NS"] == ["BROAD", "SECTOR"]