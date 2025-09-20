# streamlit_app.py
"""
Simple Streamlit app (single-file).
Features:
- Upload CSV or use sample data
- Preview dataframe and basic stats
- Choose columns to plot (scatter) and show linear trendline
- Filter rows by numeric range
- Download filtered data as CSV
"""

import io
import base64
from typing import Tuple

import numpy as np
import pandas as pd
import streamlit as st
import altair as alt

st.set_page_config(page_title="Simple Streamlit Demo", layout="wide")

# ---- Helper functions ----
@st.cache_data
def load_sample_data(n=200) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    x = rng.normal(loc=50, scale=15, size=n)
    noise = rng.normal(scale=8, size=n)
    # simple relation y = 0.7*x + 10 + noise
    y = 0.7 * x + 10 + noise
    cat = rng.choice(["A", "B", "C"], size=n)
    df = pd.DataFrame({"x": x.round(2), "y": y.round(2), "category": cat})
    df["id"] = np.arange(1, n + 1)
    return df[["id", "x", "y", "category"]]

def compute_trendline(x: np.ndarray, y: np.ndarray) -> Tuple[float, float]:
    # returns slope, intercept
    slope, intercept = np.polyfit(x, y, 1)
    return slope, intercept

def df_to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")

def get_download_link(df: pd.DataFrame, filename="data.csv") -> str:
    b = df_to_csv_bytes(df)
    b64 = base64.b64encode(b).decode()
    href = f"data:file/csv;base64,{b64}"
    return href

# ---- Sidebar ----
st.sidebar.title("Controls")
source = st.sidebar.radio("Data source", ("Sample data", "Upload CSV"))

if source == "Upload CSV":
    uploaded = st.sidebar.file_uploader("Upload a CSV file", type=["csv"])
    if uploaded is not None:
        try:
            df = pd.read_csv(uploaded)
        except Exception as e:
            st.sidebar.error(f"Gagal membaca CSV: {e}")
            df = pd.DataFrame()
    else:
        st.sidebar.info("Belum ada file. Menggunakan sample data sementara.")
        df = load_sample_data()
else:
    df = load_sample_data()

# show small preview in sidebar
st.sidebar.markdown("**Preview (first 5 rows)**")
st.sidebar.dataframe(df.head())

# ---- Main layout ----
st.title("Aplikasi Streamlit Sederhana — Single File")
st.write(
    "Demo: upload CSV atau gunakan data contoh. "
    "Pilih kolom untuk diplot, filter numeric, lihat statistik, dan unduh data."
)

# Data info
st.subheader("Data")
st.write(f"Jumlah baris: {df.shape[0]} — Jumlah kolom: {df.shape[1]}")
st.dataframe(df, use_container_width=True)

# Basic stats
st.subheader("Statistik Ringkas")
st.write(df.describe(include="all"))

# ---- Column selection for plotting ----
numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
if len(numeric_cols) < 2:
    st.info("Butuh minimal 2 kolom numerik untuk membuat scatter plot + trendline.")
else:
    st.subheader("Scatter plot + Trendline")
    col1, col2 = st.columns([1, 1])
    with col1:
        x_col = st.selectbox("X axis (numeric)", numeric_cols, index=0)
    with col2:
        y_col = st.selectbox("Y axis (numeric)", numeric_cols, index=1 if len(numeric_cols) > 1 else 0)

    # Optional category for color
    cat_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()
    color_col = st.selectbox("Optional: color by (categorical)", [None] + cat_cols)

    # Filtering by numeric range (on chosen X)
    st.markdown("**Filter baris berdasarkan rentang X**")
    min_x, max_x = float(df[x_col].min()), float(df[x_col].max())
    range_sel = st.slider("X range", min_value=min_x, max_value=max_x, value=(min_x, max_x))
    df_filtered = df[(df[x_col] >= range_sel[0]) & (df[x_col] <= range_sel[1])]

    st.write(f"Menampilkan {len(df_filtered)} baris setelah filter.")

    # Plot with Altair
    base = alt.Chart(df_filtered).mark_point(size=60).encode(
        x=alt.X(x_col, title=x_col),
        y=alt.Y(y_col, title=y_col),
        tooltip=list(df.columns),
    )
    if color_col:
        base = base.encode(color=color_col)

    # trendline calculation
    try:
        slope, intercept = compute_trendline(df_filtered[x_col].to_numpy(), df_filtered[y_col].to_numpy())
        # create trendline data
        x_vals = np.array([df_filtered[x_col].min(), df_filtered[x_col].max()])
        y_vals = slope * x_vals + intercept
        trend_df = pd.DataFrame({x_col: x_vals, y_col: y_vals})
        trend = alt.Chart(trend_df).mark_line().encode(x=x_col, y=y_col)
        chart = (base + trend).interactive().properties(height=450)
    except Exception as e:
        st.warning(f"Gagal menghitung trendline: {e}")
        chart = base.interactive().properties(height=450)

    st.altair_chart(chart, use_container_width=True)
    st.markdown(f"Trendline: slope = **{slope:.4f}**, intercept = **{intercept:.4f}**")

# ---- Simple row filter by category (if exists) ----
if cat_cols:
    st.subheader("Filter Kategori")
    for c in cat_cols:
        vals = df[c].unique().tolist()
        chosen = st.multiselect(f"Pilih nilai untuk kolom `{c}` (kosong = semua)", options=vals, default=vals)
        if chosen:
            df = df[df[c].isin(chosen)]

# ---- Download / Export ----
st.subheader("Download Data")
st.write("Unduh data yang saat ini tampil (CSV).")
csv_bytes = df_to_csv_bytes(df)
st.download_button(
    label="Download CSV",
    data=csv_bytes,
    file_name="data_export.csv",
    mime="text/csv",
)

# Also provide raw view and simple transform example
st.subheader("Contoh Transformasi: Tambah Kolom Baru")
if st.button("Tambah kolom x_plus_y (x + y) bila ada"):
    if {"x", "y"}.issubset(df.columns):
        df["x_plus_y"] = df["x"] + df["y"]
        st.success("Kolom 'x_plus_y' ditambahkan.")
        st.dataframe(df.head())
    else:
        st.error("Kolom 'x' dan/atau 'y' tidak ditemukan di tabel saat ini.")

st.sidebar.markdown("---")
st.sidebar.write("Made with ❤️ — Streamlit demo")
