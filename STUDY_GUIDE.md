# Study guide

Plain-language notes for understanding (and defending) every part of this project.

---

## 1. The pipeline in one picture

```
data/raw/*.csv  ──read_raw()──►  raw tables (text, untouched)      schema raw
      │
      ▼  src/transform.py + src/cleaning.py
clean DataFrames ──load_clean()──► typed tables + PK/CHECK          schema clean
      │                                   │
      │                                   ▼ sql/marts.sql
      │                            aggregated tables                schema mart
      ▼  src/analysis.py                  │
models, yields, affordability ──write_mart()──►  mart.*             │
      │                                   ▼ sql/queries/01-10
      ▼                            query results ─► data/processed/query_*.csv
reports/*.md, reports/figures/*.png, data/processed/*.csv
                                          │
                              app/dashboard.py (Postgres, CSV fallback)
```

`python -m src.pipeline` runs all of it (`src/pipeline.py: run()`):

1. **Ingest** (`src/ingest.py`) reads every CSV as strings (`dtype=str`) so nothing is
   silently converted.
2. **Clean** (`src/transform.py`) calls small pure functions from `src/cleaning.py`; each
   step that can remove rows writes to a `CleaningLog` (rows before/after + reason).
3. **Load** (`src/load.py`): raw → `raw` schema with `to_sql(replace)`; `sql/schema.sql`
   creates `clean` tables with types, primary keys and `CHECK` constraints, then data is
   appended in one transaction (if any row breaks a constraint, nothing is loaded).
4. **Marts** (`sql/marts.sql`) are `CREATE TABLE AS` aggregations, rebuilt each run.
5. **Analysis** (`src/analysis.py`) fits models and computes yields/affordability; results
   are written to `mart.*` too, so the dashboard reads one place.
6. **Queries** in `sql/queries/` run and are saved as CSV.
7. **Reports and charts** are regenerated, so numbers in the docs can be checked.

Why three layers? You can always trace a number back: mart ← clean ← raw ← source file.
If a cleaning rule changes, raw does not have to be re-downloaded.

Why does the pipeline run from committed snapshots? Reproducibility: the same input gives
the same output on any machine and in CI. `python -m src.ingest` downloads a fresh rent map
to a new dated file when you want to update.

## 2. The data (and why the plan changed)

- **MF ČR rent map** — the Ministry of Finance estimates "usual" rent per m² for every
  cadastral area from listings using a hedonic model. It is *offer* data, quarterly since
  2019, for four flat sizes. A city district (městská část) value = median of its
  cadastral areas. CC BY 4.0.
- **ČSÚ Ceny nemovitostí** — realised prices from the cadastre (tax returns on transfers),
  average Kč/m² by okres; Brno-město is one okres = the whole city.
- **ČSÚ price index** — 2015 = 100, quarterly, ČR / Praha / kraje.
- **Wages** — ČSÚ average gross monthly wage, Jihomoravský kraj.
- **Mortgage rate** — ČBA Hypomonitor, average agreed rate on new mortgages.

There is no open flat-level dataset with area/floor/condition, and no open sale price by
Brno district. Scraping listings would break portal terms. So: the regression is on rents
(where location detail exists) and sale prices are used at city level.

## 3. Cleaning decisions

| Rule | Why |
|---|---|
| Names: NFC Unicode, unify dashes ("Brno – střed" → "Brno-střed"), collapse spaces, alias table for accent-less spellings | the same district must join to itself across sources |
| Size labels → 1..4 (`5+kk` → 4) | MF has four categories; anything bigger is "4 and more" |
| `parse_czech_number`: spaces/non-breaking spaces as thousands, decimal comma, `x` = suppressed → missing | ČSÚ formatting |
| Missing key fields → **drop, never impute** | a made-up rent or price would be fabricated data |
| Duplicates on the natural key → keep first | a district/size/period must appear once |
| Value ≤ 0 → drop | impossible for a price or rent |
| Outliers: modified z-score on log value within flat size, \|z\| > 3.5 → **flag**, keep | robust (median/MAD) so the outlier does not hide itself; flagging keeps the data honest; model M3 checks sensitivity |
| ČSÚ index: annual average must equal mean of quarters (±0.15) | catches transcription errors |
| 2025 district rent = 2026 rent / (1 + yoy %) | matches rent to the 2025 price year |

