"""Static PNG charts for the README / report (matplotlib, light theme).

Palette: validated categorical slots 1-3 (blue, orange, aqua) in fixed order;
one hue (blue) for single-series charts; text always in neutral ink."""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src.config import FIGURES_DIR  # noqa: E402

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
GRID = "#e4e3df"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a"]
AGG_LABEL = {"brno": "Brno", "praha": "Prague", "cr": "Czech Republic"}


def _style(ax, title: str, subtitle: str | None = None) -> None:
    ax.set_facecolor(SURFACE)
    ax.figure.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=INK_2, labelsize=9)
    ax.grid(color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    ax.set_title(title, loc="left", color=INK, fontsize=12, fontweight="bold", pad=22)
    if subtitle:
        ax.text(0, 1.02, subtitle, transform=ax.transAxes, color=INK_2, fontsize=9)


def _save(fig, name: str) -> None:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / name, dpi=150, facecolor=SURFACE)
    plt.close(fig)


def district_rent(rent_map: pd.DataFrame) -> None:
    d = rent_map[(rent_map["area_type"] == "city_district") & (rent_map["size_key"] == 2)]
    d = d.sort_values("rent_kc_m2_month")
    fig, ax = plt.subplots(figsize=(8, 8.5))
    ax.barh(d["area_name"], d["rent_kc_m2_month"], color=SERIES[0], height=0.7)
    med = d["rent_kc_m2_month"].median()
    ax.axvline(med, color=INK_2, linewidth=1, linestyle="--")
    ax.text(med + 2, -1.2, f"median {med:.0f}", color=INK_2, fontsize=8)
    for y, v in enumerate(d["rent_kc_m2_month"]):
        if y in (0, len(d) - 1):
            ax.text(v + 2, y, f"{v:.0f}", va="center", color=INK, fontsize=8)
    ax.set_xlim(0, d["rent_kc_m2_month"].max() * 1.08)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Kč per m² per month", color=INK_2, fontsize=9)
    _style(
        ax,
        "Asking rent by Brno city district, 2-room flats",
        "MF ČR rent map, edition 2026-08; offer prices, "
        "median of the district's cadastral areas",
    )
    _save(fig, "fig1_district_rent.png")


def rent_trend(history: pd.DataFrame) -> None:
    h = history[history["size_key"] == 2]
    fig, ax = plt.subplots(figsize=(9, 4.8))
    for i, agg in enumerate(["praha", "brno", "cr"]):
        s = h[h["aggregate"] == agg].sort_values("period")
        ax.plot(s["period"], s["rent_kc_m2_month"], color=SERIES[i], linewidth=2)
        ax.text(
            s["period"].iloc[-1] + pd.Timedelta(days=40),
            s["rent_kc_m2_month"].iloc[-1],
            f"{AGG_LABEL[agg]} {s['rent_kc_m2_month'].iloc[-1]:.0f}",
            va="center",
            color=INK,
            fontsize=9,
        )
    ax.axvspan(pd.Timestamp("2022-08-01"), pd.Timestamp("2023-11-01"), color=GRID, alpha=0.6)
    ax.text(
        pd.Timestamp("2022-09-15"),
        h["rent_kc_m2_month"].min(),
        "stagnation",
        color=INK_2,
        fontsize=8,
    )
    ax.set_xlim(h["period"].min(), h["period"].max() + pd.Timedelta(days=330))
    ax.set_ylabel("Kč per m² per month", color=INK_2, fontsize=9)
    _style(
        ax,
        "Asking rents, 2-room flats, 2019-2026",
        "MF ČR rent map; median of cadastral-area medians (not an official city figure)",
    )
    _save(fig, "fig2_rent_trend.png")


def price_index(idx_q: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(9, 4.8))
    names = {
        "Hlavní město Praha": "Prague",
        "Jihomoravský kraj": "South Moravian Region",
        "Česká republika": "Czech Republic",
    }
    for i, (area, label) in enumerate(names.items()):
        s = idx_q[idx_q["area_name"] == area].sort_values("period")
        ax.plot(s["period"], s["index_2015_100"], color=SERIES[i], linewidth=2)
        offset = {0: -7, 1: -2, 2: 7}[i]
        ax.text(
            s["period"].iloc[-1] + pd.Timedelta(days=40),
            s["index_2015_100"].iloc[-1] + offset,
            f"{label} {s['index_2015_100'].iloc[-1]:.0f}",
            va="center",
            color=INK,
            fontsize=9,
        )
    ax.set_xlim(idx_q["period"].min(), idx_q["period"].max() + pd.Timedelta(days=760))
    ax.set_ylabel("index, 2015 = 100", color=INK_2, fontsize=9)
    _style(
        ax,
        "Apartment transaction price index, 2015-2025",
        "ČSÚ, table 2-6b (quarterly, 2015 = 100); Brno itself has no published index",
    )
    _save(fig, "fig3_price_index.png")


