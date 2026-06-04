"""
All SQL queries. Each function takes a DuckDB connection and returns a pd.DataFrame.
No Streamlit code here.
"""
from __future__ import annotations

import duckdb
import pandas as pd


# ── Monthly activity helpers ───────────────────────────────────────────────────

def get_monthly_active_counts(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Returns (activity_month, active_company_count) sorted ascending."""
    return con.execute("""
        WITH months AS (
            SELECT company_id,
                   strftime(CAST(sent_at AS DATE), '%Y-%m') AS activity_month
            FROM messages
            WHERE direction = 'company_to_inf'
            UNION
            SELECT company_id,
                   strftime(CAST(applied_at AS DATE), '%Y-%m') AS activity_month
            FROM applications
        )
        SELECT activity_month,
               COUNT(DISTINCT company_id) AS active_company_count
        FROM months
        GROUP BY activity_month
        ORDER BY activity_month
    """).df()


def get_active_this_month(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Returns company_ids active in the current calendar month."""
    return con.execute("""
        SELECT DISTINCT company_id FROM (
            SELECT company_id
            FROM messages
            WHERE direction = 'company_to_inf'
              AND strftime(CAST(sent_at AS DATE), '%Y-%m')
                  = strftime(CURRENT_DATE, '%Y-%m')
            UNION
            SELECT company_id
            FROM applications
            WHERE strftime(CAST(applied_at AS DATE), '%Y-%m')
                  = strftime(CURRENT_DATE, '%Y-%m')
        )
    """).df()


def get_churn_rate(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Returns (last_month_count, churned_count, churn_rate_pct)."""
    return con.execute("""
        WITH this_month AS (
            SELECT DISTINCT company_id FROM messages
            WHERE direction = 'company_to_inf'
              AND strftime(CAST(sent_at AS DATE), '%Y-%m')
                  = strftime(CURRENT_DATE, '%Y-%m')
            UNION
            SELECT DISTINCT company_id FROM applications
            WHERE strftime(CAST(applied_at AS DATE), '%Y-%m')
                  = strftime(CURRENT_DATE, '%Y-%m')
        ),
        last_month AS (
            SELECT DISTINCT company_id FROM messages
            WHERE direction = 'company_to_inf'
              AND strftime(CAST(sent_at AS DATE), '%Y-%m')
                  = strftime(CURRENT_DATE - INTERVAL '1 month', '%Y-%m')
            UNION
            SELECT DISTINCT company_id FROM applications
            WHERE strftime(CAST(applied_at AS DATE), '%Y-%m')
                  = strftime(CURRENT_DATE - INTERVAL '1 month', '%Y-%m')
        )
        SELECT
            COUNT(DISTINCT lm.company_id) AS last_month_count,
            COUNT(DISTINCT CASE WHEN tm.company_id IS NULL THEN lm.company_id END)
                AS churned_count,
            ROUND(
                COUNT(DISTINCT CASE WHEN tm.company_id IS NULL THEN lm.company_id END)
                * 100.0 / NULLIF(COUNT(DISTINCT lm.company_id), 0),
            1) AS churn_rate_pct
        FROM last_month lm
        LEFT JOIN this_month tm USING (company_id)
    """).df()


# ── Continuity matrix ─────────────────────────────────────────────────────────

def get_continuity_matrix_raw(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Returns (company_id, company_name, activity_month, is_active=1)."""
    return con.execute("""
        WITH months AS (
            SELECT company_id,
                   strftime(CAST(sent_at AS DATE), '%Y-%m') AS activity_month
            FROM messages
            WHERE direction = 'company_to_inf'
            UNION
            SELECT company_id,
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
        ORDER BY c.company_id, m.activity_month
    """).df()


def get_avg_continuation_months(con: duckdb.DuckDBPyConnection) -> float:
    """Returns mean total_active_months across all companies that ever had activity."""
    result = con.execute("""
        WITH months AS (
            SELECT company_id,
                   strftime(CAST(sent_at AS DATE), '%Y-%m') AS activity_month
            FROM messages
            WHERE direction = 'company_to_inf'
            UNION
            SELECT company_id,
                   strftime(CAST(applied_at AS DATE), '%Y-%m') AS activity_month
            FROM applications
        )
        SELECT AVG(cnt) AS avg_months
        FROM (
            SELECT company_id, COUNT(DISTINCT activity_month) AS cnt
            FROM months
            GROUP BY company_id
        )
    """).fetchone()
    return float(result[0]) if result and result[0] is not None else 0.0


# ── Weekly messages ───────────────────────────────────────────────────────────

def get_weekly_messages(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Outbound message counts per company per ISO week, last 12 weeks."""
    return con.execute("""
        SELECT
            m.company_id,
            c.company_name,
            strftime(CAST(m.sent_at AS DATE), '%G-W%V') AS iso_week,
            COUNT(*) AS message_count
        FROM messages m
        JOIN companies c USING (company_id)
        WHERE m.direction = 'company_to_inf'
          AND CAST(m.sent_at AS DATE) >= CURRENT_DATE - INTERVAL '12 weeks'
        GROUP BY m.company_id, c.company_name, iso_week
        ORDER BY m.company_id, iso_week
    """).df()


def get_all_active_companies(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Returns (company_id, company_name) for all active companies."""
    return con.execute("""
        SELECT company_id, company_name
        FROM companies
        WHERE status = 'active'
        ORDER BY company_name
    """).df()


def get_silent_companies_3w(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Active companies with 0 outbound messages in the last 3 weeks."""
    return con.execute("""
        WITH recent AS (
            SELECT DISTINCT company_id
            FROM messages
            WHERE direction = 'company_to_inf'
              AND CAST(sent_at AS DATE) >= CURRENT_DATE - INTERVAL '3 weeks'
        )
        SELECT c.company_id, c.company_name
        FROM companies c
        LEFT JOIN recent r USING (company_id)
        WHERE c.status = 'active'
          AND r.company_id IS NULL
        ORDER BY c.company_name
    """).df()


# ── Attractiveness scores ─────────────────────────────────────────────────────

def get_attractiveness_scores(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """
    0–12 attractiveness score per job posting with company name.

    Weighted scoring (12 points total):
      1. Title length >= 20 chars                            (1pt)
      2. Description >= 200 chars                            (1pt)
      3. Description >= 500 chars                            (1pt)
      4-5. Image count: 0 = 0pt, 1-2 = 1pt, 3+ = 2pt        (2pt MAX)  ⭐
      6. compensation_type = 'fixed'                         (1pt)
      7. compensation_amount > 0                             (1pt)
      8-9. Follower targeting:                                          ⭐
           Not specified or <=3000+ (id 1-5) = 2pt
           5000+ (id 6)                       = 1pt
           >=10000+ (id 7-9)                  = 0pt
      10. category set                                       (1pt)
      11. SNS targets set                                    (1pt)
      12. Country targets set                                (1pt)
    """
    # follower_count_id may not exist on CSV-mode (test data).
    # Detect by looking up table info.
    cols = [r[1] for r in con.execute("PRAGMA table_info('job_postings')").fetchall()]
    has_follower_id = "follower_count_id" in cols
    has_country_count = "target_country_count" in cols

    follower_score = (
        "(CASE "
        "  WHEN jp.follower_count_id BETWEEN 1 AND 5 THEN 2 "
        "  WHEN jp.follower_count_id = 6             THEN 1 "
        "  ELSE 0 END)"
        if has_follower_id else
        # Fallback for CSV mode: required_followers within sweet spot
        "(CASE "
        "  WHEN jp.required_followers BETWEEN 1 AND 3000     THEN 2 "
        "  WHEN jp.required_followers BETWEEN 3001 AND 5000  THEN 1 "
        "  WHEN jp.required_followers >= 10000               THEN 0 "
        "  WHEN jp.required_followers = 0                    THEN 2 "
        "  ELSE 1 END)"
    )
    country_score = (
        "(CASE WHEN jp.target_country_count >= 1 THEN 1 ELSE 0 END)"
        if has_country_count else "0"
    )

    return con.execute(f"""
        SELECT
            jp.posting_id,
            jp.company_id,
            c.company_name,
            jp.title,
            jp.status,
            jp.image_count,
            LENGTH(jp.description) AS description_length,
            jp.compensation_type,
            jp.compensation_amount,
            jp.platform_targets,
            jp.required_followers,
            jp.category,
            jp.created_at,
            DATEDIFF('day', CAST(jp.created_at AS DATE), CURRENT_DATE) AS posting_age_days,
            (
                (CASE WHEN LENGTH(jp.title)       >= 20  THEN 1 ELSE 0 END) +
                (CASE WHEN LENGTH(jp.description) >= 200 THEN 1 ELSE 0 END) +
                (CASE WHEN LENGTH(jp.description) >= 500 THEN 1 ELSE 0 END) +
                (CASE WHEN jp.image_count >= 3 THEN 2
                      WHEN jp.image_count >= 1 THEN 1
                      ELSE 0 END) +
                (CASE WHEN jp.compensation_type = 'fixed'  THEN 1 ELSE 0 END) +
                (CASE WHEN jp.compensation_amount > 0      THEN 1 ELSE 0 END) +
                {follower_score} +
                (CASE WHEN jp.category IS NOT NULL
                      AND jp.category != ''                THEN 1 ELSE 0 END) +
                (CASE WHEN jp.platform_targets IS NOT NULL
                      AND jp.platform_targets != ''        THEN 1 ELSE 0 END) +
                {country_score}
            ) AS attractiveness_score
        FROM job_postings jp
        LEFT JOIN companies c USING (company_id)
        ORDER BY attractiveness_score DESC
    """).df()


def get_posting_age_distribution(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Histogram of active posting ages (days since creation)."""
    return con.execute("""
        WITH ages AS (
            SELECT DATEDIFF('day', CAST(created_at AS DATE), CURRENT_DATE) AS age_days
            FROM job_postings WHERE status = 'active'
        )
        SELECT
            CASE
                WHEN age_days <= 30  THEN '1: 0-30日'
                WHEN age_days <= 60  THEN '2: 31-60日'
                WHEN age_days <= 90  THEN '3: 61-90日'
                WHEN age_days <= 180 THEN '4: 91-180日'
                WHEN age_days <= 365 THEN '5: 181-365日'
                ELSE '6: 365日超'
            END AS age_bucket,
            COUNT(*) AS posting_count
        FROM ages
        GROUP BY age_bucket
        ORDER BY age_bucket
    """).df()


def get_company_refresh_activity(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Per-company posting refresh stats."""
    return con.execute("""
        SELECT
            c.company_id,
            c.company_name,
            COUNT(jp.posting_id) AS total_postings,
            SUM(CASE WHEN jp.status = 'active' THEN 1 ELSE 0 END) AS active_postings,
            SUM(CASE WHEN DATEDIFF('day', CAST(jp.created_at AS DATE), CURRENT_DATE) <= 30
                     THEN 1 ELSE 0 END) AS new_in_30d,
            SUM(CASE WHEN DATEDIFF('day', CAST(jp.created_at AS DATE), CURRENT_DATE) > 90
                     AND jp.status = 'active' THEN 1 ELSE 0 END) AS stale_active,
            MAX(CAST(jp.created_at AS DATE)) AS latest_posting_date
        FROM companies c
        LEFT JOIN job_postings jp ON jp.company_id = c.company_id
        GROUP BY c.company_id, c.company_name
        HAVING total_postings > 0
        ORDER BY new_in_30d DESC, active_postings DESC
    """).df()


def get_age_vs_adoption_correlation(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """For each posting: age in days vs adoption rate (≥3 apps)."""
    return con.execute("""
        SELECT
            jp.posting_id,
            jp.title,
            DATEDIFF('day', CAST(jp.created_at AS DATE), CURRENT_DATE) AS age_days,
            COUNT(a.application_id) AS total_apps,
            ROUND(
                SUM(CASE WHEN a.status = 'accepted' THEN 1 ELSE 0 END) * 100.0
                / NULLIF(COUNT(a.application_id), 0), 1
            ) AS adoption_rate_pct
        FROM job_postings jp
        LEFT JOIN applications a USING (posting_id)
        WHERE jp.status = 'active'
        GROUP BY jp.posting_id, jp.title, jp.created_at
        HAVING total_apps >= 3
    """).df()


def get_application_rates(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Adoption rate per posting (only postings with >= 3 applications)."""
    return con.execute("""
        SELECT
            posting_id,
            COUNT(*)                                                     AS total_applications,
            SUM(CASE WHEN status = 'accepted' THEN 1 ELSE 0 END)        AS accepted_count,
            ROUND(
                SUM(CASE WHEN status = 'accepted' THEN 1 ELSE 0 END)
                * 100.0 / COUNT(*),
            1) AS adoption_rate_pct
        FROM applications
        GROUP BY posting_id
        HAVING COUNT(*) >= 3
        ORDER BY adoption_rate_pct DESC
    """).df()


# ── Extra summary queries ─────────────────────────────────────────────────────

def get_application_status_breakdown(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Application status counts for the donut chart."""
    return con.execute("""
        SELECT status, COUNT(*) AS count
        FROM applications
        GROUP BY status
        ORDER BY count DESC
    """).df()


def get_total_messages(con: duckdb.DuckDBPyConnection) -> int:
    result = con.execute(
        "SELECT COUNT(*) FROM messages WHERE direction = 'company_to_inf'"
    ).fetchone()
    return int(result[0]) if result else 0


def get_overall_adoption_rate(con: duckdb.DuckDBPyConnection) -> float:
    result = con.execute("""
        SELECT
            ROUND(
                SUM(CASE WHEN status = 'accepted' THEN 1 ELSE 0 END) * 100.0
                / NULLIF(COUNT(*), 0),
            1)
        FROM applications
    """).fetchone()
    return float(result[0]) if result and result[0] is not None else 0.0


def get_monthly_messages_and_apps(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Per-month total messages (bar) + active company count (line)."""
    return con.execute("""
        WITH msg AS (
            SELECT strftime(CAST(sent_at AS DATE), '%Y-%m') AS m,
                   COUNT(*) AS message_count,
                   COUNT(DISTINCT company_id) AS active_companies
            FROM messages
            WHERE direction = 'company_to_inf'
            GROUP BY m
        )
        SELECT m AS activity_month, message_count, active_companies
        FROM msg
        ORDER BY m
    """).df()


def get_continuation_ranking(con: duckdb.DuckDBPyConnection, limit: int = 15) -> pd.DataFrame:
    """Top N companies by billed_months (掲載開始日 → 解約日/今日).

    Uses sheet_contracts (契約マスタシート) as the source of truth.
    Falls back to DB-derived calculation if sheet is unavailable.
    """
    if sheet_available(con):
        return con.execute(f"""
            SELECT
                company_name,
                SUM(CAST(billed_months AS INTEGER))                              AS active_months,
                CASE WHEN MAX(CASE WHEN is_churned = 0 THEN 1 ELSE 0 END) = 1
                     THEN '継続中' ELSE '解約済' END                              AS status,
                MIN(start_date)                                                  AS start_date,
                MAX(churn_date)                                                  AS churn_date
            FROM sheet_contracts
            WHERE company_name IS NOT NULL
              AND company_name != ''
              AND billed_months IS NOT NULL
            GROUP BY company_name
            ORDER BY SUM(billed_months) DESC, MIN(start_date) ASC
            LIMIT {limit}
        """).df()

    # Fallback when sheet is not connected
    return con.execute(f"""
        WITH months AS (
            SELECT company_id,
                   strftime(CAST(sent_at AS DATE), '%Y-%m') AS m
            FROM messages WHERE direction = 'company_to_inf'
            UNION
            SELECT company_id,
                   strftime(CAST(applied_at AS DATE), '%Y-%m') AS m
            FROM applications
        ),
        agg AS (
            SELECT company_id,
                   COUNT(DISTINCT m) AS active_months,
                   COUNT(*) AS activity_count
            FROM months
            GROUP BY company_id
        )
        SELECT c.company_name, a.active_months, a.activity_count AS activity_count
        FROM agg a
        JOIN companies c USING (company_id)
        ORDER BY a.active_months DESC, a.activity_count DESC
        LIMIT {limit}
    """).df()


def get_top_companies_monthly_messages(con: duckdb.DuckDBPyConnection,
                                       top_n: int = 10) -> pd.DataFrame:
    """Top N companies by total messages, with per-month message counts."""
    return con.execute(f"""
        WITH ranked AS (
            SELECT company_id, COUNT(*) AS total
            FROM messages
            WHERE direction = 'company_to_inf'
            GROUP BY company_id
            ORDER BY total DESC
            LIMIT {top_n}
        )
        SELECT
            c.company_name,
            strftime(CAST(m.sent_at AS DATE), '%Y-%m') AS month,
            COUNT(*) AS msg_count
        FROM messages m
        JOIN companies c USING (company_id)
        WHERE m.direction = 'company_to_inf'
          AND m.company_id IN (SELECT company_id FROM ranked)
        GROUP BY c.company_name, month
        ORDER BY c.company_name, month
    """).df()


# ── Churn analysis ────────────────────────────────────────────────────────────

def get_overall_churn_rate(con: duckdb.DuckDBPyConnection) -> dict:
    """Overall churn rate: churned / total × 100."""
    result = con.execute("""
        SELECT
            COUNT(*)                                                  AS total,
            SUM(CASE WHEN status != 'active' THEN 1 ELSE 0 END)       AS churned
        FROM companies
    """).fetchone()
    total, churned = (result or (0, 0))
    rate = (churned / total * 100) if total else 0.0
    return {"total": int(total), "churned": int(churned), "rate_pct": round(rate, 1)}


def get_weekly_churn(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Per-ISO-week count of churn events for the last 16 weeks."""
    return con.execute("""
        SELECT
            strftime(CAST(churned_at AS DATE), '%G-W%V') AS iso_week,
            COUNT(*) AS churn_count
        FROM churn_events
        WHERE CAST(churned_at AS DATE) >= CURRENT_DATE - INTERVAL '16 weeks'
        GROUP BY iso_week
        ORDER BY iso_week
    """).df()


def get_churn_reason_breakdown(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Counts per churn reason (all-time)."""
    return con.execute("""
        SELECT reason, COUNT(*) AS count
        FROM churn_events
        GROUP BY reason
        ORDER BY count DESC
    """).df()


def get_churn_company_list(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """List of churned companies with reason and date."""
    return con.execute("""
        SELECT
            c.company_name,
            ce.churned_at,
            ce.reason,
            c.plan_type,
            c.cs_owner,
            c.prefecture
        FROM churn_events ce
        JOIN companies c USING (company_id)
        ORDER BY ce.churned_at DESC
    """).df()


# ── Application analysis ──────────────────────────────────────────────────────

def get_monthly_company_apps(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Per-company per-month application + accepted counts."""
    return con.execute("""
        SELECT
            c.company_id,
            c.company_name,
            strftime(CAST(a.applied_at AS DATE), '%Y-%m') AS month,
            COUNT(*) AS applied_count,
            SUM(CASE WHEN a.status = 'accepted' THEN 1 ELSE 0 END) AS accepted_count
        FROM applications a
        JOIN companies c USING (company_id)
        GROUP BY c.company_id, c.company_name, month
        ORDER BY c.company_name, month
    """).df()


def get_monthly_apps_total(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Total apps + accepted per month (for combo chart)."""
    return con.execute("""
        SELECT
            strftime(CAST(applied_at AS DATE), '%Y-%m') AS month,
            COUNT(*) AS applied_count,
            SUM(CASE WHEN status = 'accepted' THEN 1 ELSE 0 END) AS accepted_count
        FROM applications
        GROUP BY month
        ORDER BY month
    """).df()


def get_active_postings_list(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """掲載中&応募可（status=active）の全案件に応募者数・採用者数を付与して返す。"""
    postings = con.execute("""
        SELECT
            c.company_name                                          AS 企業名,
            jp.title                                                AS 案件名,
            jp.category                                             AS カテゴリ,
            CAST(jp.created_at AS DATE)                             AS 公開日,
            COUNT(a.application_id)                                 AS 応募者数,
            SUM(CASE WHEN a.status = 'accepted' THEN 1 ELSE 0 END) AS 採用者数
        FROM job_postings jp
        JOIN companies c USING (company_id)
        LEFT JOIN applications a USING (posting_id)
        WHERE jp.status = 'active'
        GROUP BY c.company_name, jp.posting_id, jp.title, jp.category, jp.created_at
        ORDER BY 応募者数 DESC, c.company_name
    """).df()

    # 解約済み企業を除外: L列(db_company_name=登録企業名)優先、空ならD列(company_name)フォールバック
    # DBの company_name は HTML エンコード(&amp; 等)や店舗名付きのケースがあるため
    # HTMLデコード後に部分一致で突合する
    try:
        import html as _html

        churned_df = con.execute("""
            SELECT company_name, db_company_name, is_churned
            FROM sheet_contracts
            WHERE company_name IS NOT NULL OR db_company_name IS NOT NULL
        """).df()
        churned_df["effective_name"] = churned_df["db_company_name"].where(
            churned_df["db_company_name"].notna() & (churned_df["db_company_name"] != ""),
            churned_df["company_name"]
        )
        by_name = churned_df.groupby("effective_name")["is_churned"].max()
        exclude = set(by_name[by_name == 1].index) - set(by_name[by_name == 0].index)

        if exclude:
            def _is_excluded(db_name: str) -> bool:
                decoded = _html.unescape(str(db_name))
                for ex in exclude:
                    ex_dec = _html.unescape(str(ex))
                    if ex_dec in decoded or decoded in ex_dec:
                        return True
                return False

            postings = postings[~postings["企業名"].apply(_is_excluded)].reset_index(drop=True)
    except Exception:
        pass

    return postings


def get_monthly_apps_from_sheet(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """月別応募数 from the 応募者数 sheet tab (sheet_app_counts)."""
    try:
        return con.execute("""
            SELECT
                strftime(CAST(posting_date AS DATE), '%Y-%m') AS month,
                SUM(app_count) AS applied_count
            FROM sheet_app_counts
            WHERE posting_date IS NOT NULL
            GROUP BY month
            ORDER BY month
        """).df()
    except Exception:
        return pd.DataFrame(columns=["month", "applied_count"])


def get_apps_by_prefecture_from_sheet(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """都道府県別応募数 (当月/先月) from sheet_individual_check.
    フィルター: status1=募集中, status2 ∈ {解約連絡あり, 公開中, 空白}
    """
    try:
        return con.execute("""
            SELECT
                region                           AS prefecture,
                COUNT(*)                         AS posting_count,
                SUM(COALESCE(apps_count, 0))     AS app_count_current,
                SUM(COALESCE(prev_apps_count, 0)) AS app_count_prev
            FROM sheet_individual_check
            WHERE status1 = '募集中'
              AND (status2 IN ('解約連絡あり', '公開中') OR status2 = '' OR status2 IS NULL)
              AND region IS NOT NULL AND region != '' AND region != 'オンライン'
            GROUP BY region
            ORDER BY (SUM(COALESCE(prev_apps_count, 0)) * 1.0 / NULLIF(COUNT(*), 0)) DESC NULLS LAST
        """).df()
    except Exception:
        return pd.DataFrame(columns=["prefecture", "posting_count", "app_count_current", "app_count_prev"])


def get_application_buckets(con: duckdb.DuckDBPyConnection) -> dict:
    """Companies grouped into application volume buckets."""
    df = con.execute("""
        SELECT c.company_id, c.company_name, c.status,
               COUNT(a.application_id) AS app_count
        FROM companies c
        LEFT JOIN applications a USING (company_id)
        GROUP BY c.company_id, c.company_name, c.status
        ORDER BY app_count DESC
    """).df()

    return {
        "zero":  df[df["app_count"] == 0],
        "le3":   df[(df["app_count"] >= 1) & (df["app_count"] <= 3)],
        "le5":   df[(df["app_count"] >= 1) & (df["app_count"] <= 5)],
        "ge15":  df[df["app_count"] >= 15],
        "ge20":  df[df["app_count"] >= 20],
        "ge25":  df[df["app_count"] >= 25],
        "all":   df,
    }


def get_apps_by_prefecture(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Application totals per prefecture (joined via company)."""
    return con.execute("""
        SELECT
            c.prefecture,
            COUNT(DISTINCT c.company_id)                               AS company_count,
            COUNT(a.application_id)                                    AS application_count,
            SUM(CASE WHEN a.status = 'accepted' THEN 1 ELSE 0 END)    AS accepted_count
        FROM companies c
        LEFT JOIN applications a USING (company_id)
        WHERE c.prefecture IS NOT NULL AND c.prefecture != ''
        GROUP BY c.prefecture
        ORDER BY application_count DESC
    """).df()


def get_apps_by_genre(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Application totals per posting category (genre)."""
    return con.execute("""
        SELECT
            COALESCE(NULLIF(jp.category, ''), 'その他') AS category,
            COUNT(a.application_id)                       AS application_count,
            SUM(CASE WHEN a.status = 'accepted' THEN 1 ELSE 0 END) AS accepted_count
        FROM job_postings jp
        LEFT JOIN applications a USING (posting_id)
        GROUP BY category
        ORDER BY application_count DESC
    """).df()


# ── Company detail ────────────────────────────────────────────────────────────

def get_company_info(con: duckdb.DuckDBPyConnection, company_id: str) -> pd.DataFrame:
    return con.execute("""
        SELECT company_id, company_name, plan_type, status, cs_owner,
               contract_start_date, contract_end_date
        FROM companies
        WHERE company_id = ?
    """, [company_id]).df()


def get_company_active_months(con: duckdb.DuckDBPyConnection, company_id: str) -> int:
    result = con.execute("""
        WITH months AS (
            SELECT strftime(CAST(sent_at AS DATE), '%Y-%m') AS m
            FROM messages
            WHERE company_id = ? AND direction = 'company_to_inf'
            UNION
            SELECT strftime(CAST(applied_at AS DATE), '%Y-%m') AS m
            FROM applications
            WHERE company_id = ?
        )
        SELECT COUNT(DISTINCT m) FROM months
    """, [company_id, company_id]).fetchone()
    return int(result[0]) if result else 0


def get_company_weekly_messages(con: duckdb.DuckDBPyConnection, company_id: str) -> pd.DataFrame:
    return con.execute("""
        SELECT
            strftime(CAST(sent_at AS DATE), '%G-W%V') AS iso_week,
            COUNT(*) AS message_count
        FROM messages
        WHERE company_id = ?
          AND direction = 'company_to_inf'
          AND CAST(sent_at AS DATE) >= CURRENT_DATE - INTERVAL '12 weeks'
        GROUP BY iso_week
        ORDER BY iso_week
    """, [company_id]).df()


def get_company_postings(con: duckdb.DuckDBPyConnection, company_id: str) -> pd.DataFrame:
    return con.execute("""
        SELECT
            jp.posting_id, jp.title, jp.status,
            jp.image_count,
            LENGTH(jp.description) AS description_length,
            jp.compensation_type, jp.has_deadline, jp.has_sample,
            jp.platform_targets, jp.required_followers, jp.category,
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
        WHERE jp.company_id = ?
        ORDER BY attractiveness_score DESC
    """, [company_id]).df()


# ── Retention analytics from contract master sheet ────────────────────────────

def sheet_available(con: duckdb.DuckDBPyConnection) -> bool:
    """Check if sheet_contracts table is registered."""
    try:
        con.execute("SELECT 1 FROM sheet_contracts LIMIT 1").fetchone()
        return True
    except Exception:
        return False


def get_monthly_churn_rate(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """
    月次チャーンレート（解約権利ベース）。

    計算式:
      分子 = 当月に解約した企業数（churn_date が当月内 かつ 必須期間経過済み）
      分母 = 当月に解約可能だった企業数
             （当月アクティブ かつ service_start_date + contract_months <= 当月1日）

    Returns: DataFrame(month, churned, eligible, churn_rate)
    """
    if not sheet_available(con):
        return pd.DataFrame()

    raw = con.execute("""
        SELECT
            company_name,
            service_start_date,
            CAST(contract_months AS INTEGER) AS contract_months,
            churn_date,
            CAST(is_churned AS INTEGER) AS is_churned
        FROM sheet_contracts
        WHERE service_start_date IS NOT NULL
          AND contract_months IS NOT NULL
    """).df()

    if raw.empty:
        return pd.DataFrame()

    today    = pd.Timestamp.today().normalize()
    # データの最古 service_start_date の翌月から当月まで
    min_start = raw["service_start_date"].min()
    if pd.isna(min_start):
        return pd.DataFrame()
    start_month = (pd.Timestamp(min_start) + pd.DateOffset(months=1)).replace(day=1)
    months       = pd.date_range(start_month, today.replace(day=1), freq="MS")

    rows = []
    for m in months:
        m_end = m + pd.offsets.MonthEnd(0)
        churned  = 0
        eligible = 0

        for _, r in raw.iterrows():
            ssd      = pd.Timestamp(r["service_start_date"]).replace(day=1)
            min_end  = (ssd + pd.DateOffset(months=int(r["contract_months"]))).replace(day=1)
            past_min = min_end <= m  # 必須期間満了済み

            churn_ts = (
                pd.Timestamp(r["churn_date"]).replace(day=1)
                if pd.notna(r["churn_date"]) else None
            )
            is_ch = r["is_churned"] == 1

            # 当月アクティブ: 開始済み かつ（解約していない OR 当月以降に解約）
            active = ssd <= m_end and (not is_ch or (churn_ts is not None and churn_ts >= m))

            if active and past_min:
                eligible += 1
                # 当月に解約（churn_date の月が m と一致）
                if is_ch and churn_ts is not None and churn_ts == m:
                    churned += 1

        rows.append({
            "month":       m.strftime("%Y-%m"),
            "churned":     churned,
            "eligible":    eligible,
            "churn_rate":  round(churned / eligible * 100, 1) if eligible > 0 else None,
        })

    return pd.DataFrame(rows)


def get_retention_kpis(con: duckdb.DuckDBPyConnection) -> dict:
    """Headline retention KPIs from sheet_contracts."""
    if not sheet_available(con):
        return {}

    total       = con.execute("SELECT COUNT(*) FROM sheet_contracts").fetchone()[0]
    churned     = con.execute(
        "SELECT COUNT(*) FROM sheet_contracts WHERE is_churned = 1"
    ).fetchone()[0]
    continuing  = total - churned

    # 6/12 months retention:
    # 分母: AN列（最低契約期間）が経過した企業のみ（評価可能コホート）
    # 分子: billed_months >= 6 or 12
    six_month = con.execute("""
        SELECT
            COUNT(*) AS denom,
            SUM(CASE WHEN billed_months >= 6 THEN 1 ELSE 0 END) AS reached_6m
        FROM sheet_contracts
        WHERE start_date IS NOT NULL
          AND contract_months IS NOT NULL
          AND DATEDIFF('month', start_date, CURRENT_DATE) >= contract_months
    """).fetchone()

    twelve_month = con.execute("""
        SELECT
            COUNT(*) AS denom,
            SUM(CASE WHEN billed_months >= 12 THEN 1 ELSE 0 END) AS reached_12m
        FROM sheet_contracts
        WHERE start_date IS NOT NULL
          AND contract_months IS NOT NULL
          AND DATEDIFF('month', start_date, CURRENT_DATE) >= contract_months
    """).fetchone()

    # 平均LTV = 解約済み企業の課金月数の平均
    avg_ltv = con.execute("""
        SELECT AVG(billed_months)
        FROM sheet_contracts
        WHERE is_churned = 1 AND billed_months > 0
    """).fetchone()[0] or 0

    return {
        "total":               int(total),
        "continuing":          int(continuing),
        "churned":             int(churned),
        "churn_rate":          round((churned / total * 100) if total else 0, 1),
        "six_m_denom":         int(six_month[0] or 0),
        "six_m_reached":       int(six_month[1] or 0),
        "six_m_rate":          round((six_month[1] / six_month[0] * 100)
                                     if six_month[0] else 0, 1),
        "twelve_m_denom":      int(twelve_month[0] or 0),
        "twelve_m_reached":    int(twelve_month[1] or 0),
        "twelve_m_rate":       round((twelve_month[1] / twelve_month[0] * 100)
                                     if twelve_month[0] else 0, 1),
        "avg_ltv_months":      round(float(avg_ltv), 1),
    }


def get_active_companies_retention(con: duckdb.DuckDBPyConnection) -> dict:
    """現在掲載中（is_churned=0）企業の継続率分析（AN列ベース評価可能コホート）。"""
    if not sheet_available(con):
        return {}

    # 全掲載中企業数（status='公開中' or '解約連絡あり'）※解約連絡ありはchurn_dateあり（予定日）でも含む
    total_active = con.execute("""
        SELECT COUNT(*) FROM sheet_contracts
        WHERE start_date IS NOT NULL
          AND status IN ('公開中', '解約連絡あり')
    """).fetchone()[0] or 0

    # 評価可能コホート（AN列の月数が経過した企業）
    evaluable = con.execute("""
        SELECT
            COUNT(*) AS denom,
            SUM(CASE WHEN billed_months >= 6  THEN 1 ELSE 0 END) AS reached_6m,
            SUM(CASE WHEN billed_months >= 12 THEN 1 ELSE 0 END) AS reached_12m
        FROM sheet_contracts
        WHERE start_date IS NOT NULL
          AND status IN ('公開中', '解約連絡あり')
          AND contract_months IS NOT NULL
          AND DATEDIFF('month', start_date, CURRENT_DATE) >= contract_months
    """).fetchone()

    denom     = int(evaluable[0] or 0)
    reached6  = int(evaluable[1] or 0)
    reached12 = int(evaluable[2] or 0)

    # 継続月数バケット（全掲載中）
    buckets = con.execute("""
        SELECT
            CASE
                WHEN billed_months < 3  THEN '〜2ヶ月'
                WHEN billed_months < 6  THEN '3〜5ヶ月'
                WHEN billed_months < 12 THEN '6〜11ヶ月'
                WHEN billed_months < 24 THEN '12〜23ヶ月'
                ELSE '24ヶ月〜'
            END AS bucket,
            COUNT(*) AS company_count
        FROM sheet_contracts
        WHERE start_date IS NOT NULL
          AND status IN ('公開中', '解約連絡あり')
        GROUP BY bucket
        ORDER BY MIN(billed_months)
    """).df()

    # プラン別内訳（評価可能コホートのみ）
    by_plan = con.execute("""
        SELECT
            COALESCE(plan_name, '不明') AS plan,
            COUNT(*) AS company_count,
            ROUND(AVG(billed_months), 1) AS avg_months,
            SUM(CASE WHEN billed_months >= 6  THEN 1 ELSE 0 END) AS reached_6m,
            SUM(CASE WHEN billed_months >= 12 THEN 1 ELSE 0 END) AS reached_12m
        FROM sheet_contracts
        WHERE start_date IS NOT NULL
          AND status IN ('公開中', '解約連絡あり')
          AND contract_months IS NOT NULL
          AND DATEDIFF('month', start_date, CURRENT_DATE) >= contract_months
        GROUP BY plan_name
        ORDER BY company_count DESC
    """).df()

    return {
        "total_active":  total_active,
        "evaluable":     denom,
        "not_evaluable": total_active - con.execute("""
            SELECT COUNT(*) FROM sheet_contracts
            WHERE start_date IS NOT NULL
              AND status IN ('公開中', '解約連絡あり')
              AND contract_months IS NOT NULL
        """).fetchone()[0],
        "reached_6m":    reached6,
        "rate_6m":       round(reached6 / denom * 100, 1) if denom else 0,
        "reached_12m":   reached12,
        "rate_12m":      round(reached12 / denom * 100, 1) if denom else 0,
        "buckets":       buckets,
        "by_plan":       by_plan,
    }



def get_avg_duration_all(con: duckdb.DuckDBPyConnection) -> dict:
    """評価可能コホート（AN列経過済み）の平均継続月数 + プラン別内訳。"""
    if not sheet_available(con):
        return {}
    try:
        row = con.execute("""
            SELECT
                COUNT(*)           AS total,
                AVG(billed_months) AS avg_all,
                SUM(CASE WHEN is_churned = 0 THEN 1 ELSE 0 END) AS active_count,
                SUM(CASE WHEN is_churned = 1 THEN 1 ELSE 0 END) AS churned_count,
                AVG(CASE WHEN is_churned = 1 THEN billed_months END) AS avg_churned
            FROM sheet_contracts
            WHERE billed_months IS NOT NULL AND billed_months > 0
              AND contract_months IS NOT NULL
              AND DATEDIFF('month', start_date, CURRENT_DATE) >= contract_months
        """).fetchone()
        plan_df = con.execute("""
            SELECT
                COALESCE(NULLIF(TRIM(plan_name), ''), '（プラン不明）') AS plan,
                COUNT(*)           AS company_count,
                ROUND(AVG(billed_months), 1) AS avg_months,
                ROUND(AVG(CASE WHEN is_churned = 1 THEN billed_months END), 1) AS avg_churned_months,
                SUM(CASE WHEN is_churned = 0 THEN 1 ELSE 0 END) AS active_count
            FROM sheet_contracts
            WHERE billed_months IS NOT NULL AND billed_months > 0
              AND contract_months IS NOT NULL
              AND DATEDIFF('month', start_date, CURRENT_DATE) >= contract_months
            GROUP BY plan
            ORDER BY avg_months DESC
        """).df()
        # 全社（フィルターなし）の平均も取得
        row_all = con.execute("""
            SELECT COUNT(*), AVG(billed_months)
            FROM sheet_contracts
            WHERE billed_months IS NOT NULL AND billed_months > 0
        """).fetchone()
        return {
            "total":         int(row[0] or 0),
            "avg_all":       round(float(row[1] or 0), 1),
            "active_count":  int(row[2] or 0),
            "churned_count": int(row[3] or 0),
            "avg_churned":   round(float(row[4] or 0), 1),
            "by_plan":       plan_df,
            "total_unfiltered": int(row_all[0] or 0),
            "avg_all_unfiltered": round(float(row_all[1] or 0), 1),
        }
    except Exception:
        return {}


def get_min_contract_analysis(con: duckdb.DuckDBPyConnection) -> dict:
    """AN列（最低契約期間）と実際の継続月数を比較する。"""
    if not sheet_available(con):
        return {}
    try:
        # 最低契約期間が設定されている行のみ対象
        # 同じ会社名が複数回登場する企業（再開企業）は除外
        base = con.execute("""
            SELECT
                company_name,
                billed_months,
                contract_months  AS min_period,
                is_churned,
                churn_date
            FROM sheet_contracts
            WHERE contract_months IS NOT NULL AND billed_months IS NOT NULL
              AND billed_months > 0
              AND company_name IN (
                  SELECT company_name
                  FROM sheet_contracts
                  GROUP BY company_name
                  HAVING COUNT(*) = 1
              )
        """).df()
        if base.empty:
            return {}

        # 解約済み企業のみで最低期間との比較
        # billed_months は月差分（例: 11月開始→1月解約 = 2）
        # contract_months = 3 の場合、最終月は開始月+2 → billed_months == contract_months - 1 が「ちょうど」
        churned = base[base["is_churned"] == 1].copy()
        before = churned[churned["billed_months"] < churned["min_period"] - 1]
        exact  = churned[churned["billed_months"] == churned["min_period"] - 1]
        # 最低期間以上続けた企業（継続中 + 解約済みで期間超え）
        beyond = base[base["billed_months"] >= base["min_period"]]

        return {
            "before_names":   before["company_name"].dropna().tolist(),
            "before_count":   len(before),
            "exact_count":    len(exact),
            "exact_names":    exact["company_name"].dropna().tolist(),
            "beyond_count":   len(beyond),
            "beyond_avg":     round(float(beyond["billed_months"].mean()), 1) if len(beyond) else 0,
        }
    except Exception:
        return {}


def get_retention_by_plan(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    if not sheet_available(con):
        return pd.DataFrame()
    return con.execute("""
        SELECT
            COALESCE(plan_name, '不明') AS plan_name,
            COUNT(*) AS total,
            SUM(CASE WHEN is_churned = 0 THEN 1 ELSE 0 END) AS continuing,
            SUM(CASE WHEN is_churned = 1 THEN 1 ELSE 0 END) AS churned,
            ROUND(
                SUM(CASE WHEN is_churned = 0 THEN 1 ELSE 0 END) * 100.0
                / NULLIF(COUNT(*), 0), 1
            ) AS retention_pct,
            ROUND(AVG(billed_months), 1) AS avg_active_months
        FROM sheet_contracts
        GROUP BY plan_name
        HAVING COUNT(*) >= 2
        ORDER BY total DESC
    """).df()


def get_retention_by_payment(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    if not sheet_available(con):
        return pd.DataFrame()
    return con.execute("""
        SELECT
            COALESCE(payment_method, '不明') AS payment_method,
            COUNT(*) AS total,
            SUM(CASE WHEN is_churned = 0 THEN 1 ELSE 0 END) AS continuing,
            ROUND(SUM(CASE WHEN is_churned = 0 THEN 1 ELSE 0 END) * 100.0
                  / NULLIF(COUNT(*), 0), 1) AS retention_pct
        FROM sheet_contracts
        GROUP BY payment_method
        HAVING COUNT(*) >= 1
        ORDER BY total DESC
    """).df()


def get_retention_by_cs_owner(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    if not sheet_available(con):
        return pd.DataFrame()
    return con.execute("""
        SELECT
            COALESCE(cs_owner, '不明') AS cs_owner,
            COUNT(*) AS total,
            SUM(CASE WHEN is_churned = 0 THEN 1 ELSE 0 END) AS continuing,
            ROUND(SUM(CASE WHEN is_churned = 0 THEN 1 ELSE 0 END) * 100.0
                  / NULLIF(COUNT(*), 0), 1) AS retention_pct,
            ROUND(AVG(billed_months), 1) AS avg_active_months
        FROM sheet_contracts
        GROUP BY cs_owner
        HAVING COUNT(*) >= 3
        ORDER BY total DESC
    """).df()


def get_retention_by_genre(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    if not sheet_available(con):
        return pd.DataFrame()
    return con.execute("""
        SELECT
            COALESCE(genre, '不明') AS genre,
            COUNT(*) AS total,
            SUM(CASE WHEN is_churned = 0 THEN 1 ELSE 0 END) AS continuing,
            ROUND(SUM(CASE WHEN is_churned = 0 THEN 1 ELSE 0 END) * 100.0
                  / NULLIF(COUNT(*), 0), 1) AS retention_pct
        FROM sheet_contracts
        GROUP BY genre
        HAVING COUNT(*) >= 2
        ORDER BY total DESC
    """).df()


def get_company_retention_timeline(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """
    企業別 月次継続タイムライン。
    データソース: sheet_timeline_source（gid=0, E列=取引先名）を優先。
                  未登録なら sheet_contracts にフォールバック。
    Returns DataFrame: company_name, ym (YYYY-MM), code
      code: 1=継続中, 2=解約月, 3=再開月（解約後の再契約初月）
    同名企業の複数行 = 再開契約として扱う。
    企業は最初の掲載開始日の昇順でソート済み。
    """
    # ソーステーブルの優先順位: sheet_timeline_source > sheet_contracts
    tables = con.execute("SHOW TABLES").df()["name"].tolist()
    if "sheet_timeline_source" in tables:
        source_table = "sheet_timeline_source"
    elif "sheet_contracts" in tables:
        source_table = "sheet_contracts"
    else:
        return pd.DataFrame()

    raw = con.execute(f"""
        SELECT
            company_name,
            start_date,
            churn_date,
            CAST(is_churned AS INTEGER) AS is_churned,
            CAST(COALESCE(billed_months, 0) AS INTEGER) AS billed_months
        FROM {source_table}
        WHERE start_date IS NOT NULL
          AND TRIM(COALESCE(company_name, '')) != ''
        ORDER BY company_name, start_date
    """).df()

    if raw.empty:
        return pd.DataFrame()

    today = pd.Timestamp.today().normalize().replace(day=1)
    records = []

    # 企業ごとに処理（複数契約 = 再開企業を検出）
    for company, grp in raw.groupby("company_name", sort=False):
        grp = grp.sort_values("start_date").reset_index(drop=True)
        prev_was_churned = False

        for idx, row in grp.iterrows():
            start_ts = pd.Timestamp(row["start_date"]).replace(day=1)
            is_churned = row["is_churned"] == 1

            if is_churned:
                if pd.notna(row["churn_date"]):
                    end_ts = pd.Timestamp(row["churn_date"]).replace(day=1)
                else:
                    bm = max(1, int(row["billed_months"]))
                    end_ts = (start_ts + pd.DateOffset(months=bm - 1)).replace(day=1)
                churn_ym = end_ts.strftime("%Y-%m")
            else:
                end_ts = today
                churn_ym = None

            is_reopen = prev_was_churned and idx > 0
            cur = start_ts
            while cur <= end_ts:
                ym = cur.strftime("%Y-%m")
                if is_reopen and ym == start_ts.strftime("%Y-%m"):
                    code = 3  # 再開月
                elif is_churned and ym == churn_ym:
                    code = 2  # 解約月
                else:
                    code = 1  # 継続中
                records.append({"company_name": company, "ym": ym, "code": code})
                cur = (cur + pd.DateOffset(months=1)).replace(day=1)

            prev_was_churned = is_churned

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)
    # 同企業×同月は最大値（再開 > 解約 > 継続）
    df = df.groupby(["company_name", "ym"], as_index=False)["code"].max()

    # 企業ソート: 最初の掲載開始日（昇順）
    first_start = (
        raw.groupby("company_name")["start_date"]
        .min()
        .sort_values()
    )
    df["sort_key"] = df["company_name"].map(first_start)
    df = df.sort_values(["sort_key", "company_name", "ym"])

    return df[["company_name", "ym", "code"]]


def get_cohort_retention(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """
    Cohort retention heatmap: cohort_month (掲載開始日の月) × months_since_start → retention %.

    生存判定は 掲載開始日 と 解約日 の日付計算で行う：
      - 解約していない契約は常に生存
      - 解約した契約は (M+offset) < billed_months なら生存（billed_months分は課金された）
    """
    if not sheet_available(con):
        return pd.DataFrame()

    raw = con.execute("""
        SELECT
            strftime(start_date, '%Y-%m') AS cohort,
            is_churned,
            billed_months
        FROM sheet_contracts
        WHERE start_date IS NOT NULL
    """).df()

    if raw.empty:
        return pd.DataFrame()

    today = pd.Timestamp.today().normalize()
    rows = []

    for cohort_key, group in raw.groupby("cohort"):
        N = len(group)
        cohort_start = pd.Timestamp(cohort_key + "-01")
        max_offset = (today.year - cohort_start.year) * 12 + (today.month - cohort_start.month)

        for offset in range(0, max(0, max_offset) + 1):
            alive = 0
            for _, r in group.iterrows():
                if r["is_churned"] == 0:
                    alive += 1
                else:
                    bm = r.get("billed_months")
                    if pd.notna(bm) and offset < int(bm):
                        alive += 1
            rows.append({
                "cohort":         cohort_key,
                "m_offset":       offset,
                "alive":          alive,
                "total":          N,
                "retention_pct":  round(alive / N * 100, 1) if N else 0,
            })

    return pd.DataFrame(rows)


def get_followup_companies(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """
    Companies needing CS follow-up:
      - 接点経過日 long
      - 状況 = 未連絡停止 / 解約連絡あり / 強制解約 など
      - 直近のアクション必要
    """
    if not sheet_available(con):
        return pd.DataFrame()
    return con.execute("""
        SELECT
            company_name,
            status,
            response_status,
            contact_days_ago,
            cs_owner,
            plan_name
        FROM sheet_contracts
        WHERE
            (status LIKE '%未連絡%'
             OR status LIKE '%解約連絡%'
             OR status LIKE '%停止%'
             OR response_status LIKE '%要連絡%'
             OR response_status LIKE '%返信待ち%')
          AND (status NOT LIKE '%解約済%' OR status IS NULL)
        ORDER BY status, company_name
    """).df()


# ── Slack churn report queries ────────────────────────────────────────────────

def slack_available(con: duckdb.DuckDBPyConnection) -> bool:
    """Check if slack_churns table is registered."""
    try:
        con.execute("SELECT 1 FROM slack_churns LIMIT 1").fetchone()
        return True
    except Exception:
        return False


def get_slack_churn_timeline(con: duckdb.DuckDBPyConnection,
                              days: int = 60) -> pd.DataFrame:
    """Recent churn reports from Slack, newest first."""
    if not slack_available(con):
        return pd.DataFrame()
    return con.execute(f"""
        SELECT
            posted_at,
            reporter,
            company_name,
            subsidiary,
            reason,
            raw_text
        FROM slack_churns
        WHERE posted_at >= CURRENT_DATE - INTERVAL '{days} days'
        ORDER BY posted_at DESC
    """).df()


def get_slack_churn_reason_breakdown(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Counts per parsed reason (top-N grouping)."""
    if not slack_available(con):
        return pd.DataFrame()
    return con.execute("""
        SELECT
            CASE
                WHEN reason IS NULL OR reason = ''  THEN '未分類'
                WHEN reason IN ('不明','未分類')      THEN '不明・未分類'
                ELSE reason
            END AS reason_label,
            COUNT(*) AS count
        FROM slack_churns
        GROUP BY reason_label
        ORDER BY count DESC
    """).df()


def get_slack_weekly_churn(con: duckdb.DuckDBPyConnection,
                           start_date: str = "2025-11-01") -> pd.DataFrame:
    """Per-week churn report counts from start_date to today.
    Returns columns: week_start (Monday DATE), label (e.g. '2026年5月1週目'), churn_count.
    """
    if not slack_available(con):
        return pd.DataFrame()

    df = con.execute(f"""
        SELECT
            DATE_TRUNC('week', CAST(posted_at AS DATE)) AS week_start,
            COUNT(*) AS churn_count
        FROM slack_churns
        WHERE CAST(posted_at AS DATE) >= DATE '{start_date}'
        GROUP BY week_start
        ORDER BY week_start
    """).df()

    def _japanese_label(d):
        if pd.isna(d):
            return ""
        d = pd.Timestamp(d)
        # 月内の何週目か（その月の1日からの位置で判定）
        week_of_month = (d.day - 1) // 7 + 1
        return f"{d.year}年{d.month}月{week_of_month}週目"

    df["label"] = df["week_start"].apply(_japanese_label)
    return df


def get_slack_monthly_churn(con: duckdb.DuckDBPyConnection,
                            start_date: str = "2025-11-01") -> pd.DataFrame:
    """Per-month churn report counts from start_date to today.
    Returns columns: month_start (DATE), label (e.g. '2026年5月'), churn_count.
    """
    if not slack_available(con):
        return pd.DataFrame()

    df = con.execute(f"""
        SELECT
            DATE_TRUNC('month', CAST(posted_at AS DATE)) AS month_start,
            COUNT(*) AS churn_count
        FROM slack_churns
        WHERE CAST(posted_at AS DATE) >= DATE '{start_date}'
        GROUP BY month_start
        ORDER BY month_start
    """).df()

    df["label"] = df["month_start"].apply(
        lambda d: f"{pd.Timestamp(d).year}年{pd.Timestamp(d).month}月" if not pd.isna(d) else ""
    )
    return df


def get_slack_kpis(con: duckdb.DuckDBPyConnection) -> dict:
    """Headline KPIs for Slack churn timeline."""
    if not slack_available(con):
        return {}
    last_24h, last_7d, last_30d, total = con.execute("""
        SELECT
            SUM(CASE WHEN posted_at >= CURRENT_DATE - INTERVAL '1 day'   THEN 1 ELSE 0 END),
            SUM(CASE WHEN posted_at >= CURRENT_DATE - INTERVAL '7 days'  THEN 1 ELSE 0 END),
            SUM(CASE WHEN posted_at >= CURRENT_DATE - INTERVAL '30 days' THEN 1 ELSE 0 END),
            COUNT(*)
        FROM slack_churns
    """).fetchone()
    return {
        "last_24h":  int(last_24h or 0),
        "last_7d":   int(last_7d or 0),
        "last_30d":  int(last_30d or 0),
        "total":     int(total or 0),
    }


def get_3source_consistency(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """
    Cross-check companies reported in Slack against shop sheet and DB.
    Helps spot 'reported in Slack but not yet in sheet/DB' cases.
    """
    if not slack_available(con):
        return pd.DataFrame()

    # Get distinct churned companies from Slack (latest posting per company)
    slack_df = con.execute("""
        SELECT
            company_name,
            ARG_MAX(posted_at, posted_at) AS last_reported,
            ARG_MAX(reason,    posted_at) AS latest_reason
        FROM slack_churns
        WHERE company_name IS NOT NULL
        GROUP BY company_name
        ORDER BY last_reported DESC
    """).df()

    # Check sheet
    if sheet_available(con):
        sheet_companies = con.execute("""
            SELECT DISTINCT company_name FROM sheet_contracts WHERE company_name IS NOT NULL
        """).df()["company_name"].tolist()
    else:
        sheet_companies = []

    def _normalize(s):
        if not s: return ""
        return str(s).replace(" ", "").replace("　", "").lower()

    sheet_norm = {_normalize(c) for c in sheet_companies}

    slack_df["in_sheet"] = slack_df["company_name"].apply(
        lambda c: _normalize(c) in sheet_norm
    )
    return slack_df


# ── 未回収債権 ────────────────────────────────────────────────────────────────

def uncollected_available(con: duckdb.DuckDBPyConnection) -> bool:
    try:
        con.execute("SELECT 1 FROM billing_uncollected LIMIT 1")
        return True
    except Exception:
        return False


def get_uncollected_kpis(con: duckdb.DuckDBPyConnection) -> dict:
    """件数・総額・企業数のKPI。"""
    if not uncollected_available(con):
        return {}
    row = con.execute("""
        SELECT
            COUNT(*)                          AS invoice_count,
            SUM(invoice_amount)               AS total_amount,
            COUNT(DISTINCT company)           AS company_count,
            SUM(CASE WHEN confirmed_type = '確認中' THEN invoice_amount ELSE 0 END) AS in_review_amount,
            SUM(CASE WHEN due_date < CURRENT_DATE THEN invoice_amount ELSE 0 END)   AS overdue_amount
        FROM billing_uncollected
    """).fetchone()
    return {
        "invoice_count":   int(row[0] or 0),
        "total_amount":    int(row[1] or 0),
        "company_count":   int(row[2] or 0),
        "in_review_amount": int(row[3] or 0),
        "overdue_amount":  int(row[4] or 0),
    }


def get_uncollected_by_company(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """企業別 未回収サマリー（決済残額・件数・最終決済期日）。"""
    if not uncollected_available(con):
        return pd.DataFrame()
    return con.execute("""
        SELECT
            company                                     AS 企業名,
            MAX(remaining)                              AS 決済残額,
            COUNT(*)                                    AS 未払い件数,
            SUM(invoice_amount)                         AS 未払い総額,
            MAX(due_date)::VARCHAR                      AS 最終決済期日,
            MAX(confirmed_type)                         AS ステータス,
            MAX(status)                                 AS 連絡状況
        FROM billing_uncollected
        WHERE company IS NOT NULL
        GROUP BY company
        ORDER BY MAX(remaining) DESC NULLS LAST, SUM(invoice_amount) DESC
    """).df()


def get_uncollected_detail(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """未回収明細一覧（企業名・期日・金額・請求書番号・ステータス）。"""
    if not uncollected_available(con):
        return pd.DataFrame()
    return con.execute("""
        SELECT
            company          AS 企業名,
            due_date::VARCHAR AS 決済期日,
            invoice_amount   AS 請求金額,
            remaining        AS 決済残額,
            invoice_no       AS 請求書番号,
            confirmed_type   AS 種別,
            status           AS 連絡状況
        FROM billing_uncollected
        ORDER BY company, due_date
    """).df()


def get_apps_bucket_by_month(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """
    先月・当月の応募数バケット別 案件数（積み上げ棒グラフ用）。
    対象: status1='募集中' AND status2 IN ('解約連絡あり','公開中','空白')
    先月: I列（post_create_date）が当月の案件を除外（先月は存在しなかった案件）
    バケット: 0/1〜4/5〜9/10〜14/15〜19/20〜24/25〜29/30以上
    """
    import datetime
    today = datetime.date.today()
    cur_label   = f"{today.year}年{today.month}月（当月）"
    prev_month  = (today.replace(day=1) - datetime.timedelta(days=1))
    prev_label  = f"{prev_month.year}年{prev_month.month}月（先月）"
    # 当月1日（先月フィルター用）
    cur_month_start = today.replace(day=1).isoformat()

    bucket_case = lambda col: f"""
        CASE
            WHEN COALESCE({col}, 0) = 0  THEN '0件'
            WHEN {col} <  5              THEN '1〜4件'
            WHEN {col} < 10              THEN '5〜9件'
            WHEN {col} < 15              THEN '10〜14件'
            WHEN {col} < 20              THEN '15〜19件'
            WHEN {col} < 25              THEN '20〜24件'
            WHEN {col} < 30              THEN '25〜29件'
            ELSE                              '30件以上'
        END
    """

    df = con.execute(f"""
        SELECT '{cur_label}' AS month,
               {bucket_case('apps_count')} AS bucket,
               COUNT(*) AS 案件数
        FROM sheet_individual_check
        WHERE status1 = '募集中'
          AND COALESCE(status2, '') IN ('解約連絡あり', '公開中', '')
        GROUP BY bucket

        UNION ALL

        SELECT '{prev_label}' AS month,
               {bucket_case('prev_apps_count')} AS bucket,
               COUNT(*) AS 案件数
        FROM sheet_individual_check
        WHERE status1 = '募集中'
          AND COALESCE(status2, '') IN ('解約連絡あり', '公開中', '')
          AND (
              post_create_date IS NULL
              OR TRY_STRPTIME(post_create_date, '%m/%d/%Y') < DATE '{cur_month_start}'
          )
        GROUP BY bucket
    """).df()

    # 月・バケットの順序を固定
    month_order  = [prev_label, cur_label]
    bucket_order = ['0件','1〜4件','5〜9件','10〜14件','15〜19件','20〜24件','25〜29件','30件以上']
    df["month"]  = pd.Categorical(df["month"],  categories=month_order,  ordered=True)
    df["bucket"] = pd.Categorical(df["bucket"], categories=bucket_order, ordered=True)
    return df.sort_values(["month", "bucket"])


# ── 解約詳細シート分析（2025/12以降）─────────────────────────────────────────

def churn_detail_available(con: duckdb.DuckDBPyConnection) -> bool:
    try:
        con.execute("SELECT 1 FROM sheet_churn_detail LIMIT 1")
        return True
    except Exception:
        return False


def get_churn_detail_kpis(con: duckdb.DuckDBPyConnection) -> dict:
    """解約詳細シートの基本KPI。
    アンケート未回答 = センチメント空欄 OR J列（reason_detail）に'アンケート未回答'を含む
    """
    row = con.execute("""
        SELECT
            COUNT(*)                                          AS total,
            ROUND(AVG(billed_months), 1)                     AS avg_months,
            SUM(CASE WHEN sentiment = 'ネガティブ'   THEN 1 ELSE 0 END) AS negative,
            SUM(CASE WHEN sentiment = 'ニュートラル' THEN 1 ELSE 0 END) AS neutral,
            SUM(CASE WHEN sentiment = 'ポジティブ'   THEN 1 ELSE 0 END) AS positive,
            SUM(CASE WHEN reason_detail LIKE '%アンケート未回答%'
            THEN 1 ELSE 0 END) AS unknown
        FROM sheet_churn_detail
    """).fetchone()
    return {
        "total":    int(row[0] or 0),
        "avg_months": float(row[1] or 0),
        "negative": int(row[2] or 0),
        "neutral":  int(row[3] or 0),
        "positive": int(row[4] or 0),
        "unknown":  int(row[5] or 0),
    }


def get_churn_by_month(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """月別解約数。"""
    return con.execute("""
        SELECT
            churn_ym                  AS 解約月,
            COUNT(*)                  AS 解約数,
            ROUND(AVG(billed_months), 1) AS 平均利用月数
        FROM sheet_churn_detail
        GROUP BY churn_ym
        ORDER BY churn_ym
    """).df()


def get_churn_reasons(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """解約理由①②③を縦持ちに展開して集計（上位15）。"""
    return con.execute("""
        SELECT reason, COUNT(*) AS 件数
        FROM (
            SELECT reason1 AS reason FROM sheet_churn_detail WHERE reason1 IS NOT NULL AND reason1 != ''
            UNION ALL
            SELECT reason2 FROM sheet_churn_detail WHERE reason2 IS NOT NULL AND reason2 != ''
            UNION ALL
            SELECT reason3 FROM sheet_churn_detail WHERE reason3 IS NOT NULL AND reason3 != ''
        )
        GROUP BY reason
        ORDER BY 件数 DESC
        LIMIT 15
    """).df()


def get_churn_reasons_by_month(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """解約月×理由の件数（理由①②③ 合算）。積み上げ棒グラフ用。"""
    return con.execute("""
        SELECT churn_ym AS 解約月, reason, COUNT(*) AS 件数
        FROM (
            SELECT churn_ym, reason1 AS reason FROM sheet_churn_detail
            WHERE reason1 IS NOT NULL AND reason1 != ''
            UNION ALL
            SELECT churn_ym, reason2 FROM sheet_churn_detail
            WHERE reason2 IS NOT NULL AND reason2 != ''
            UNION ALL
            SELECT churn_ym, reason3 FROM sheet_churn_detail
            WHERE reason3 IS NOT NULL AND reason3 != ''
        )
        WHERE churn_ym IS NOT NULL AND churn_ym != ''
        GROUP BY churn_ym, reason
        ORDER BY churn_ym, 件数 DESC
    """).df()


def get_churn_sentiment_by_month(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """月別×センチメント別 解約数。"""
    return con.execute("""
        SELECT
            churn_ym AS 解約月,
            COALESCE(NULLIF(sentiment, ''), '不明') AS センチメント,
            COUNT(*) AS 件数
        FROM sheet_churn_detail
        GROUP BY churn_ym, センチメント
        ORDER BY churn_ym, センチメント
    """).df()


def get_churn_detail_list(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """解約企業一覧テーブル。利用月数は整数、アンケート未回答フラグ付き。"""
    return con.execute("""
        SELECT
            churn_ym                              AS 解約月,
            company_name                          AS 企業名,
            CAST(billed_months AS INTEGER)        AS 利用月数,
            plan_name                             AS プラン,
            COALESCE(reason1, '')                 AS 理由①,
            COALESCE(reason2, '')                 AS 理由②,
            COALESCE(reason3, '')                 AS 理由③,
            CASE
                WHEN reason_detail LIKE '%アンケート未回答%' THEN 'アンケート未回答'
                WHEN sentiment IS NULL OR sentiment = ''    THEN '—'
                ELSE sentiment
            END                                   AS センチメント,
            COALESCE(reason_detail, '')           AS 詳細
        FROM sheet_churn_detail
        ORDER BY churn_date DESC
    """).df()


# ── CS業務用: per-company real-time queries ───────────────────────────────────

def get_cs_company_list(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """全企業リスト（company_id, profile_id, company_name, status, plan_type）。
    profile_id = profiles.id = projects.author_id（外部レポートURLのキー）。
    """
    return con.execute("""
        SELECT company_id, profile_id, company_name, status, plan_type
        FROM companies
        ORDER BY company_name
    """).df()


def get_cs_company_projects_with_apps(
    con: duckdb.DuckDBPyConnection, company_id: str
) -> pd.DataFrame:
    """企業の全案件と応募数・採用数。
    _raw_projects.author_id は profile_id なので _raw_profiles 経由で user_id と紐付ける。
    """
    return con.execute("""
        SELECT
            CAST(pj.id AS VARCHAR)  AS posting_id,
            COALESCE(pj.project_title, '') AS title,
            CASE
                WHEN pj.proj_status = 'publish' AND pj.proposal_status = 'open'  THEN 'active'
                WHEN pj.proj_status IN ('draft','pending')                         THEN 'draft'
                ELSE 'closed'
            END AS status,
            COALESCE(cat.name, '')  AS category,
            CAST(pj.created_at AS DATE) AS created_date,
            COUNT(pr.id)            AS total_apps,
            SUM(CASE WHEN pr.prop_status IN ('hired','completed') THEN 1 ELSE 0 END) AS accepted_apps,
            SUM(CASE WHEN pr.prop_status IN ('new','active','pending','draft','publish')
                     THEN 1 ELSE 0 END) AS pending_apps
        FROM _raw_projects pj
        JOIN _raw_profiles prof ON prof.profile_id = pj.author_id AND prof.role_id = 2
        LEFT JOIN _raw_proposals pr ON pr.project_id = pj.id
        LEFT JOIN _raw_categories cat ON cat.id = pj.project_category
        WHERE CAST(prof.user_id AS VARCHAR) = ?
          AND pj.deleted_at IS NULL
        GROUP BY
            pj.id, pj.project_title, pj.proj_status, pj.proposal_status,
            cat.name, pj.created_at
        ORDER BY
            CASE WHEN pj.proj_status = 'publish' AND pj.proposal_status = 'open'
                 THEN 0 ELSE 1 END,
            pj.created_at DESC
    """, [company_id]).df()


def get_cs_recent_applications(
    con: duckdb.DuckDBPyConnection, company_id: str, limit: int = 30
) -> pd.DataFrame:
    """企業の最新応募一覧。_raw_profiles 経由で company_id（user_id）を正しく解決。"""
    return con.execute("""
        SELECT
            COALESCE(pj.project_title, '')          AS 案件名,
            CASE
                WHEN pj.proj_status = 'publish' AND pj.proposal_status = 'open' THEN '掲載中'
                ELSE '終了'
            END                                     AS 案件状態,
            pr.prop_status                          AS 応募状態,
            CAST(pr.created_at AS DATE)             AS 応募日,
            CAST(pr.updated_at AS DATE)             AS 対応日
        FROM _raw_proposals pr
        JOIN _raw_projects pj   ON pj.id           = pr.project_id
        JOIN _raw_profiles prof ON prof.profile_id = pj.author_id AND prof.role_id = 2
        WHERE CAST(prof.user_id AS VARCHAR) = ?
          AND pr.created_at IS NOT NULL
        ORDER BY pr.created_at DESC
        LIMIT ?
    """, [company_id, limit]).df()


def get_cs_monthly_activity(
    con: duckdb.DuckDBPyConnection, company_id: str
) -> pd.DataFrame:
    """月別 応募数・採用数。_raw_profiles 経由で user_id を解決。"""
    return con.execute("""
        SELECT
            strftime(CAST(pr.created_at AS DATE), '%Y-%m') AS month,
            COUNT(*)                                        AS app_count,
            SUM(CASE WHEN pr.prop_status IN ('hired','completed')
                     THEN 1 ELSE 0 END)                    AS hired_count
        FROM _raw_proposals pr
        JOIN _raw_projects pj   ON pj.id           = pr.project_id
        JOIN _raw_profiles prof ON prof.profile_id = pj.author_id AND prof.role_id = 2
        WHERE CAST(prof.user_id AS VARCHAR) = ?
          AND pr.created_at IS NOT NULL
        GROUP BY month
        ORDER BY month
    """, [company_id]).df()


def get_cs_sheet_contract(
    con: duckdb.DuckDBPyConnection, company_name: str
) -> pd.DataFrame:
    """シートから企業名で契約情報を取得（部分一致）。"""
    try:
        return con.execute("""
            SELECT
                company_name, start_date, churn_date,
                billed_months, plan_name, status,
                contract_months, sales_owner
            FROM sheet_contracts
            WHERE company_name LIKE ?
            LIMIT 5
        """, [f"%{company_name}%"]).df()
    except Exception:
        return pd.DataFrame()


def get_cs_daily_messages(
    con: duckdb.DuckDBPyConnection, company_id: str, weeks: int = 53
) -> pd.DataFrame:
    """企業の日別メッセージ送信数（コントリビューショングラフ用）。"""
    return con.execute("""
        SELECT
            CAST(sent_at AS DATE)  AS day,
            COUNT(*)               AS msg_count
        FROM messages
        WHERE company_id = ?
          AND direction   = 'company_to_inf'
          AND CAST(sent_at AS DATE) >= CURRENT_DATE - INTERVAL (? * 7) DAY
        GROUP BY day
        ORDER BY day
    """, [company_id, weeks]).df()


def get_cs_daily_applications(
    con: duckdb.DuckDBPyConnection, company_id: str, weeks: int = 53
) -> pd.DataFrame:
    """企業への日別応募数（コントリビューショングラフ用）。"""
    return con.execute("""
        SELECT
            CAST(a.applied_at AS DATE) AS day,
            COUNT(*)                   AS app_count
        FROM applications a
        JOIN job_postings jp ON jp.posting_id = a.posting_id
        WHERE jp.company_id = ?
          AND a.applied_at IS NOT NULL
          AND CAST(a.applied_at AS DATE) >= CURRENT_DATE - INTERVAL (? * 7) DAY
        GROUP BY day
        ORDER BY day
    """, [company_id, weeks]).df()


# ── 解約マッピング（シート × DB 統合）───────────────────────────────────────

def get_company_churn_mapping(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """
    全企業の解約状況と表示名を返す。
    sheet_contracts.user_id → companies.company_id でJOINし、
    シートの企業名（メールアドレス回避）を優先する。

    Returns DataFrame: profile_id, company_id, display_name, is_churned(0/1)
    """
    tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}

    if "sheet_contracts" not in tables:
        return con.execute("""
            SELECT
                profile_id,
                company_id,
                company_name AS display_name,
                CASE WHEN status IN ('churned','suspended') THEN 1 ELSE 0 END AS is_churned
            FROM companies
            WHERE profile_id IS NOT NULL
        """).df()

    tables_set = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    has_churn_detail = "sheet_churn_detail" in tables_set

    churn_detail_cte = """
        churn_detail_names AS (
            SELECT DISTINCT company_name AS churn_name
            FROM sheet_churn_detail
            WHERE company_name IS NOT NULL AND TRIM(company_name) <> ''
        ),
    """ if has_churn_detail else """
        churn_detail_names AS (SELECT NULL AS churn_name WHERE 1=0),
    """

    df = con.execute(f"""
        WITH sheet_by_uid AS (
            -- 方法1: user_id (col6) → company_id 直接マッチ（表示名をシート名に置換）
            -- MIN(is_churned): 再契約がある場合は 0（active）が優先
            SELECT
                CAST(user_id AS VARCHAR)          AS company_id,
                MIN(CAST(is_churned AS INTEGER))  AS is_churned,
                MAX(company_name)                 AS sheet_name,
                MAX(CASE WHEN is_churned = 1 THEN churn_date ELSE NULL END) AS churn_date
            FROM sheet_contracts
            WHERE user_id IS NOT NULL
              AND CAST(user_id AS VARCHAR) NOT IN ('', 'None')
            GROUP BY CAST(user_id AS VARCHAR)
        ),
        sheet_by_coname AS (
            -- 方法2: sheet_contracts.company_name(col4) = companies.company_name 完全一致
            -- 同名企業で最も解約率が低い値（再契約あり=0が優先）
            SELECT
                company_name,
                MIN(CAST(is_churned AS INTEGER))  AS is_churned,
                MAX(CASE WHEN is_churned = 1 THEN churn_date ELSE NULL END) AS churn_date
            FROM sheet_contracts
            WHERE company_name IS NOT NULL AND TRIM(company_name) <> ''
            GROUP BY company_name
        ),
        {churn_detail_cte}
        dummy AS (SELECT 1)
        SELECT
            c.profile_id,
            c.company_id,
            -- 表示名: uid マッチがあればシート名（メールアドレス→企業名）、なければDB名
            COALESCE(
                NULLIF(TRIM(COALESCE(sbu.sheet_name, '')), ''),
                c.company_name
            )                                                            AS display_name,
            CASE WHEN c.status IN ('churned','suspended') THEN 1 ELSE 0 END AS db_is_churned,
            CASE
                WHEN sbu.is_churned IS NOT NULL THEN sbu.is_churned   -- uid最優先
                WHEN scn.is_churned IS NOT NULL THEN scn.is_churned   -- company_name次
                WHEN cdn.churn_name IS NOT NULL THEN 1                -- 解約詳細タブ記載=解約
                ELSE 0
            END                                                          AS sheet_is_churned,
            COALESCE(sbu.churn_date, scn.churn_date)                     AS churn_date
        FROM companies c
        LEFT JOIN sheet_by_uid      sbu ON sbu.company_id  = c.company_id
        LEFT JOIN sheet_by_coname   scn ON scn.company_name = c.company_name
                                        AND sbu.company_id IS NULL  -- uid マッチがない場合のみ
        LEFT JOIN churn_detail_names cdn ON cdn.churn_name  = c.company_name
                                        AND sbu.company_id IS NULL
                                        AND scn.company_name IS NULL  -- 上位マッチなしの場合のみ
        WHERE c.profile_id IS NOT NULL
    """).df()

    # DB または シートどちらかが解約なら解約扱い
    df["is_churned"] = (
        (df["db_is_churned"] > 0) | (df["sheet_is_churned"] > 0)
    ).astype(int)

    # 解約月（YYYY-MM）: 解約企業のみ。churn_date が取得できない場合は空文字
    df["churn_month"] = pd.to_datetime(df["churn_date"], errors="coerce").dt.strftime("%Y-%m")
    df.loc[df["is_churned"] == 0, "churn_month"] = ""
    df["churn_month"] = df["churn_month"].fillna("")

    return df[["profile_id", "company_id", "display_name", "is_churned", "churn_month"]]


# ── 利用状況ヒートマップ（全企業×時間軸）────────────────────────────────────

def get_usage_heatmap_messages_monthly(
    con: duckdb.DuckDBPyConnection,
    start_date: str = "",
    end_date: str = "",
    active_only: bool = False,
) -> pd.DataFrame:
    """全企業×月のメッセージ送信数（月別集計）。start/end_date は 'YYYY-MM-DD' 形式。"""
    status_filter = "AND c.status = 'active'" if active_only else ""
    date_filter = (
        f"AND CAST(m.sent_at AS DATE) BETWEEN '{start_date}' AND '{end_date}'"
        if start_date and end_date else ""
    )
    return con.execute(f"""
        SELECT
            c.company_name,
            c.profile_id,
            strftime(CAST(m.sent_at AS DATE), '%Y-%m') AS ym,
            COUNT(*)                                    AS cnt
        FROM messages m
        JOIN companies c ON c.company_id = m.company_id
        WHERE m.direction = 'company_to_inf'
          {date_filter}
          {status_filter}
        GROUP BY c.company_name, c.profile_id, ym
        ORDER BY c.company_name, ym
    """).df()


def get_usage_heatmap_proposals_monthly(
    con: duckdb.DuckDBPyConnection,
    start_date: str = "",
    end_date: str = "",
    active_only: bool = False,
) -> pd.DataFrame:
    """全企業×月の応募数・採用数・完了数（月別集計）。start/end_date は 'YYYY-MM-DD' 形式。"""
    status_filter = "AND c.status = 'active'" if active_only else ""
    date_filter = (
        f"AND CAST(p.created_at AS DATE) BETWEEN '{start_date}' AND '{end_date}'"
        if start_date and end_date else ""
    )
    return con.execute(f"""
        SELECT
            c.company_name,
            c.profile_id,
            strftime(CAST(p.created_at AS DATE), '%Y-%m') AS ym,
            COUNT(*)                                                       AS app_count,
            SUM(CASE WHEN p.prop_status = 'hired'     THEN 1 ELSE 0 END)  AS hire_count,
            SUM(CASE WHEN p.prop_status = 'completed' THEN 1 ELSE 0 END)  AS complete_count
        FROM _raw_proposals p
        JOIN _raw_projects   pj ON pj.id         = p.project_id
        JOIN _raw_profiles   pr ON pr.profile_id = pj.author_id AND pr.role_id = 2
        JOIN companies        c ON c.company_id  = CAST(pr.user_id AS VARCHAR)
        WHERE 1=1
          {date_filter}
          {status_filter}
        GROUP BY c.company_name, c.profile_id, ym
        ORDER BY c.company_name, ym
    """).df()


def get_usage_heatmap_messages(
    con: duckdb.DuckDBPyConnection,
    start_date: str = "",
    end_date: str = "",
    active_only: bool = False,
) -> pd.DataFrame:
    """全企業×日付のメッセージ送信数（DBの lg__messages 由来）。start/end_date は 'YYYY-MM-DD' 形式。"""
    status_filter = "AND c.status = 'active'" if active_only else ""
    date_filter = (
        f"AND CAST(m.sent_at AS DATE) BETWEEN '{start_date}' AND '{end_date}'"
        if start_date and end_date else ""
    )
    return con.execute(f"""
        SELECT
            c.company_name,
            c.profile_id,
            strftime(CAST(m.sent_at AS DATE), '%Y-%m-%d') AS day,
            COUNT(*)                                        AS cnt
        FROM messages m
        JOIN companies c ON c.company_id = m.company_id
        WHERE m.direction = 'company_to_inf'
          {date_filter}
          {status_filter}
        GROUP BY c.company_name, c.profile_id, day
        ORDER BY c.company_name, day
    """).df()


def get_usage_heatmap_proposals(
    con: duckdb.DuckDBPyConnection,
    start_date: str = "",
    end_date: str = "",
    active_only: bool = False,
) -> pd.DataFrame:
    """全企業×10日区切りの応募数・採用数・完了数（_raw_proposals 由来）。start/end_date は 'YYYY-MM-DD' 形式。"""
    status_filter = "AND c.status = 'active'" if active_only else ""
    date_filter = (
        f"AND CAST(p.created_at AS DATE) BETWEEN '{start_date}' AND '{end_date}'"
        if start_date and end_date else ""
    )
    return con.execute(f"""
        SELECT
            c.company_name,
            c.profile_id,
            strftime(CAST(p.created_at AS DATE), '%Y-%m') AS ym,
            CASE
                WHEN extract('day' from CAST(p.created_at AS DATE)) <= 10 THEN '1〜10日'
                WHEN extract('day' from CAST(p.created_at AS DATE)) <= 20 THEN '11〜20日'
                ELSE '21〜31日'
            END AS period,
            COUNT(*)                                                        AS app_count,
            SUM(CASE WHEN p.prop_status = 'hired'     THEN 1 ELSE 0 END)  AS hire_count,
            SUM(CASE WHEN p.prop_status = 'completed' THEN 1 ELSE 0 END)  AS complete_count
        FROM _raw_proposals p
        JOIN _raw_projects   pj ON pj.id           = p.project_id
        JOIN _raw_profiles   pr ON pr.profile_id   = pj.author_id AND pr.role_id = 2
        JOIN companies        c ON c.company_id     = CAST(pr.user_id AS VARCHAR)
        WHERE 1=1
          {date_filter}
          {status_filter}
        GROUP BY c.company_name, c.profile_id, ym, period
        ORDER BY c.company_name, ym, period
    """).df()