Real result: 0 rows removed (official statistics are already clean), 3 rows flagged.
The rules are still tested on synthetic messy examples in `tests/test_cleaning.py`.

## 4. What each SQL query shows

| File | Answers | Techniques |
|---|---|---|
| `01_district_rent_ranking` | rank of city districts by 2-room rent and % vs the median district | CTE, `PERCENTILE_CONT`, `RANK()` |
| `02_size_discount_by_area` | per area, how much cheaper per m² larger flats are than 1-room | conditional aggregation `MAX(...) FILTER (WHERE ...)` (a pivot) |
| `03_rent_yoy_trend` | yoy growth of Brno vs Prague vs ČR per edition | reads `mart.rent_trend` (built with `LAG(…, 4)`), pivot with `FILTER` |
| `04_rent_cagr` | compound annual growth 2019-02 → 2026-08 | `FIRST_VALUE`/`LAST_VALUE` with a full window frame, `POWER` |
| `05_okres_price_growth` | Brno-město vs other South Moravian okresy, growth 2023→2025 | CTEs, `CROSS JOIN` to a one-row CTE, `DENSE_RANK()` |
| `06_price_index_cycle` | peak, trough, drawdown, recovery quarter of the price index | running max (`MAX() OVER (ROWS UNBOUNDED PRECEDING)`), `DISTINCT ON`, self-join |
| `07_rolling_rent_gap_brno_praha` | Brno rent as % of Prague, with a rolling 1-year average | `AVG() OVER (ROWS BETWEEN 3 PRECEDING AND CURRENT ROW)` |
| `08_gross_yield_by_district` | gross yield and payback per district at the city price | CTE + arithmetic |
| `09_affordability_wage_years` | years of gross wage to buy an average flat, 2024 vs 2025 | join prices × areas × wages, regex filter `~ '^\d{4}$'` |
| `10_rent_growth_by_quartile` | do cheap areas grow faster? | `NTILE(4)`, `STDDEV_SAMP` |

Remember: `LAG(x, 4)` = value 4 rows earlier in the window (4 quarterly editions = 1 year).
`RANK` leaves gaps after ties (1,1,3), `DENSE_RANK` does not (1,1,2).

## 5. The regression, step by step

**Model M2:** `log(rent_m2) = β0 + β2·D2 + β3·D3 + β4·D4 + Σ γ_a·Area_a + ε`

- One row = one cadastral area × one flat size (48 × 4 = 192 rows). City-district rows are
  excluded: they are medians of the same areas, so including them would double count.
- `D2, D3, D4` are dummies for 2-, 3-, 4+-room flats; the 1-room flat is the base.
- `Area_a` = 47 dummies (one area is the base) = **location fixed effects**. They absorb
  everything that is constant for an area (distance to centre, transport, building stock).

**Interpreting a coefficient.** Because the left side is a log, a dummy coefficient b means
a percentage difference of `(e^b − 1)·100 %`:
- β2 = −0.2064 → e^−0.2064 − 1 = **−18.7 %**: a 2-room flat's rent per m² is 18.7 % lower
  than a 1-room flat's *in the same area*. (Not per flat — per m². Per flat, a 2-room
  still costs more.)
- β3 = −0.3305 → −28.1 %; β4 = −0.4114 → −33.7 %.
- β0 = 5.88 → e^5.88 ≈ 358 Kč/m² is the fitted 1-room rent in the base area.
- γ_a: % difference of area a vs the base area for the same size. The dashboard re-centres
  them on the median area so they read as "premium vs a typical area".
