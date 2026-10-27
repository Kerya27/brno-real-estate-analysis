-- Question: How many years of the average South Moravian gross wage does an average
-- Brno-město flat cost, and how did that change from 2024 to 2025?
WITH flat AS (
    SELECT p.year, p.price_kc_m2, a.avg_flat_m2,
           p.price_kc_m2 * a.avg_flat_m2 AS flat_price_kc
    FROM clean.okres_prices p
    JOIN clean.okres_areas a USING (area_name)
    WHERE p.area_name = 'Brno-město'
),
wage AS (
    SELECT CAST(period AS INTEGER) AS year, avg_gross_wage_kc
    FROM clean.wages
    WHERE region = 'Jihomoravský kraj' AND period ~ '^\d{4}$'
)
SELECT f.year, f.price_kc_m2, f.avg_flat_m2, ROUND(f.flat_price_kc) AS flat_price_kc,
       w.avg_gross_wage_kc,
       ROUND((f.flat_price_kc / (w.avg_gross_wage_kc * 12))::numeric, 2) AS years_of_gross_wage,
       ROUND((f.price_kc_m2 / w.avg_gross_wage_kc)::numeric, 2)          AS monthly_wages_per_m2
FROM flat f
JOIN wage w USING (year)
ORDER BY f.year;
