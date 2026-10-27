-- Question: How do transaction prices per m2 in Brno-město compare with the other
-- districts of the South Moravian Region, and how much did they grow 2023 -> 2025?
WITH wide AS (
    SELECT area_name, area_level,
           MAX(price_kc_m2) FILTER (WHERE year = 2023) AS p2023,
           MAX(price_kc_m2) FILTER (WHERE year = 2025) AS p2025
    FROM mart.okres_price_growth
    WHERE region = 'Jihomoravský kraj' OR area_level = 'stat'
    GROUP BY area_name, area_level
),
kraj AS (
    SELECT p2025 AS kraj_2025 FROM wide WHERE area_name = 'Jihomoravský kraj'
)
SELECT area_name, area_level, p2023, p2025,
       ROUND(((p2025 / p2023 - 1) * 100)::numeric, 1)           AS growth_2023_2025_pct,
       ROUND(((p2025 / kraj.kraj_2025 - 1) * 100)::numeric, 1)  AS pct_vs_kraj_2025,
       DENSE_RANK() OVER (ORDER BY p2025 DESC)                  AS price_rank_2025
FROM wide CROSS JOIN kraj
ORDER BY p2025 DESC;