- Small-b shortcut: b ≈ % change only when |b| < ~0.1; here b is large, so use e^b − 1.

**Fit.** R² = 0.871 for size only (M1), 0.953 with location (M2). Adjusted R² (0.936)
penalises the 47 extra parameters. Location is jointly significant: robust Wald F = 541,
p ≈ 0.

**Why size coefficients are identical in M1 and M2:** every area has all four sizes
(balanced panel), so size dummies are uncorrelated with area dummies → adding areas does not
change the size estimates, only their standard errors (smaller, since the residual noise drops).

**Assumption checks (`reports/regression_report.md`):**
- *Linearity / specification* — RESET test: p = 0.00 for M1 (location is missing → mis-
  specified), p = 0.34 for M2 (fine).
- *Homoskedasticity* — Breusch-Pagan p < 0.001 for M2 → variance differs across areas/sizes
  → use **HC3 robust standard errors** (HC3 is the conservative choice for small samples
  and high-leverage points). Coefficients are unbiased either way; only SEs change.
- *Normality of residuals* — Jarque-Bera p = 0.33: no evidence against normality (matters
  for small-sample inference; with HC SEs we rely on it less).
- *Multicollinearity* — dummies of one categorical variable cannot be collinear except via
  the dummy trap, avoided by dropping a base category. Condition number 53 is fine.
- *Outliers* — M3 drops the 1 flagged cadastral row → coefficients unchanged.
- *Independence* — areas next to each other may share shocks (spatial correlation); not
  modelled here (a limitation).

**Trend model.** `log(rent) = a + b·t + c1·max(0, t − k1) + c2·max(0, t − k2)`, t in
quarters, k1 = 2022-08, k2 = 2023-11 (a "hinge" / piecewise-linear spline). Slope in each
regime: b, b + c1, b + c1 + c2. Annual growth = e^(4·slope) − 1. Durbin-Watson ≈ 0.6–1.0
(< 2) → residuals are autocorrelated (normal for time series) → **Newey-West (HAC) SEs**
with 4 lags. The knots were chosen by looking at the data (around the 2022 rate shock), so
treat the break as descriptive, not as a formally tested structural break (a Chow or
Bai-Perron test would be the next step).

## 6. Rent vs buy and affordability formulas

- Gross yield = annual rent / price = (rent per m² per month × 12) / price per m².
- Payback = 1 / yield (years of gross rent to repay the price; ignores costs and growth).
- Annuity payment: `M = P · r / (1 − (1 + r)^−n)`, r = annual rate / 12, n = years × 12.
- Price-to-income = flat price / (monthly wage × 12).
- Assumptions in `src/config.py`: 63 m² (ČSÚ average flat in Brno-město), 80 % LTV,
  30 years, ČBA rates. Change them there; the dashboard calculator lets you play with them.

## 7. Limitations (say these before the interviewer does)

1. Rents are **asking** prices modelled by MF; paid rents are lower.
2. Sale prices only at **okres** level → district yields use one price.
3. No flat attributes (floor, condition, age) → location effects can mix in building age.
4. Aggregated medians; Brno/Praha/ČR aggregates are medians of medians.
5. Correlation, not causation — the 2022 pause coincides with rate hikes, nothing more.
6. Short price window (2023-2025 by okres), regional (not city) wages, gross not net, mean
   wage not median.
7. Values were transcribed from published tables (cross-checked, see DATA_SOURCES.md).

## 8. The dashboard

`app/dashboard.py`, Streamlit:
- `load_all()` tries Postgres (`DATABASE_URL`), else reads `data/processed/*.csv`;
  `@st.cache_data` caches it for 10 minutes.
