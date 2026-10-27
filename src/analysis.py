"""Analysis helpers: OLS models, rent-vs-buy and affordability math."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
from statsmodels.stats.diagnostic import het_breuschpagan, linear_reset
from statsmodels.stats.stattools import durbin_watson, jarque_bera

from src.config import ASSUMPTIONS, Assumptions

# ---------------------------------------------------------------- finance


def annuity_payment(principal: float, annual_rate_pct: float, years: int) -> float:
    """Monthly payment of a fixed-rate annuity mortgage.
    M = P * r / (1 - (1 + r)^-n), r = monthly rate, n = months. r == 0 -> P / n."""
    if principal < 0 or years <= 0:
        raise ValueError("principal must be >= 0 and years > 0")
    n = years * 12
    r = annual_rate_pct / 100 / 12
    if r == 0:
        return principal / n
    return principal * r / (1 - (1 + r) ** -n)


def gross_yield(annual_rent: float | pd.Series, price: float | pd.Series):
    """Gross rental yield = annual rent / purchase price (no costs, vacancy or tax)."""
    return annual_rent / price


def payback_years(yield_fraction: float | pd.Series):
    """Years of gross rent needed to repay the price = 1 / gross yield."""
    return 1 / yield_fraction


# ---------------------------------------------------------------- rent model


@dataclass
class ModelResult:
    name: str
    formula: str
    n: int
    r2: float
    adj_r2: float
    coefs: pd.DataFrame
    diagnostics: dict
    summary_text: str


def _coef_table(res) -> pd.DataFrame:
    ci = res.conf_int()
    tbl = pd.DataFrame(
        {
            "term": res.params.index,
            "coef": res.params.values,
            "std_err_hc3": res.bse.values,
            "p_value": res.pvalues.values,
            "ci_low": ci[0].values,
            "ci_high": ci[1].values,
        }
    )
    # log-linear model: effect of a dummy in % = exp(b) - 1
    # only meaningful for 0/1 dummies (C(...)[T.x] terms), NaN otherwise
    is_dummy = tbl["term"].str.contains("[T.", regex=False)
    tbl["effect_pct"] = np.where(is_dummy, (np.exp(tbl["coef"]) - 1) * 100, np.nan)
    return tbl.reset_index(drop=True)


def _diagnostics(res) -> dict:
    bp_lm, bp_p, _, _ = het_breuschpagan(res.resid, res.model.exog)
    jb, jb_p, skew, kurt = jarque_bera(res.resid)
    out = {
        "breusch_pagan_p": float(bp_p),
        "jarque_bera_p": float(jb_p),
        "residual_skew": float(skew),
        "residual_kurtosis": float(kurt),
        "condition_number": float(res.condition_number),
    }
    try:
        out["reset_p"] = float(linear_reset(res, power=2, use_f=True).pvalue)
    except (ValueError, np.linalg.LinAlgError):
        out["reset_p"] = float("nan")
    return out


def rent_model_frame(rent_map: pd.DataFrame) -> pd.DataFrame:
    """Regression sample: cadastral areas only (city-district rows are medians of
    the same cadastral areas, so using both would double count)."""
    df = rent_map[rent_map["area_type"] == "cadastral_area"].copy()
    df["log_rent"] = np.log(df["rent_kc_m2_month"])
    df["size"] = df["size_label"]
    return df


def fit_rent_models(rent_map: pd.DataFrame) -> list[ModelResult]:
    """M1: log rent ~ flat size. M2: + cadastral-area fixed effects (location).
    M3: M2 without flagged outliers (robustness). All with HC3 robust SEs."""
    df = rent_model_frame(rent_map)
    base = "C(size, Treatment('1+kk/1+1'))"
    specs = [
        ("M1 size only", f"log_rent ~ {base}", df),
        ("M2 size + location FE", f"log_rent ~ {base} + C(area_name)", df),
        ("M3 = M2 without outliers", f"log_rent ~ {base} + C(area_name)", df[~df["is_outlier"]]),
    ]
    results = []
    for name, formula, data in specs:
        res = smf.ols(formula, data=data).fit(cov_type="HC3")
        diag = _diagnostics(res)
        if "area_name" in formula:
            # robust Wald test: are location effects jointly zero?
            names = [p for p in res.params.index if p.startswith("C(area_name)")]
            restriction = np.zeros((len(names), len(res.params)))
            for i, p in enumerate(names):
                restriction[i, list(res.params.index).index(p)] = 1
            wald = res.wald_test(restriction, scalar=True)
            diag["location_wald_F"] = float(wald.statistic)
            diag["location_wald_p"] = float(wald.pvalue)
        results.append(
            ModelResult(
                name=name,
                formula=formula,
                n=int(res.nobs),
                r2=float(res.rsquared),
                adj_r2=float(res.rsquared_adj),
                coefs=_coef_table(res),
                diagnostics=diag,
                summary_text=res.summary().as_text(),
            )
        )
    return results


def location_premiums(rent_map: pd.DataFrame) -> pd.DataFrame:
    """Location effect of each cadastral area from M2, re-centred on the median area:
    '% above/below a typical Brno area for the same flat size'."""
    df = rent_model_frame(rent_map)
    res = smf.ols("log_rent ~ C(size) + C(area_name) - 1", data=df).fit()
    # with -1 the size dummies absorb the intercept; area effects relative to baseline
    eff = {name: 0.0 for name in df["area_name"].unique()}
    for p, v in res.params.items():
        if p.startswith("C(area_name)[T."):
            eff[p[len("C(area_name)[T.") : -1]] = v
    s = pd.Series(eff)
    s = s - s.median()
    out = pd.DataFrame({"area_name": s.index, "location_effect_pct": (np.exp(s.values) - 1) * 100})
    return out.sort_values("location_effect_pct", ascending=False).reset_index(drop=True)


# ---------------------------------------------------------------- trend model


def fit_rent_trend(
    history: pd.DataFrame,
    aggregate: str = "brno",
    size_key: int = 2,
    knots: tuple[str, str] = ("2022-08-01", "2023-11-01"),
) -> ModelResult:
    """Piecewise-linear trend in log rent with Newey-West (HAC) SEs, 4 lags.

    Three regimes: before knot1, between knots (post-2022 stagnation), after knot2.
    Slopes are per quarter; annualised growth = exp(4 * slope) - 1."""
    df = history[(history["aggregate"] == aggregate) & (history["size_key"] == size_key)]
    df = df.sort_values("period").reset_index(drop=True)
    t = np.arange(len(df), dtype=float)
    k1 = int((df["period"] < pd.Timestamp(knots[0])).sum())
    k2 = int((df["period"] < pd.Timestamp(knots[1])).sum())
    X = pd.DataFrame(
        {
            "t": t,
            "after_knot1": np.clip(t - k1, 0, None),
            "after_knot2": np.clip(t - k2, 0, None),
        }
    )
    X = sm.add_constant(X)
    y = np.log(df["rent_kc_m2_month"].astype(float))
    res = sm.OLS(y, X).fit(cov_type="HAC", cov_kwds={"maxlags": 4})
    slopes = {
        "slope_regime1": res.params["t"],
        "slope_regime2": res.params["t"] + res.params["after_knot1"],
        "slope_regime3": res.params["t"] + res.params["after_knot1"] + res.params["after_knot2"],
    }
    annual = {
        k.replace("slope", "annual_growth_pct"): (np.exp(4 * v) - 1) * 100
        for k, v in slopes.items()
    }
    diag = {
        "durbin_watson": float(durbin_watson(res.resid)),
        **annual,
        "regime1": f"{df['period'].iloc[0]:%Y-%m}..{df['period'].iloc[k1 - 1]:%Y-%m}",
        "regime2": f"{df['period'].iloc[k1]:%Y-%m}..{df['period'].iloc[k2 - 1]:%Y-%m}",
        "regime3": f"{df['period'].iloc[k2]:%Y-%m}..{df['period'].iloc[-1]:%Y-%m}",
    }
    tbl = _coef_table(res).rename(columns={"std_err_hc3": "std_err_hac"})
    return ModelResult(
        name=f"Trend {aggregate} size {size_key}",
        formula="log_rent ~ t + hinge1 + hinge2",
        n=int(res.nobs),
        r2=float(res.rsquared),
        adj_r2=float(res.rsquared_adj),
        coefs=tbl,
        diagnostics=diag,
        summary_text=res.summary().as_text(),
    )


# ---------------------------------------------------------------- rent vs buy


def district_yields(rent_map: pd.DataFrame, price_kc_m2: float) -> pd.DataFrame:
    """Gross yield per city district and flat size, using the district rent matched to
    the price year (2025-08, backed out from yoy) and ONE city-wide price, because
    open district-level sale prices do not exist. It is a 'what if you paid the
    Brno average price here' yield, not a measured district yield."""
    df = rent_map[rent_map["area_type"] == "city_district"].copy()
    df["annual_rent_kc_m2"] = df["rent_kc_m2_month_prev_year"] * 12
    df["gross_yield_pct"] = gross_yield(df["annual_rent_kc_m2"], price_kc_m2) * 100
    df["payback_years"] = payback_years(df["gross_yield_pct"] / 100)
    return df[
        [
            "area_name",
            "size_key",
            "size_label",
            "rent_kc_m2_month_prev_year",
            "annual_rent_kc_m2",
            "gross_yield_pct",
            "payback_years",
        ]
    ].reset_index(drop=True)