def size_effect(coefs: pd.DataFrame) -> None:
    c = coefs[(coefs["model"] == "M2 size + location FE") & coefs["term"].str.contains("size")]
    labels = [t.split("[T.")[1].rstrip("]") for t in c["term"]]
    eff = (np.exp(c["coef"]) - 1) * 100
    lo = (np.exp(c["ci_low"]) - 1) * 100
    hi = (np.exp(c["ci_high"]) - 1) * 100
    fig, ax = plt.subplots(figsize=(8, 3.6))
    y = np.arange(len(labels))
    ax.hlines(y, lo, hi, color=SERIES[0], linewidth=2)
    ax.plot(eff, y, "o", color=SERIES[0], markersize=8, markeredgecolor=SURFACE, markeredgewidth=2)
    for yi, e in zip(y, eff, strict=True):
        ax.text(e, yi + 0.22, f"{e:.1f} %", ha="center", color=INK, fontsize=9)
    ax.axvline(0, color=INK_2, linewidth=1)
    ax.set_yticks(y, labels)
    ax.set_xlim(-40, 2)
    ax.set_ylim(-0.6, len(labels) - 0.3)
    ax.set_xlabel(
        "difference in rent per m² vs 1-room flat, same location (95 % CI, HC3)",
        color=INK_2,
        fontsize=9,
    )
    _style(
        ax,
        "Bigger flats rent for less per m²",
        "OLS on log rent with 48 cadastral-area fixed effects, n = 192",
    )
    _save(fig, "fig4_size_effect.png")


def okres_prices(prices: pd.DataFrame, areas: pd.DataFrame) -> None:
    jmk = areas[(areas["region"] == "Jihomoravský kraj") & (areas["area_level"] == "okres")]
    p = prices[prices["area_name"].isin(jmk["area_name"])]
    w = p.pivot(index="area_name", columns="year", values="price_kc_m2").sort_values(2025)
    fig, ax = plt.subplots(figsize=(8, 4.2))
    y = np.arange(len(w))
    ax.barh(y, w[2025], color=SERIES[0], height=0.6, label="2025")
    ax.plot(w[2023], y, "|", color=INK, markersize=14, markeredgewidth=2, label="2023")
    for yi, (v25, v23) in enumerate(zip(w[2025], w[2023], strict=True)):
        ax.text(
            v25 + 1200,
            yi,
            f"{v25:,.0f}  (+{(v25 / v23 - 1) * 100:.0f} % vs 2023)".replace(",", " "),
            va="center",
            color=INK,
            fontsize=8,
        )
    ax.set_yticks(y, w.index)
    ax.set_xlim(0, w[2025].max() * 1.35)
    ax.grid(axis="y", visible=False)
    ax.legend(frameon=False, fontsize=8, loc="lower right", labelcolor=INK_2)
    ax.set_xlabel("average transaction price, Kč per m²", color=INK_2, fontsize=9)
    _style(
        ax,
        "Brno-město vs the rest of South Moravia",
        "ČSÚ, Ceny nemovitostí 2023-2025, table 2-4 (realised prices from the cadastre)",
    )
    _save(fig, "fig5_okres_prices.png")


def location_effects(prem: pd.DataFrame) -> None:
    p = prem.sort_values("location_effect_pct")
    fig, ax = plt.subplots(figsize=(8, 9))
    colors = [SERIES[1] if v < 0 else SERIES[0] for v in p["location_effect_pct"]]
    ax.barh(p["area_name"], p["location_effect_pct"], color=colors, height=0.7)
    ax.axvline(0, color=INK_2, linewidth=1)
    ax.grid(axis="y", visible=False)
    ax.tick_params(axis="y", labelsize=8)
    ax.set_xlabel("% vs median area, same flat size (model M2)", color=INK_2, fontsize=9)
    _style(
        ax,
        "Location premium by cadastral area",
        "Fixed effects from log-rent OLS; asking rents 2026-08",
    )
    _save(fig, "fig6_location_effects.png")


def make_all(clean: dict, outputs: dict) -> None:
    district_rent(clean["rent_map"])
    rent_trend(clean["rent_history"])
    price_index(clean["price_index_q"])
    size_effect(outputs["regression_coefficients"])
    okres_prices(clean["okres_prices"], clean["okres_areas"])
    location_effects(outputs["location_premiums"])
