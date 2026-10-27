"""Streamlit dashboard. Reads the mart/clean tables from PostgreSQL; if the database
is not reachable it falls back to the CSVs in data/processed (written by the pipeline).

Run:  streamlit run app/dashboard.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.analysis import annuity_payment  # noqa: E402
from src.config import ASSUMPTIONS, PROCESSED_DIR, database_url  # noqa: E402

SERIES = {"brno": "#eb6834", "praha": "#2a78d6", "cr": "#1baf7a"}
AGG_LABEL = {"brno": "Brno", "praha": "Prague", "cr": "Czech Republic"}
BLUE = "#2a78d6"

st.set_page_config(page_title="Brno Real Estate Analysis", layout="wide")

TABLES = {
    "rent_map": ("clean.rent_map", "clean_rent_map.csv"),
    "rent_trend": ("mart.rent_trend", "mart_rent_trend.csv"),
    "okres": ("mart.okres_price_growth", "mart_okres_price_growth.csv"),
    "index_q": ("clean.price_index_q", "clean_price_index_q.csv"),
    "coefs": ("mart.regression_coefficients", "regression_coefficients.csv"),
    "diag": ("mart.model_diagnostics", "model_diagnostics.csv"),
    "premiums": ("mart.location_premiums", "location_premiums.csv"),
    "yields": ("mart.district_yields", "district_yields.csv"),
    "afford": ("mart.affordability", "affordability.csv"),
    "regimes": ("mart.rent_trend_regimes", "rent_trend_regimes.csv"),
    "cleaning": ("mart.cleaning_log", "cleaning_log.csv"),
}


@st.cache_data(ttl=600)
def load_all() -> tuple[dict[str, pd.DataFrame], str]:
    try:
        from sqlalchemy import create_engine, text

        engine = create_engine(database_url(), connect_args={"connect_timeout": 3})
        with engine.connect() as conn:
            data = {
                k: pd.read_sql(text(f"SELECT * FROM {t}"), conn) for k, (t, _) in TABLES.items()
            }
        source = "PostgreSQL"
    except Exception:  # noqa: BLE001 - any DB problem -> use the files
        missing = [f for _, f in TABLES.values() if not (PROCESSED_DIR / f).exists()]
        if missing:
            st.error("No database and no processed files. Run `python -m src.pipeline` first.")
            st.stop()
        data = {k: pd.read_csv(PROCESSED_DIR / f) for k, (_, f) in TABLES.items()}
        source = "data/processed CSV files (database not reachable)"
    for key in ("rent_trend", "index_q"):
        data[key]["period"] = pd.to_datetime(data[key]["period"])
    return data, source


def style(fig: go.Figure, height: int = 420) -> go.Figure:
    fig.update_layout(
        height=height,
        margin=dict(l=10, r=10, t=40, b=10),
        legend=dict(orientation="h", y=1.08, x=0, title=None),
        hovermode="x unified" if fig.data and fig.data[0].type == "scatter" else "closest",
    )
    fig.update_xaxes(showgrid=False)
    return fig


data, source = load_all()
rent = data["rent_map"]
okres = data["okres"]
brno_prices = okres[okres["area_name"] == "Brno-město"].set_index("year")["price_kc_m2"]
price_2025 = float(brno_prices[2025])
price_2024 = float(brno_prices[2024])

st.title("Brno Real Estate Market Analysis")
st.caption(
    "Asking rents: MF ČR rent map (offer prices, edition 2026-08). Sale prices: ČSÚ realised "
    f"transaction prices (okres level, latest 2025). Data source for this page: {source}."
)

tab_over, tab_dist, tab_trend, tab_model, tab_buy, tab_data = st.tabs(
    ["Overview", "Districts", "Trends", "Regression", "Rent vs buy & affordability", "Data quality"]
)

# ------------------------------------------------------------------ overview
with tab_over:
    afford = data["afford"]
    latest = afford.iloc[-1]
    two = rent[(rent["area_type"] == "city_district") & (rent["size_key"] == 2)]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(
        "Brno-město transaction price 2025",
        f"{price_2025:,.0f} Kč/m²".replace(",", " "),
        f"{(price_2025 / price_2024 - 1) * 100:+.1f} % vs 2024",
    )
    c2.metric(
        "Median district asking rent, 2-room",
        f"{two['rent_kc_m2_month'].median():.0f} Kč/m²/month",
        f"{two['yoy_pct'].median():+.1f} % yoy (median)",
    )
    c3.metric(
        "Average flat (63 m²) in years of gross wage",
        f"{afford.iloc[1]['price_to_income_1_earner']:.1f} years",
        "one earner, 2025",
        delta_color="off",
    )
    c4.metric(
        "Mortgage payment, 80 % LTV, 30 y",
        f"{latest['monthly_payment_kc']:,.0f} Kč".replace(",", " "),
        f"at {latest['rate_pct']:.2f} % ({ASSUMPTIONS.rate_latest_period})",
        delta_color="off",
    )
    st.markdown(
        "- **Rents by district** differ by about ±10 % around the median; the spread between flat "
        "sizes (per m²) is much larger than the spread between locations.\n"
        "- **Prices**: Brno-město is the most expensive okres in South Moravia, 22 % above the "
        "regional average in 2025.\n"
        "- **Rent vs buy**: buying at the 2025 average Brno price yields roughly 2.5-4.5 % gross "
        "from asking rents, i.e. 22-41 years of gross rent to repay the price.\n"
        "- Offer rents are not paid rents, and okres-level prices hide district differences. "
        "See the *Data quality* tab and the README limitations."
    )

# ------------------------------------------------------------------ districts
with tab_dist:
    level = st.radio(
        "Level", ["City districts (městské části)", "Cadastral areas"], horizontal=True
    )
    area_type = "city_district" if level.startswith("City") else "cadastral_area"
    size_label = st.selectbox("Flat size", sorted(rent["size_label"].unique()), index=1)
    d = rent[(rent["area_type"] == area_type) & (rent["size_label"] == size_label)]
    d = d.sort_values("rent_kc_m2_month")
    fig = px.bar(
        d,
        x="rent_kc_m2_month",
        y="area_name",
        orientation="h",
        color_discrete_sequence=[BLUE],
        hover_data={"yoy_pct": ":.1f", "rent_flat_month_kc": ":,.0f"},
        labels={
            "rent_kc_m2_month": "Kč per m² per month",
            "area_name": "",
            "yoy_pct": "yoy %",
            "rent_flat_month_kc": "whole flat, Kč/month",
        },
    )
    fig.add_vline(
        x=d["rent_kc_m2_month"].median(),
        line_dash="dash",
        line_color="#52514e",
        annotation_text="median",
    )
    st.plotly_chart(style(fig, height=max(420, 18 * len(d))), use_container_width=True)
    st.dataframe(
        d[
            [
                "area_name",
                "rent_kc_m2_month",
                "yoy_pct",
                "rent_kc_m2_month_prev_year",
                "rent_flat_month_kc",
                "is_outlier",
            ]
        ].sort_values("rent_kc_m2_month", ascending=False),
        hide_index=True,
        use_container_width=True,
    )
    st.subheader("South Moravian districts: transaction prices (ČSÚ)")
    w = (
        okres[okres["area_level"] == "okres"]
        .pivot(index="area_name", columns="year", values="price_kc_m2")
        .reset_index()
    )
    w.columns = [str(c) for c in w.columns]
    w["growth_2023_2025_pct"] = (w["2025"] / w["2023"] - 1) * 100
    st.dataframe(
        w.sort_values("2025", ascending=False).round(1), hide_index=True, use_container_width=True
    )

# ------------------------------------------------------------------ trends
with tab_trend:
    size_label_t = st.selectbox(
        "Flat size ", sorted(data["rent_trend"]["size_label"].unique()), index=1
    )
    rt = data["rent_trend"][data["rent_trend"]["size_label"] == size_label_t].copy()
    rt["city"] = rt["aggregate"].map(AGG_LABEL)
    fig = px.line(
        rt,
        x="period",
        y="rent_kc_m2_month",
        color="city",
        color_discrete_map={AGG_LABEL[k]: v for k, v in SERIES.items()},
        labels={"rent_kc_m2_month": "Kč per m² per month", "period": ""},
    )
    fig.add_vrect(
        x0="2022-08-01",
        x1="2023-11-01",
        fillcolor="#e4e3df",
        opacity=0.5,
        line_width=0,
        annotation_text="stagnation",
    )
    st.plotly_chart(style(fig), use_container_width=True)
    st.caption("Annualised growth of Brno asking rents by regime (piecewise trend, HAC SEs):")
    st.dataframe(data["regimes"].round(2), hide_index=True, use_container_width=True)
    idx = data["index_q"]
    fig2 = px.line(
        idx,
        x="period",
        y="index_2015_100",
        color="area_name",
        color_discrete_sequence=[BLUE, "#eb6834", "#1baf7a"],
        labels={"index_2015_100": "index 2015 = 100", "period": "", "area_name": ""},
    )
    st.subheader("Apartment transaction price index (ČSÚ, 2015 = 100)")
    st.plotly_chart(style(fig2), use_container_width=True)

# ------------------------------------------------------------------ regression
with tab_model:
    st.markdown(
        "**Model:** `log(rent per m²) = β0 + β·size dummies + γ·cadastral-area fixed effects + ε`, "
        "OLS with HC3 robust standard errors, n = 192 (48 areas × 4 sizes). A coefficient b on a "
        "dummy means rent per m² is (e^b − 1)·100 % different from a 1-room flat in the same area."
    )
    st.dataframe(data["diag"].round(4), hide_index=True, use_container_width=True)
    coefs = data["coefs"]
    show = coefs[~coefs["term"].str.startswith("C(area_name)")]
    model = st.selectbox("Model", show["model"].unique())
    st.dataframe(
        show[show["model"] == model].drop(columns=["model"]).round(4),
        hide_index=True,
        use_container_width=True,
    )
    prem = data["premiums"].sort_values("location_effect_pct")
    fig = px.bar(
        prem,
        x="location_effect_pct",
        y="area_name",
        orientation="h",
        color=np.where(prem["location_effect_pct"] < 0, "below median", "above median"),
        color_discrete_map={"below median": "#eb6834", "above median": BLUE},
        labels={
            "location_effect_pct": "% vs median area, same flat size",
            "area_name": "",
            "color": "",
        },
    )
    st.subheader("Location premium by cadastral area")
    st.plotly_chart(style(fig, height=900), use_container_width=True)

# ------------------------------------------------------------------ rent vs buy
with tab_buy:
    st.subheader("Gross yield if you paid the Brno-město 2025 average price")
    st.caption(
        f"Price {price_2025:,.0f}".replace(",", " ")
        + " Kč/m² for every district (no open district sale prices exist); rent = asking "
        "rent 2025-08. Gross = before costs, vacancy, tax."
    )
    y = data["yields"]
    pick = st.selectbox("Flat size  ", sorted(y["size_label"].unique()), index=1)
    yy = y[y["size_label"] == pick].sort_values("gross_yield_pct")
    fig = px.bar(
        yy,
        x="gross_yield_pct",
        y="area_name",
        orientation="h",
        color_discrete_sequence=[BLUE],
        hover_data={"payback_years": ":.1f"},
        labels={"gross_yield_pct": "gross yield %", "area_name": ""},
    )
    st.plotly_chart(style(fig, height=650), use_container_width=True)

    st.subheader("Mortgage calculator")
    c1, c2, c3 = st.columns(3)
    m2 = c1.slider("Flat size (m²)", 30, 120, int(ASSUMPTIONS.avg_flat_m2))
    price_m2 = c1.number_input("Price per m² (Kč)", 30000, 250000, int(price_2025), step=1000)
    rate = c2.slider("Interest rate (%)", 2.0, 8.0, float(ASSUMPTIONS.rate_latest_pct), 0.05)
    ltv = c2.slider("Loan-to-value", 0.5, 0.9, float(ASSUMPTIONS.ltv), 0.05)
    years = c3.slider("Term (years)", 10, 35, ASSUMPTIONS.term_years)
    wage = c3.number_input(
        "Gross monthly wage per earner (Kč)",
        20000,
        200000,
        int(data["afford"].iloc[-1]["monthly_gross_wage_kc"]),
        step=500,
    )
    earners = c3.radio("Earners", [1, 2], horizontal=True, index=1)
    price = m2 * price_m2
    payment = annuity_payment(price * ltv, rate, years)
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Price", f"{price:,.0f} Kč".replace(",", " "))
    k2.metric("Down payment", f"{price * (1 - ltv):,.0f} Kč".replace(",", " "))
    k3.metric("Monthly payment", f"{payment:,.0f} Kč".replace(",", " "))
    k4.metric("Share of gross household wage", f"{payment / (wage * earners) * 100:.1f} %")
    st.caption("Shares use gross wages; the burden on net (take-home) pay is higher.")
    st.dataframe(data["afford"].round(2), hide_index=True, use_container_width=True)

# ------------------------------------------------------------------ data quality
with tab_data:
    st.markdown("Every cleaning step and how many rows it removed:")
    st.dataframe(data["cleaning"], hide_index=True, use_container_width=True)
    flagged = rent[rent["is_outlier"]]
    st.markdown(
        f"Outlier rule: |modified z| > 3.5 on log rent within flat size and level → "
        f"**{len(flagged)} rows flagged, none dropped** (model M3 re-fits without them)."
    )
    st.dataframe(
        flagged[["area_type", "area_name", "size_label", "rent_kc_m2_month", "robust_z"]],
        hide_index=True,
        use_container_width=True,
    )
