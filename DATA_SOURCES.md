# Data sources

All files in `data/raw/` are small snapshots of published data, committed so the project is
reproducible offline. Download / retrieval date for every file: **2026-10-27**.

No data was scraped from listing portals. No value was invented: where a number is derived
from published numbers, the derivation is stated below.

| File | What | Source (publisher) | URL | Licence / terms |
|---|---|---|---|---|
| `mf_rent_map_brno_2026-08.csv` | Median **asking** rent, Kč/m²/month, by Brno cadastral area (48) and city district (29) × 4 flat sizes, edition 2026-08, with yoy change | Ministry of Finance ČR – *Cenová mapa nájemného*; machine-readable copy by *Brno pod lupou* (M. Kubásek) | https://www.brnopodlupou.cz/data/cenova-mapa-najmu.csv · MF: https://mf.gov.cz/cs/rozpoctova-politika/podpora-projektoveho-rizeni/cenova-mapa/cenova-mapa-infografika | **CC BY 4.0** (attribution: Brno pod lupou, MF ČR) |
| `mf_rent_history_city_aggregates.csv` | Same rent map, city aggregates Brno / Praha / ČR, 31 quarterly editions 2019-02 … 2026-08 | as above (`city_median_history` in the JSON) | https://www.brnopodlupou.cz/data/cenova-mapa-najmu.json | **CC BY 4.0** |
| `mf_rent_size_categories.csv` | Size categories and the model flat area used by MF (35/55/75/100 m²) | as above (`size_categories`, `model_area_m2`) | same JSON | **CC BY 4.0** |
| `csu_apartment_prices_okres_2023_2025.csv` | Average **transaction** price of apartments, Kč/m², 2023, 2024, 2025 and 2023-2025, number of transfers, average flat size; ČR, Praha, Jihomoravský kraj and its 7 okresy | Czech Statistical Office (ČSÚ), *Ceny nemovitostí – 2023–2025*, table 2-4 (published 15 Jul 2026) | https://csu.gov.cz/produkty/ceny-nemovitosti · table PDF: https://csu.gov.cz/docs/107508/d279d0d1-043e-0faa-b5cb-56e400cc134b/0140162607.pdf?version=1.0 | ČSÚ data may be reused with source attribution ([terms](https://csu.gov.cz/podminky_pro_vyuzivani_a_dalsi_zverejnovani_statistickych_udaju_csu)) |
| `csu_apartment_price_index_2015_100.csv` | Apartment price index (2015 = 100), quarterly + annual average 2015-2025, ČR / Praha / Jihomoravský kraj | ČSÚ, same publication, table 2-6b | https://csu.gov.cz/docs/107508/03f3e6a8-c5ea-7a3c-ed9a-399d6dea6f9e/0140162610.pdf?version=1.0 | ČSÚ terms (attribution) |
| `csu_wages_jmk.csv` | Average gross monthly wage, Jihomoravský kraj: 2025, Q4 2025, H1 2026, Q2 2026; **2024 is derived** = 2025 value − stated yoy change (+3 431 Kč) | ČSÚ regional office Brno, press releases | https://csu.gov.cz/jhm/prumerna-mzda-v-jihomoravskem-kraji-ve-2-ctvrtleti-2026-a-v-1-pololeti-roku-2026 · Q4 2025 release (via kurzy.cz): https://zpravy.kurzy.cz/852298-v-jihomoravskem-kraji-prumerna-mzda-ve-4-ctvrtleti-2025-vzrostla-realne-o-5-2--na-51-922-kc/ | ČSÚ terms (attribution) |
| `cba_mortgage_rates.csv` | Average agreed rate on new mortgages, % p.a.: 2024 and 2025 averages and the monthly values the page shows (2025-03 … 2026-09) | Czech Banking Association (ČBA) Hypomonitor | https://www.cbamonitor.cz/statistika/prumerna-urokova-sazba-novych-hypotek | Published statistic, used as a cited figure |

## How the data was obtained and checked

- The analysis environment could not reach ČSÚ / Eurostat / ČNB APIs directly, so values were
  retrieved from the published pages and files above and written to CSV. Cross-checks:
  ČR 2025 = 72 410 and Praha 2025 = 131 520 Kč/m² match ČSÚ's own summary page
  (https://csu.gov.cz/ceny-nemovitosti); Brno-město 2024 = 88 333 and 2025 = 99 713 Kč/m²
  match an independent page quoting the same ČSÚ table; the pipeline checks that every
  index row's annual average equals the mean of its four quarters (0 violations).
- `python -m src.ingest` re-downloads the latest rent map CSV to a new dated file, so the
  snapshot can be refreshed without overwriting it.

## Sources checked but not used

| Source | Why not used |
|---|---|
| Eurostat `prc_hpi_q` (house price index) | Not reachable from the build environment; the ČSÚ index above is the national source for the same statistic, with a regional split Eurostat does not have. |
| ČNB ARAD (mortgage rates) | Not reachable from the build environment; ČBA Hypomonitor publishes the same concept (agreed rate on new mortgages). Note the two series differ slightly (ČNB reports an annualised rate). |
| data.brno.cz (city open data, ArcGIS Hub) | Page content is rendered by JavaScript and was not retrievable; district names/codes come with the rent map (RÚIAN codes). |
| Listing portals (Sreality, Bezrealitky, …) and scraper datasets | **Not used.** Their terms do not allow scraping/redistribution, and no openly licensed Brno listing dataset (Kaggle or government) with flat-level attributes was found. |
| Commercial reports (Deloitte Real Index, developer reports, CEMAP) | Licence unclear / not open data. |

**Consequence:** there is no open flat-level dataset (area, floor, condition, building type)
and no open district-level *sale* price for Brno. The analysis is adapted accordingly — see
the README.