- Tabs: Overview (KPI `st.metric`s), Districts (Plotly bar + table, level/size selectors),
  Trends (lines + regime table), Regression (diagnostics, coefficients, location premiums),
  Rent vs buy (yield chart + mortgage calculator with sliders, which calls the same
  `annuity_payment()` that the tests cover), Data quality (cleaning log, outliers).
- Colours: one fixed colour per entity (Brno orange, Prague blue, ČR green) everywhere.

## 9. Fifteen likely interview questions

1. **Why log of rent?** Effects become percentages (comparable across cheap and expensive
   areas), the distribution is less skewed, and multiplicative effects (size discount ×
   location premium) become additive.
2. **How do you read −0.2064 on the 2-room dummy?** e^−0.2064 − 1 = −18.7 %: rent per m² is
   18.7 % lower than for a 1-room flat in the same area, other things in the model equal.
3. **What are fixed effects and why use them?** A dummy per area that soaks up everything
   constant about it (location, amenities). The size effect is then estimated *within*
   areas, so it is not confused with where small flats tend to be.
4. **R² went from 0.87 to 0.95 — is the second model better?** It explains more variance,
   and adjusted R² (penalises parameters) also rises, the Wald test rejects "no location
   effect" and RESET stops flagging mis-specification. But R² alone never proves a model;
   with 51 parameters on 192 rows you also check overfitting.
5. **What does heteroskedasticity do and how did you handle it?** Coefficients stay unbiased
   but usual SEs are wrong → wrong p-values. Breusch-Pagan detected it; I used HC3 robust SEs.
6. **Why Newey-West for the trend?** Time series residuals are autocorrelated (DW ≈ 1);
   HAC SEs correct for autocorrelation and heteroskedasticity.
7. **What is a p-value?** The probability of a result at least this extreme if the null
   (coefficient = 0) were true. It is not the probability the null is true, and it says
   nothing about the size or importance of an effect.
8. **Correlation vs causation here?** Size and rent per m² are associated; the model does not
   prove that adding a room causes lower rent per m² (e.g. bigger flats may differ in age or
   quality). The 2022 rent pause coincides with rate hikes but is not identified as caused by them.
9. **How did you handle outliers?** Modified z-score on log rent within each size
   (median/MAD, threshold 3.5); flagged not dropped; re-estimated without them (M3) — same result.
10. **Why not impute missing values?** A missing price/rent has no defensible value; imputing
    would create data. Here nothing was missing, but the rule is enforced and tested.
11. **Asking vs transaction prices — why does it matter?** Asking prices are what sellers or
    landlords hope for; transactions are what was paid. Mixing them (rent asks vs sale
    transactions) biases the yield upward if asking rents exceed paid rents.
12. **Explain a window function you used.** `LAG(rent, 4) OVER (PARTITION BY aggregate,
    size ORDER BY period)` gives the rent one year earlier in the same series, for yoy growth
    without a self-join.
13. **Why three layers (raw/clean/mart)?** Traceability, re-runnable cleaning without
    re-downloading, constraints on clean data, and simple fast tables for the dashboard.
14. **How do you know the pipeline works?** 47 pytest tests (cleaning edge cases, mortgage
    formula vs a textbook value, models recovering known coefficients from synthetic data,
    Postgres integration incl. a CHECK constraint), Ruff, GitHub Actions on every push,
    pipeline rerun is idempotent.
15. **What would you do with more time/data?** Flat-level transaction data (ČÚZK price data
    if licensed) for a real hedonic sale model; spatial models / distance to centre;
    formal break tests; net-wage affordability with household income distribution; a
    scheduled refresh of the rent map; a Power BI version on the same mart.

Bonus quick ones: *OLS assumptions?* linear in parameters, exogeneity (E[ε|X] = 0), no perfect
collinearity, homoskedastic & uncorrelated errors for usual SEs, normality for exact
small-sample tests. *Dummy trap?* including a dummy for every category plus an intercept
makes X singular — drop one base category. *Why median not mean for rents?* robust to
extreme listings.
