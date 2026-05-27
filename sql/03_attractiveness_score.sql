-- Attractiveness score (0–8) per job posting.
-- Each of the 8 criteria contributes 1 point when met.
-- Used by: DB-04 posting quality, DB-01 avg attractiveness score.

SELECT
    jp.posting_id,
    jp.company_id,
    c.company_name,
    jp.title,
    jp.status,
    jp.image_count,
    LENGTH(jp.description)  AS description_length,
    jp.compensation_type,
    jp.has_deadline,
    jp.has_sample,
    jp.platform_targets,
    jp.required_followers,
    jp.category,
    (
        (CASE WHEN jp.image_count >= 3                             THEN 1 ELSE 0 END) +
        (CASE WHEN LENGTH(jp.description) >= 200                  THEN 1 ELSE 0 END) +
        (CASE WHEN jp.compensation_type = 'fixed'                 THEN 1 ELSE 0 END) +
        (CASE WHEN jp.has_deadline = TRUE                         THEN 1 ELSE 0 END) +
        (CASE WHEN jp.has_sample = TRUE                           THEN 1 ELSE 0 END) +
        (CASE WHEN jp.platform_targets IS NOT NULL
              AND jp.platform_targets != ''                       THEN 1 ELSE 0 END) +
        (CASE WHEN jp.required_followers BETWEEN 10000 AND 500000 THEN 1 ELSE 0 END) +
        (CASE WHEN jp.category IS NOT NULL
              AND jp.category != ''                               THEN 1 ELSE 0 END)
    ) AS attractiveness_score
FROM job_postings jp
JOIN companies c USING (company_id);
