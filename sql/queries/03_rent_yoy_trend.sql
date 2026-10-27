-- Question: How fast have asking rents (2-room flats) grown year over year in Brno
-- compared with Prague and the Czech Republic, edition by edition?
SELECT period,
       MAX(rent_kc_m2_month) FILTER (WHERE aggregate = 'brno')  AS brno_rent,
       MAX(yoy_pct)          FILTER (WHERE aggregate = 'brno')  AS brno_yoy_pct,
       MAX(yoy_pct)          FILTER (WHERE aggregate = 'praha') AS praha_yoy_pct,
       MAX(yoy_pct)          FILTER (WHERE aggregate = 'cr')    AS cr_yoy_pct
FROM mart.rent_trend
WHERE size_key = 2
GROUP BY period
ORDER BY period;
