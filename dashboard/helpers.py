import sys, pathlib
from datetime import datetime, timezone, timedelta
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import pandas as pd
import streamlit as st
from src.db import get_conn, load_config


@st.cache_data(ttl=600)
def q(sql, params=()):
    
    conn = get_conn()
    try:
        return pd.read_sql(sql, conn, params=params)
    finally:
        conn.close()


def index_names():
    return list(load_config()["indices"].keys())


def index_symbol(name):
    return load_config()["indices"][name]["yf_symbol"]


def latest_date():
    return q("SELECT MAX(date) AS d FROM gold_returns")["d"][0]

def data_banner():
    ist = datetime.now(timezone(timedelta(hours=5, minutes=30)))
    last = latest_date()
    mins = ist.hour * 60 + ist.minute
    if last == ist.strftime("%Y-%m-%d") and ist.weekday() < 5 and mins < 15 * 60 + 45:
        st.warning(f"{last} is PROVISIONAL: market is still open, so price and "
                   "volume are partial. Re-run the pipeline after 4 PM IST.")
    else:
        st.success(f"Data confirmed up to {last} (completed trading day).")