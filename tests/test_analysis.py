"""Tests for analysis math and the model code (synthetic data is labelled as such)."""

import numpy as np
import pandas as pd
import pytest

from src.analysis import (
    affordability_table,
    annuity_payment,
    fit_rent_models,
    fit_rent_trend,
    gross_yield,
    payback_years,
)
from src.ingest import read_raw
from src.transform import build_clean


def test_annuity_payment_known_value():
    # textbook value: 1,000,000 at 6 % for 30 years -> 5,995.51 per month
    assert annuity_payment(1_000_000, 6.0, 30) == pytest.approx(5995.51, abs=0.01)


def test_annuity_payment_zero_rate_and_validation():
    assert annuity_payment(360_000, 0.0, 30) == pytest.approx(1000.0)
    with pytest.raises(ValueError):
        annuity_payment(100, 5.0, 0)


def test_gross_yield_and_payback():
    y = gross_yield(300 * 12, 100_000)
    assert y == pytest.approx(0.036)
    assert payback_years(y) == pytest.approx(27.78, abs=0.01)


def test_affordability_table_ratios():
    t = affordability_table(100_000, 50, 50_000, {"x": 5.0}, rent_kc_m2_month=300)
    row = t.iloc[0]
    assert row["price_kc"] == 5_000_000
    assert row["loan_kc"] == 4_000_000
    assert row["price_to_income_1_earner"] == pytest.approx(5_000_000 / 600_000)
    assert row["price_to_income_2_earners"] == pytest.approx(row["price_to_income_1_earner"] / 2)
    assert row["rent_same_flat_kc"] == 15_000


def _synthetic_rent_map(seed: int = 42) -> pd.DataFrame:
    """SYNTHETIC: 20 areas x 4 sizes with known size effects (-20 %, -30 %, -35 %)."""
    rng = np.random.default_rng(seed)
    effects = {1: 0.0, 2: np.log(0.80), 3: np.log(0.70), 4: np.log(0.65)}
    labels = {1: "1+kk/1+1", 2: "2+kk/2+1", 3: "3+kk/3+1", 4: "4+ rooms"}
    rows = []
    for a in range(20):
        loc = rng.normal(0, 0.05)
        for k in range(1, 5):
            log_rent = np.log(350) + effects[k] + loc + rng.normal(0, 0.01)
            rows.append(
                {
                    "area_type": "cadastral_area",
                    "area_name": f"Area {a:02d}",
                    "size_key": k,
                    "size_label": labels[k],
                    "rent_kc_m2_month": float(np.exp(log_rent)),
                    "is_outlier": False,
                }
            )
    return pd.DataFrame(rows)


def test_rent_model_recovers_known_size_effects():
    models = fit_rent_models(_synthetic_rent_map())
    m2 = models[1]
    eff = m2.coefs.set_index("term")["effect_pct"]
    assert eff.filter(like="2+kk").iloc[0] == pytest.approx(-20, abs=1.5)
    assert eff.filter(like="3+kk").iloc[0] == pytest.approx(-30, abs=1.5)
    assert eff.filter(like="4+").iloc[0] == pytest.approx(-35, abs=1.5)
    assert m2.r2 > models[0].r2  # location fixed effects add explanatory power
    assert m2.diagnostics["location_wald_p"] < 0.01


def test_trend_model_recovers_regimes():
    """SYNTHETIC: +2 %/quarter, then flat, then +1 %/quarter (31 editions like the MF data)."""
    periods = pd.date_range("2019-02-01", periods=31, freq="3MS")
    t = np.arange(31)
    k1 = int((periods < "2022-08-01").sum())
    k2 = int((periods < "2023-11-01").sum())
    log_r = np.log(200) + 0.02 * t - 0.02 * np.clip(t - k1, 0, None)
    log_r += 0.01 * np.clip(t - k2, 0, None)
    hist = pd.DataFrame(
        {"aggregate": "brno", "size_key": 2, "period": periods, "rent_kc_m2_month": np.exp(log_r)}
    )
    res = fit_rent_trend(hist)
    assert res.diagnostics["annual_growth_pct_regime1"] == pytest.approx(8.33, abs=0.05)
    assert res.diagnostics["annual_growth_pct_regime2"] == pytest.approx(0.0, abs=0.05)
    assert res.diagnostics["annual_growth_pct_regime3"] == pytest.approx(4.06, abs=0.05)


def test_real_data_cleaning_shapes():
    clean, log = build_clean(read_raw())
    rent = clean["rent_map"]
    # 48 cadastral areas + 29 city districts, each x 4 sizes
    assert (rent["area_type"] == "cadastral_area").sum() == 48 * 4
    assert (rent["area_type"] == "city_district").sum() == 29 * 4
    assert rent["rent_kc_m2_month"].notna().all()
    assert clean["rent_history"].groupby("aggregate").size().eq(31 * 4).all()
    assert len(clean["okres_prices"]) == 30
    assert log.to_frame()["rows_removed"].ge(0).all()