def affordability_table(
    price_kc_m2: float,
    flat_m2: float,
    monthly_wage: float,
    rates_pct: dict[str, float],
    a: Assumptions = ASSUMPTIONS,
    rent_kc_m2_month: float | None = None,
) -> pd.DataFrame:
    """Price-to-income and mortgage burden for an average flat, one and two earners."""
    price = price_kc_m2 * flat_m2
    loan = price * a.ltv
    rows = []
    for label, rate in rates_pct.items():
        pay = annuity_payment(loan, rate, a.term_years)
        rows.append(
            {
                "scenario": label,
                "rate_pct": rate,
                "flat_m2": flat_m2,
                "price_kc": round(price),
                "down_payment_kc": round(price - loan),
                "loan_kc": round(loan),
                "monthly_payment_kc": round(pay),
                "price_to_income_1_earner": price / (monthly_wage * 12),
                "price_to_income_2_earners": price / (monthly_wage * 24),
                "payment_share_of_gross_wage_1_earner_pct": pay / monthly_wage * 100,
                "payment_share_of_gross_wage_2_earners_pct": pay / (2 * monthly_wage) * 100,
                "down_payment_in_months_of_wage": (price - loan) / monthly_wage,
                "rent_same_flat_kc": None
                if rent_kc_m2_month is None
                else round(rent_kc_m2_month * flat_m2),
            }
        )
    return pd.DataFrame(rows)
