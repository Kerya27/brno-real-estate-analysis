-- Question: How did apartment prices move through the 2021-2023 cycle? Peak quarter,
-- drawdown from the peak to the trough, and how long the recovery took.
WITH q AS (
    SELECT area_name, period, index_2015_100,
           MAX(index_2015_100) OVER (PARTITION BY area_name ORDER BY period
                                     ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
               AS running_peak
    FROM clean.price_index_q
),
dd AS (
    SELECT *, ROUND(((index_2015_100 / running_peak - 1) * 100)::numeric, 1) AS drawdown_pct
    FROM q
),
worst AS (
    SELECT DISTINCT ON (area_name) area_name, period AS trough_period,
           index_2015_100 AS trough_index, running_peak, drawdown_pct
    FROM dd
    ORDER BY area_name, drawdown_pct, period
),
recovered AS (
    SELECT w.area_name, MIN(q.period) AS recovered_period
    FROM worst w
    JOIN q ON q.area_name = w.area_name
          AND q.period > w.trough_period
          AND q.index_2015_100 >= w.running_peak
    GROUP BY w.area_name
)
SELECT w.area_name, w.running_peak AS peak_index, w.trough_period, w.trough_index,
       w.drawdown_pct, r.recovered_period
FROM worst w
LEFT JOIN recovered r USING (area_name)
ORDER BY w.drawdown_pct;
