# Findings — Brno housing market (data to 2026-08)

Numbers come from the pipeline outputs in `data/processed/` (file named in brackets).
Language is deliberately cautious: these are descriptive results on aggregated, partly
offer-based data.

## 1. Brno-město is the price outlier of South Moravia — and pulled further ahead

- Average realised price of apartments in Brno-město: **77 827 → 88 333 → 99 713 Kč/m²**
  (2023 → 2024 → 2025): +12.9 % in 2025 and +28.1 % over two years
  (`query_05_okres_price_growth.csv`).
- 2025 level: **22 % above** the Jihomoravský kraj average (81 652) and **47 % above** the
  next most expensive okres, Brno-venkov (67 813). Brno-venkov grew just as fast (+28.7 %),
  consistent with demand spilling over to the commuter belt — a plausible reading, not a
  tested one.
- Price cycle (ČSÚ index, `query_06_price_index_cycle.csv`): South Moravia had the deepest
  correction of the three series, **−11.3 %** from the 2022 Q2 peak to the 2023 Q2 trough
  (ČR −7.7 %, Praha −6.9 %), and only regained the peak in 2025 Q3.

## 2. Flat size moves rent per m² more than location does

Model M2: `log(rent per m²) = β0 + size dummies + 48 cadastral-area dummies`, n = 192, HC3.

| vs 1-room flat, same area | effect on rent per m² | 95 % CI |
|---|---|---|
| 2-room (2+kk / 2+1) | **−18.7 %** | −20.3 % to −17.0 % |
| 3-room | **−28.1 %** | −29.6 % to −26.7 % |
| 4+ rooms | **−33.7 %** | −35.3 % to −32.2 % |

- Size alone explains R² = 0.87; with location effects R² = 0.95 (adj. 0.94). Location
  effects are jointly significant (robust Wald F = 541, p < 0.001) but their spread is
  narrower: about **+13 %** (Komárov, Horní Heršpice) to **−12 %** (Útěchov) around the
  median area, most areas within ±5 % (`location_premiums.csv`).
- The size coefficients are identical with and without location effects because every area
  has all four sizes (balanced design → size and location dummies are orthogonal).
- Diagnostics: residuals look normal (Jarque-Bera p = 0.33), heteroskedasticity is present
  (Breusch-Pagan p < 0.001) → robust SEs are needed; RESET p = 0.34 after adding location.
  Dropping the 3 flagged outliers (M3) changes nothing material.
- Caveat: the top premiums are in Brno-jih cadastral areas. If listings there are mostly
  new-builds, part of the "location" effect is really a building-age effect — the
  aggregated data cannot separate the two.

## 3. Rents: boom, pause, boom again

Piecewise log-linear trend of Brno 2-room asking rents, Newey-West SEs (`rent_trend_regimes.csv`):

| period | annualised growth |
|---|---|
| 2019-02 … 2022-05 | **+7.2 %/yr** |
| 2022-08 … 2023-08 | **−0.5 %/yr** (flat) |
| 2023-11 … 2026-08 | **+5.8 %/yr** |

Same pattern for all flat sizes. Over the whole period Brno rents grew a little faster than
Prague's (CAGR 5.7 % vs 5.3 %, 2-room) and moved from 86 % to 89 % of the Prague level
(`query_04`, `query_07`). Year-on-year growth in the latest edition: median district +8 %.
Within Brno, the most expensive quarter of areas grew fastest for 3- and 4-room flats
(`query_10`) — no sign that cheaper areas are catching up, though one year is a short window.

## 4. Rent vs buy: thin gross yields

At the Brno-město 2025 price and 2025-08 asking rents (`district_yields.csv`):

| flat size | gross yield, median district (range) | payback |
|---|---|---|
| 1-room | 3.9 % (3.6–4.5 %) | ~26 years |
| 2-room | 3.2 % (2.7–3.5 %) | ~31 years |
| 3-room | 2.8 % (2.6–3.0 %) | ~35 years |
| 4+ rooms | 2.7 % (2.5–3.0 %) | ~38 years |

Gross yields sit **below** the 4.6–5.1 % mortgage rates of 2025-2026, before maintenance,
vacancy, tax and transaction costs — buying to let in Brno only pays through expected price
growth. Because district sale prices are not published, differences between districts come
from rents only.

## 5. Affordability

Average Brno-město flat: 63 m² (ČSÚ) × 99 713 Kč/m² = **6.28 M Kč** (`affordability.csv`).

| | 2024 | 2025 | latest |
|---|---|---|---|
| price-to-income (one average gross wage, years) | 10.3 | **10.8** | 10.6 |
| mortgage rate (ČBA) | 5.07 % | 4.58 % | 5.10 % (2026-09) |
| monthly payment, 80 % LTV, 30 y | 24 090 | **25 703** | 27 286 Kč |
| payment / one gross wage | 53 % | 53 % | 55 % |
| payment / two gross wages | 27 % | 27 % | 28 % |
| asking rent for the same flat (2-room rate) | 16 506 | 17 199 | 18 585 Kč |

Prices rose faster than wages in 2025 (+12.9 % vs +7.6 %), but the lower rate kept the
payment share flat. For a single average earner the payment is more than half of the
*gross* wage (a larger share of net pay); for two earners it is about a quarter. The 20 % down payment (1.26 M Kč) equals about 26 months of
gross wage — usually the binding constraint.
