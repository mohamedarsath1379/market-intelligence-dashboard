CREATE TABLE IF NOT EXISTS instruments (
  symbol TEXT PRIMARY KEY,
  name TEXT,
  kind TEXT                      -- 'stock' or 'index'
);

-- BRONZE: raw data exactly as downloaded
CREATE TABLE IF NOT EXISTS bronze_daily_prices (
  symbol TEXT, date TEXT,
  open REAL, high REAL, low REAL, close REAL, volume REAL,
  loaded_at TEXT,
  PRIMARY KEY (symbol, date)
);

-- SILVER: cleaned and validated
CREATE TABLE IF NOT EXISTS silver_daily_prices (
  symbol TEXT, date TEXT,
  open REAL, high REAL, low REAL, close REAL, volume REAL,
  PRIMARY KEY (symbol, date)
);
CREATE TABLE IF NOT EXISTS silver_index_weights (
  index_name TEXT, symbol TEXT, weight REAL, as_of TEXT,
  PRIMARY KEY (index_name, symbol)
);

-- GOLD: analytics outputs (more gold tables come in Step 2)
CREATE TABLE IF NOT EXISTS gold_signals (
  date TEXT, symbol TEXT, signal TEXT, reason TEXT
);
CREATE TABLE IF NOT EXISTS alerts (
  date TEXT, message TEXT, sent INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS gold_returns (
  symbol TEXT, date TEXT, close REAL, prev_close REAL, pct_change REAL,
  pdh REAL, pdl REAL, volume REAL, avg_vol_20 REAL,
  PRIMARY KEY (symbol, date)
);
CREATE TABLE IF NOT EXISTS gold_trend (
  symbol TEXT, date TEXT, sma_fast REAL, sma_slow REAL, trend TEXT,
  PRIMARY KEY (symbol, date)
);
CREATE TABLE IF NOT EXISTS gold_contribution (
  index_name TEXT, date TEXT, symbol TEXT,
  weight REAL, pct_change REAL, contribution REAL,
  PRIMARY KEY (index_name, date, symbol)
);
CREATE TABLE IF NOT EXISTS gold_breadth (
  index_name TEXT, date TEXT,
  advances INTEGER, declines INTEGER, unchanged INTEGER, ad_ratio REAL,
  PRIMARY KEY (index_name, date)
);
CREATE TABLE IF NOT EXISTS gold_relative_strength (
  index_name TEXT, date TEXT, symbol TEXT,
  stock_ret REAL, index_ret REAL, rs REAL, rs_vs_nifty50 REAL,
  PRIMARY KEY (index_name, date, symbol)
);


CREATE TABLE IF NOT EXISTS gold_features (
  symbol TEXT, date TEXT,
  open REAL, high REAL, low REAL, close REAL, prev_close REAL,
  pct_change REAL, gap_pct REAL, ret_from_open REAL,
  pdh REAL, pdl REAL,
  ret_5d REAL, ret_20d REAL, roc REAL,
  sma_20 REAL, sma_50 REAL, ma_alignment TEXT,
  atr REAL, atr_pct REAL,
  volume REAL, rel_volume REAL,
  dist_pdh_pct REAL, dist_pdl_pct REAL,
  PRIMARY KEY (symbol, date)
);
CREATE TABLE IF NOT EXISTS gold_market_trend (
  index_name TEXT, date TEXT, trend TEXT,
  bull_votes INTEGER, bear_votes INTEGER, conditions TEXT,
  PRIMARY KEY (index_name, date)
);
CREATE TABLE IF NOT EXISTS gold_contrib_points (
  index_name TEXT, date TEXT, symbol TEXT,
  weight REAL, pct_change REAL, contrib_pct REAL,
  contrib_pts REAL, share_of_move_pct REAL, rank_pos INTEGER,
  PRIMARY KEY (index_name, date, symbol)
);
CREATE TABLE IF NOT EXISTS gold_contrib_summary (
  index_name TEXT, date TEXT,
  index_pts REAL, explained_pts REAL, explained_pct REAL,
  top_n_pts REAL, top_n_share_pct REAL,
  PRIMARY KEY (index_name, date)
);
CREATE TABLE IF NOT EXISTS gold_breadth_detail (
  index_name TEXT, date TEXT, n INTEGER,
  advances INTEGER, declines INTEGER, unchanged INTEGER,
  adv_pct REAL, dec_pct REAL, unch_pct REAL, ad_ratio REAL,
  pct_above_open REAL, pct_above_sma20 REAL, pct_above_sma50 REAL,
  index_pct REAL, divergence TEXT, narrow_flag TEXT,
  PRIMARY KEY (index_name, date)
);
CREATE TABLE IF NOT EXISTS gold_rs_multi (
  symbol TEXT, date TEXT, period INTEGER, benchmark TEXT,
  stock_ret REAL, bench_ret REAL, rs REAL, rs_z REAL,
  PRIMARY KEY (symbol, date, period, benchmark)
);
CREATE TABLE IF NOT EXISTS gold_levels (
  symbol TEXT, date TEXT,
  open REAL, close REAL, prev_close REAL, pdh REAL, pdl REAL,
  status TEXT, dist_pdh_pct REAL, dist_pdl_pct REAL, rel_volume REAL,
  event TEXT, confirmed INTEGER,
  PRIMARY KEY (symbol, date)
);
CREATE TABLE IF NOT EXISTS gold_candidates (
  symbol TEXT, date TEXT, sector TEXT,
  bull_score REAL, bear_score REAL, max_score INTEGER, data_status TEXT,
  bull_components TEXT, bull_against TEXT,
  bear_components TEXT, bear_against TEXT,
  PRIMARY KEY (symbol, date)
);
CREATE TABLE IF NOT EXISTS gold_rankings (
  date TEXT, ranking_name TEXT, index_name TEXT, rank_pos INTEGER,
  symbol TEXT, value REAL, detail TEXT
);