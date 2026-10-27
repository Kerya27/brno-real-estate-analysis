-- Aggregated layer used by the dashboard. Rebuilt on every pipeline run.

-- Rent by city district (městská část), one row per district x flat size,
-- with rank and gap to the median district of the same size.
DROP TABLE IF EXISTS mart.district_rent;
CREATE TABLE mart.district_rent AS
WITH d AS (
    SELECT area_name, size_key, size_label, model_area_m2,
           rent_kc_m2_month, rent_kc_m2_month_prev_year, yoy_pct, rent_flat_month_kc
    FROM clean.rent_map
    WHERE area_type = 'city_district'
),
med AS (
    SELECT size_key,
           PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY rent_kc_m2_month) AS median_rent
    FROM d
    GROUP BY size_key
)
SELECT d.*,
       RANK() OVER (PARTITION BY d.size_key ORDER BY d.rent_kc_m2_month DESC) AS rank_in_size,
       ROUND(((d.rent_kc_m2_month / med.median_rent - 1) * 100)::numeric, 1) AS pct_vs_median
FROM d
JOIN med USING (size_key);

-- Rent history with year-over-year growth (4 editions back = 1 year).
DROP TABLE IF EXISTS mart.rent_trend;
CREATE TABLE mart.rent_trend AS
SELECT aggregate, period, size_key, size_label, rent_kc_m2_month,
       ROUND(((rent_kc_m2_month
               / LAG(rent_kc_m2_month, 4) OVER w - 1) * 100)::numeric, 1) AS yoy_pct,
       ROUND((rent_kc_m2_month
              / FIRST_VALUE(rent_kc_m2_month) OVER w * 100)::numeric, 1) AS index_first_100
FROM clean.rent_history
WINDOW w AS (PARTITION BY aggregate, size_key ORDER BY period);

-- Transaction prices by territory and year with growth.
DROP TABLE IF EXISTS mart.okres_price_growth;
CREATE TABLE mart.okres_price_growth AS
SELECT p.area_name, a.area_level, a.region, p.year, p.price_kc_m2,
       ROUND(((p.price_kc_m2 / LAG(p.price_kc_m2) OVER w - 1) * 100)::numeric, 1) AS yoy_pct,
       a.avg_flat_m2,
       ROUND(p.price_kc_m2 * a.avg_flat_m2) AS avg_flat_price_kc
FROM clean.okres_prices p
JOIN clean.okres_areas a USING (area_name)
WINDOW w AS (PARTITION BY p.area_name ORDER BY p.year);

-- Annual price index with yoy change.
DROP TABLE IF EXISTS mart.price_index_yoy;
CREATE TABLE mart.price_index_yoy AS
SELECT area_name, year, index_2015_100,
       ROUND(((index_2015_100 / LAG(index_2015_100) OVER w - 1) * 100)::numeric, 1) AS yoy_pct
FROM clean.price_index_a
WINDOW w AS (PARTITION BY area_name ORDER BY year);
