-- Question: Are cheaper areas catching up? Average yoy rent growth by rent-level
-- quartile of cadastral areas (NTILE), per flat size.
WITH q AS (
    SELECT area_name, size_label, size_key, rent_kc_m2_month, yoy_pct,
           NTILE(4) OVER (PARTITION BY size_key ORDER BY rent_kc_m2_month) AS rent_quartile
    FROM clean.rent_map
    WHERE area_type = 'cadastral_area'
)
SELECT size_label, rent_quartile,
       COUNT(*)                                 AS areas,
       ROUND(MIN(rent_kc_m2_month), 0)          AS min_rent,
       ROUND(MAX(rent_kc_m2_month), 0)          AS max_rent,
       ROUND(AVG(yoy_pct), 1)                   AS avg_yoy_pct,
       ROUND(STDDEV_SAMP(yoy_pct), 1)           AS sd_yoy_pct
FROM q
GROUP BY size_key, size_label, rent_quartile
ORDER BY size_key, rent_quartile;
