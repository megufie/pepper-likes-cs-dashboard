-- Company activity by calendar month.
-- An "active month" = at least one outbound message OR one application received.
-- Used by: DB-02 continuity matrix, DB-01 avg continuation months.

WITH months AS (
    SELECT DISTINCT
        company_id,
        strftime(CAST(sent_at AS DATE), '%Y-%m') AS activity_month
    FROM messages
    WHERE direction = 'company_to_inf'

    UNION

    SELECT DISTINCT
        company_id,
        strftime(CAST(applied_at AS DATE), '%Y-%m') AS activity_month
    FROM applications
)
SELECT
    c.company_id,
    c.company_name,
    m.activity_month,
    1 AS is_active
FROM companies c
JOIN months m USING (company_id)
ORDER BY c.company_id, m.activity_month;
