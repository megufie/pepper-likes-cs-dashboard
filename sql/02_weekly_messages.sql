-- Outbound messages (company → influencer) per company per ISO week.
-- Covers the last 12 weeks. Used by: DB-03 weekly activity, red/yellow alerts.

SELECT
    m.company_id,
    c.company_name,
    strftime(CAST(m.sent_at AS DATE), '%G-W%V') AS iso_week,
    COUNT(*)                                     AS message_count
FROM messages m
JOIN companies c USING (company_id)
WHERE m.direction = 'company_to_inf'
  AND CAST(m.sent_at AS DATE) >= CURRENT_DATE - INTERVAL '12 weeks'
GROUP BY m.company_id, c.company_name, iso_week
ORDER BY m.company_id, iso_week;
