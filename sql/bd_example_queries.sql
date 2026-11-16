-- Example queries for the Bangladesh district tables (run in phpMyAdmin -> SQL tab).
-- Database: smart_flood_system. Tables are filled by:  python -m floodml export-mysql

-- 1. Newest risk of every district, highest first
SELECT district, division, as_of, risk_level, ROUND(probability * 100, 1) AS chance_pct, rain_3d_mm
FROM bd_latest_risk
ORDER BY probability DESC;

-- 2. Daily rainfall and weather of one district, last 30 days
SELECT d.observation_date, d.rain_mm, d.t2m, d.rh2m, d.gwet_root
FROM bd_daily_data d JOIN bd_locations l ON l.location_id = d.location_id
WHERE l.name = 'Sylhet'
ORDER BY d.observation_date DESC
LIMIT 30;

-- 3. Wettest districts over the last 7 days
SELECT l.name AS district, l.division, ROUND(SUM(d.rain_mm), 1) AS rain_7d_mm
FROM bd_daily_data d JOIN bd_locations l ON l.location_id = d.location_id
WHERE l.kind = 'district' AND d.observation_date >= CURDATE() - INTERVAL 7 DAY
GROUP BY l.name, l.division
ORDER BY rain_7d_mm DESC
LIMIT 10;

-- 4. How many flooded days per district (documented events)?
SELECT l.name AS district, COUNT(*) AS flood_days
FROM bd_flood_days f JOIN bd_locations l ON l.location_id = f.location_id
GROUP BY l.name
ORDER BY flood_days DESC;

-- 5. Rain on flood days vs other days (simple sanity check of the labels)
SELECT CASE WHEN f.location_id IS NULL THEN 'no documented flood' ELSE 'flood day' END AS day_type,
       COUNT(*) AS days, ROUND(AVG(d.rain_mm), 2) AS avg_rain_mm
FROM bd_daily_data d
LEFT JOIN (SELECT DISTINCT location_id, flood_date FROM bd_flood_days) f
       ON f.location_id = d.location_id AND f.flood_date = d.observation_date
WHERE d.location_id < 9000 AND d.observation_date >= '2022-01-01'
GROUP BY day_type;

-- 6. Prediction history of one district
SELECT p.as_of, p.risk_level, ROUND(p.probability * 100, 1) AS chance_pct
FROM bd_predictions p JOIN bd_locations l ON l.location_id = p.location_id
WHERE l.name = 'Sunamganj'
ORDER BY p.as_of DESC;
