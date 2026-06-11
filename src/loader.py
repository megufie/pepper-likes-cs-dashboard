"""
Data loader: registers tables in an in-memory DuckDB.

Modes (controlled by config.DATA_SOURCE):
  - "csv"           : reads ./data/*.csv (test data path, default)
  - "production_db" : reads existing-system MySQL READ-ONLY, then
                      creates DuckDB views matching the dashboard schema.

CRITICAL SAFETY (production_db mode):
  - Multi-layer enforcement: SQLAlchemy event sets SESSION TRANSACTION READ ONLY
  - Only SELECT statements are emitted from this module
  - No string interpolation of user input into SQL
  - Engine isolation_level=READ COMMITTED, connection timeout
"""
from __future__ import annotations

import os
import sys
import duckdb
import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config


# ── CSV mode ──────────────────────────────────────────────────────────────────

_BOOL_COLS = {"job_postings": ["has_deadline", "has_sample"]}

_DATETIME_COLS = {
    "companies":     ["registered_at", "contract_start_date", "contract_end_date"],
    "job_postings":  ["created_at", "deadline_date"],
    "messages":      ["sent_at"],
    "applications":  ["applied_at", "responded_at"],
    "churn_events":  ["churned_at"],
}


def _load_csv(table: str) -> pd.DataFrame:
    path = os.path.join(config.DATA_DIR, f"{table}.csv")
    df = pd.read_csv(path, keep_default_na=False)
    for col in _BOOL_COLS.get(table, []):
        if col in df.columns:
            df[col] = df[col].map({"True": True, "False": False, True: True, False: False})
    for col in _DATETIME_COLS.get(table, []):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    return df


def _load_csv_tables(con: duckdb.DuckDBPyConnection) -> None:
    for table in ("companies", "job_postings", "messages", "applications", "churn_events"):
        df = _load_csv(table)
        con.register(table, df)


# ── Production DB mode (MySQL, READ-ONLY) ─────────────────────────────────────

def _make_prod_engine():
    """Create a read-only-enforced SQLAlchemy engine."""
    import sqlalchemy
    from sqlalchemy import event

    if not all([config.PROD_DB_HOST, config.PROD_DB_USER,
                config.PROD_DB_PASSWORD, config.PROD_DB_NAME]):
        raise RuntimeError("PROD_DB_* environment variables are not set.")

    url = (f"mysql+pymysql://{config.PROD_DB_USER}:{config.PROD_DB_PASSWORD}"
           f"@{config.PROD_DB_HOST}:{config.PROD_DB_PORT}/{config.PROD_DB_NAME}")

    engine = sqlalchemy.create_engine(
        url,
        pool_pre_ping=False,   # pre_ping も TCP に依存するので無効化
        connect_args={
            "connect_timeout": 3,   # TCP接続タイムアウト（秒）
            "read_timeout":    20,
            "write_timeout":   20,
        },
        isolation_level="READ COMMITTED",
    )

    @event.listens_for(engine, "connect")
    def _force_read_only(dbapi_conn, conn_record):
        cur = dbapi_conn.cursor()
        try:
            cur.execute("SET SESSION TRANSACTION READ ONLY")
        except Exception:
            pass
        finally:
            cur.close()

    return engine


# Raw SELECTs — explicit, READ ONLY operations only.
_RAW_QUERIES = {
    "_raw_users": """
        SELECT id, email, status, is_suspended, created_at
        FROM users
        WHERE deleted_at IS NULL
    """,
    "_raw_profiles": """
        SELECT id AS profile_id, user_id, role_id, company_name, country, created_at
        FROM profiles
        WHERE deleted_at IS NULL AND role_id IN (2, 3)
    """,
    "_raw_billing": """
        SELECT profile_id, country_id, state_id, billing_company,
               billing_city, billing_postal_code
        FROM user_billing_detail
    """,
    "_raw_states": """
        SELECT id, name FROM country_states WHERE country_id = 112
    """,
    "_raw_subs": """
        SELECT id, subscriber_id, package_id, package_price, package_expiry,
               status, auto_renew, created_at, updated_at
        FROM package_subscribers
    """,
    "_raw_packages": """
        SELECT id, title FROM packages WHERE deleted_at IS NULL
    """,
    "_raw_projects": """
        SELECT
            id, author_id, project_title, project_description, project_category,
            project_min_price, project_max_price, project_payout_type,
            project_follower_count,
            -- Count occurrences of '"image/' substring in serialized attachments
            -- (each image file's mime_type appears once)
            CASE
                WHEN attachments IS NULL OR attachments = '' THEN 0
                ELSE (
                    CHAR_LENGTH(attachments) - CHAR_LENGTH(REPLACE(attachments, '"image/', ''))
                ) DIV CHAR_LENGTH('"image/')
            END AS image_count,
            status AS proj_status,
            proposal_status,
            created_at
        FROM projects
        WHERE deleted_at IS NULL
    """,
    "_raw_follower_counts": """
        SELECT id, name FROM follower_counts WHERE deleted_at IS NULL
    """,
    "_raw_categories": """
        SELECT id, parent_id, name FROM project_categories
        WHERE deleted_at IS NULL
    """,
    "_raw_proposals": """
        SELECT id, author_id, project_id,
               status AS prop_status, created_at, updated_at
        FROM proposals
    """,
    "_raw_messages": """
        SELECT id, thread_id, messageable_id, created_at
        FROM lg__messages
        WHERE deleted_at IS NULL
    """,
    "_raw_thread_participants": """
        SELECT thread_id, participantable_id AS user_id, role
        FROM lg__thread_participants
        WHERE deleted_at IS NULL
          AND participantable_type = 'App\\\\Models\\\\User'
    """,
    "_raw_project_sns": """SELECT project_id, sns_id FROM project_sns""",
    "_raw_sns": """SELECT id, name FROM sns WHERE deleted_at IS NULL""",
    "_raw_project_target_countries": """
        SELECT project_id, country_id FROM project_target_countries
    """,
}


def _load_production_tables(con: duckdb.DuckDBPyConnection) -> None:
    """Read raw tables from MySQL, register in DuckDB, then create dashboard views."""
    from sqlalchemy import text as sql_text

    engine = _make_prod_engine()
    try:
        with engine.connect() as conn:
            for name, sql in _RAW_QUERIES.items():
                df = pd.read_sql(sql_text(sql), conn)
                con.register(name, df)
    finally:
        engine.dispose()

    _create_dashboard_views(con)


def _create_dashboard_views(con: duckdb.DuckDBPyConnection) -> None:
    """Create views named like dashboard tables (companies, job_postings, ...)."""

    # ── companies view ────────────────────────────────────────────────────────
    con.execute("""
        CREATE OR REPLACE VIEW companies AS
        WITH sub_summary AS (
            -- A company's CURRENT state = the status of their most recent subscription row
            SELECT
                subscriber_id,
                ARG_MAX(status,         created_at) AS latest_status,
                ARG_MAX(package_id,     created_at) AS latest_package_id,
                ARG_MAX(package_expiry, created_at) AS latest_expiry,
                MIN(created_at) AS first_start
            FROM _raw_subs
            GROUP BY subscriber_id
        ),
        billing_one AS (
            SELECT profile_id,
                   ARG_MAX(state_id,         profile_id) AS state_id,
                   ARG_MAX(billing_company,  profile_id) AS billing_company
            FROM _raw_billing
            GROUP BY profile_id
        )
        SELECT
            CAST(u.id AS VARCHAR) AS company_id,
            CAST(p.profile_id AS VARCHAR) AS profile_id,   -- profiles.id (= projects.author_id)
            COALESCE(NULLIF(TRIM(p.company_name), ''),
                     b.billing_company,
                     u.email) AS company_name,
            COALESCE(pk.title, 'なし') AS plan_type,
            COALESCE(cs.name, '不明') AS prefecture,
            CAST(u.created_at AS TIMESTAMP) AS registered_at,
            CAST(ss.first_start AS DATE)    AS contract_start_date,
            CASE WHEN ss.latest_status = 'expired'
                 THEN CAST(ss.latest_expiry AS DATE) END AS contract_end_date,
            CASE
                WHEN u.is_suspended = 1                THEN 'suspended'
                WHEN ss.latest_status = 'active'       THEN 'active'
                WHEN ss.latest_status = 'expired'      THEN 'churned'
                ELSE 'active'
            END AS status,
            '未設定' AS cs_owner
        FROM _raw_users u
        JOIN _raw_profiles p ON p.user_id = u.id AND p.role_id = 2
        LEFT JOIN billing_one b ON b.profile_id = p.profile_id
        LEFT JOIN _raw_states cs ON cs.id = b.state_id
        LEFT JOIN sub_summary ss ON ss.subscriber_id = u.id
        LEFT JOIN _raw_packages pk ON pk.id = ss.latest_package_id
        WHERE u.status = 'activated'
    """)

    # ── job_postings view ─────────────────────────────────────────────────────
    con.execute("""
        CREATE OR REPLACE VIEW job_postings AS
        WITH sns_agg AS (
            SELECT ps.project_id, STRING_AGG(s.name, ',') AS platforms
            FROM _raw_project_sns ps
            JOIN _raw_sns s ON s.id = ps.sns_id
            GROUP BY ps.project_id
        ),
        country_agg AS (
            SELECT project_id, COUNT(*) AS country_count
            FROM _raw_project_target_countries
            GROUP BY project_id
        ),
        -- follower_counts.id maps to a follower threshold:
        -- 1=未指定, 2=500+, 3=1000+, 4=2000+, 5=3000+, 6=5000+, 7=10000+, 8=50000+, 9=100000+
        follower_thresholds AS (
            SELECT id,
                CASE id
                    WHEN 1 THEN 0      WHEN 2 THEN 500
                    WHEN 3 THEN 1000   WHEN 4 THEN 2000
                    WHEN 5 THEN 3000   WHEN 6 THEN 5000
                    WHEN 7 THEN 10000  WHEN 8 THEN 50000
                    WHEN 9 THEN 100000 ELSE 0
                END AS threshold
            FROM _raw_follower_counts
        )
        SELECT
            CAST(p.id AS VARCHAR) AS posting_id,
            CAST(p.author_id AS VARCHAR) AS company_id,
            COALESCE(p.project_title, '') AS title,
            COALESCE(p.project_description, '') AS description,
            COALESCE(p.image_count, 0) AS image_count,
            CASE
                WHEN p.project_payout_type = 'fixed' THEN 'fixed'
                WHEN p.project_payout_type IN ('hourly','milestone','both') THEN 'commission'
                ELSE 'free'
            END AS compensation_type,
            COALESCE(p.project_max_price, p.project_min_price, 0) AS compensation_amount,
            COALESCE(ft.threshold, 0) AS required_followers,
            COALESCE(p.project_follower_count, 0) AS follower_count_id,
            COALESCE(fc.name, '') AS follower_count_label,
            COALESCE(cat.name, '') AS category,
            FALSE AS has_deadline,
            CAST(NULL AS DATE) AS deadline_date,
            FALSE AS has_sample,
            COALESCE(s.platforms, '') AS platform_targets,
            COALESCE(co.country_count, 0) AS target_country_count,
            CAST(p.created_at AS TIMESTAMP) AS created_at,
            -- 「active = 公開中・承認済み・募集中」 = status='publish' AND proposal_status='open'
            -- これが pepperlikes.com/search-projects に表示される状態
            CASE
                WHEN p.proj_status = 'publish' AND p.proposal_status = 'open' THEN 'active'
                WHEN p.proj_status = 'publish' AND p.proposal_status = 'closed' THEN 'closed'
                WHEN p.proj_status = 'draft'     THEN 'draft'
                WHEN p.proj_status = 'pending'   THEN 'draft'
                WHEN p.proj_status = 'completed' THEN 'closed'
                WHEN p.proj_status = 'hired'     THEN 'closed'
                ELSE 'closed'
            END AS status
        FROM _raw_projects p
        LEFT JOIN _raw_categories cat ON cat.id = p.project_category
        LEFT JOIN sns_agg s ON s.project_id = p.id
        LEFT JOIN country_agg co ON co.project_id = p.id
        LEFT JOIN follower_thresholds ft ON ft.id = p.project_follower_count
        LEFT JOIN _raw_follower_counts fc ON fc.id = p.project_follower_count
    """)

    # ── applications view ─────────────────────────────────────────────────────
    con.execute("""
        CREATE OR REPLACE VIEW applications AS
        SELECT
            CAST(pr.id AS VARCHAR) AS application_id,
            CAST(pr.project_id AS VARCHAR) AS posting_id,
            CAST(pj.author_id AS VARCHAR) AS company_id,
            CAST(pr.author_id AS VARCHAR) AS influencer_id,
            CAST(pr.created_at AS TIMESTAMP) AS applied_at,
            CASE pr.prop_status
                WHEN 'hired'     THEN 'accepted'
                WHEN 'completed' THEN 'accepted'
                WHEN 'declined'  THEN 'rejected'
                WHEN 'rejected'  THEN 'rejected'
                WHEN 'refunded'  THEN 'rejected'
                WHEN 'new'       THEN 'pending'
                WHEN 'active'    THEN 'pending'
                WHEN 'pending'   THEN 'pending'
                WHEN 'draft'     THEN 'pending'
                WHEN 'publish'   THEN 'pending'
                ELSE 'withdrawn'
            END AS status,
            CAST(pr.updated_at AS TIMESTAMP) AS responded_at
        FROM _raw_proposals pr
        JOIN _raw_projects pj ON pj.id = pr.project_id
    """)

    # ── messages view ─────────────────────────────────────────────────────────
    # Direction is determined by the sender's role in the thread (buyer vs seller).
    con.execute("""
        CREATE OR REPLACE VIEW messages AS
        WITH thread_buyer AS (
            SELECT t.thread_id, MIN(t.user_id) AS buyer_id
            FROM _raw_thread_participants t
            JOIN _raw_profiles p ON p.user_id = t.user_id
            WHERE p.role_id = 2
            GROUP BY t.thread_id
        ),
        thread_seller AS (
            SELECT t.thread_id, MIN(t.user_id) AS seller_id
            FROM _raw_thread_participants t
            JOIN _raw_profiles p ON p.user_id = t.user_id
            WHERE p.role_id = 3
            GROUP BY t.thread_id
        )
        SELECT
            CAST(m.id AS VARCHAR) AS message_id,
            CAST(b.buyer_id AS VARCHAR) AS company_id,
            CAST(s.seller_id AS VARCHAR) AS influencer_id,
            CASE
                WHEN m.messageable_id = b.buyer_id  THEN 'company_to_inf'
                WHEN m.messageable_id = s.seller_id THEN 'inf_to_company'
                ELSE 'company_to_inf'
            END AS direction,
            CAST(m.created_at AS TIMESTAMP) AS sent_at,
            '' AS posting_id
        FROM _raw_messages m
        JOIN thread_buyer  b ON b.thread_id = m.thread_id
        JOIN thread_seller s ON s.thread_id = m.thread_id
    """)

    # ── churn_events view ─────────────────────────────────────────────────────
    # Source of truth (DB): one churn event per company = the LATEST expiry
    #   IF that company's CURRENT (latest) sub is expired (i.e. they did not renew).
    # If they renewed (latest is active), they did NOT churn even if older subs expired.
    # Reasons (and 区分) come from the Google Sheet — joined later when available.
    con.execute("""
        CREATE OR REPLACE VIEW churn_events AS
        WITH latest_per_company AS (
            SELECT
                subscriber_id,
                ARG_MAX(id,             created_at) AS latest_id,
                ARG_MAX(status,         created_at) AS latest_status,
                ARG_MAX(package_expiry, created_at) AS latest_expiry
            FROM _raw_subs
            GROUP BY subscriber_id
        )
        SELECT
            CAST(lpc.latest_id AS VARCHAR) AS churn_id,
            CAST(lpc.subscriber_id AS VARCHAR) AS company_id,
            CAST(lpc.latest_expiry AS DATE) AS churned_at,
            '未分類' AS reason
        FROM latest_per_company lpc
        -- Only include buyer-role users (filter out sellers)
        JOIN _raw_profiles p ON p.user_id = lpc.subscriber_id AND p.role_id = 2
        WHERE lpc.latest_status = 'expired'
          AND lpc.latest_expiry IS NOT NULL
    """)


# ── Public entry point ────────────────────────────────────────────────────────

def _load_contract_master_sheet(con: duckdb.DuckDBPyConnection) -> None:
    """Optionally load contract master sheet → registers `sheet_contracts` table."""
    try:
        from src import sheet_loader
    except ImportError:
        return
    if not sheet_loader.credentials_available():
        return
    try:
        df = sheet_loader.fetch_contract_master()
        if df is not None and not df.empty:
            con.register("sheet_contracts", df)
        else:
            import sys
            print("[sheet_loader] WARNING: fetch_contract_master returned empty — sheet_contracts not registered", file=sys.stderr)
    except Exception as e:
        import sys, traceback
        print(f"[sheet_loader] WARNING: {type(e).__name__}: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)


def _load_individual_check_sheet(con: duckdb.DuckDBPyConnection) -> None:
    """Optionally load 個別対策確認 sheet → registers `sheet_individual_check`."""
    try:
        from src import sheet_loader
    except ImportError:
        return
    if not sheet_loader.credentials_available():
        return
    try:
        df = sheet_loader.fetch_individual_check()
        if df.empty:
            return
        con.register("sheet_individual_check", df)
    except Exception as e:
        import sys
        print(f"[sheet_loader/individual] WARNING: {type(e).__name__}: {e}",
              file=sys.stderr)


def _load_adoption_counts_sheet(con: duckdb.DuckDBPyConnection) -> None:
    """Optionally load 採用・投稿数 sheet → registers `sheet_adoption`."""
    try:
        from src import sheet_loader
    except ImportError:
        return
    if not sheet_loader.credentials_available():
        return
    try:
        df = sheet_loader.fetch_adoption_counts()
        if df.empty:
            return
        con.register("sheet_adoption", df)
    except Exception as e:
        import sys
        print(f"[sheet_loader/adoption] WARNING: {type(e).__name__}: {e}",
              file=sys.stderr)


def _load_app_counts_sheet(con: duckdb.DuckDBPyConnection) -> None:
    """Optionally load 応募者数 sheet → registers `sheet_app_counts` table."""
    try:
        from src import sheet_loader
    except ImportError:
        return
    if not sheet_loader.credentials_available():
        return
    try:
        df = sheet_loader.fetch_app_counts_sheet()
        if df.empty:
            return
        con.register("sheet_app_counts", df)
    except Exception as e:
        import sys
        print(f"[sheet_loader/app_counts] WARNING: {type(e).__name__}: {e}",
              file=sys.stderr)


def _load_uncollected_debts_sheet(con: duckdb.DuckDBPyConnection) -> None:
    """Optionally load 未回収債権 sheet → registers `billing_uncollected` table."""
    try:
        from src import sheet_loader
    except ImportError:
        return
    if not sheet_loader.credentials_available():
        return
    try:
        df = sheet_loader.fetch_uncollected_debts()
        if df.empty:
            return
        con.register("billing_uncollected", df)
    except Exception as e:
        import sys
        print(f"[sheet_loader/uncollected] WARNING: {type(e).__name__}: {e}",
              file=sys.stderr)


def _load_timeline_source_sheet(con: duckdb.DuckDBPyConnection) -> None:
    """Load gid=0 タブ（取引先名E列ベース）→ registers `sheet_timeline_source`."""
    from src import sheet_loader
    if not sheet_loader.credentials_available():
        return
    try:
        df = sheet_loader.fetch_timeline_source()
        if df is None or df.empty:
            import sys
            print("[sheet_loader/timeline] WARNING: fetch_timeline_source returned empty", file=sys.stderr)
            return
        con.register("sheet_timeline_source", df)
    except Exception as e:
        import sys, traceback
        print(f"[sheet_loader/timeline] WARNING: {type(e).__name__}: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)


def _load_churn_detail_sheet(con: duckdb.DuckDBPyConnection) -> None:
    """Load 解約詳細シート（gid=363386561）→ registers `sheet_churn_detail`."""
    from src import sheet_loader
    if not sheet_loader.credentials_available():
        return
    try:
        df = sheet_loader.fetch_churn_detail()
        if df.empty:
            return
        con.register("sheet_churn_detail", df)
    except Exception as e:
        import sys
        print(f"[sheet_loader] WARNING fetch_churn_detail: {type(e).__name__}: {e}", file=sys.stderr)


def _load_slack_churn_reports(con: duckdb.DuckDBPyConnection) -> None:
    """Optionally load Slack #likes_解約報告 messages → registers `slack_churns`."""
    try:
        from src import slack_loader
    except ImportError:
        return
    if not slack_loader.credentials_available():
        return
    try:
        df = slack_loader.fetch_churn_reports(limit=300)
        if df.empty:
            return
        con.register("slack_churns", df)
    except Exception as e:
        import sys
        print(f"[slack_loader] WARNING: {type(e).__name__}: {e}", file=sys.stderr)


def _load_contract_status_sheet(con: duckdb.DuckDBPyConnection) -> None:
    """gid=1840131021 のD列ステータス集計 → `sheet_contract_status` テーブルに登録。
    render_summary() から毎回 Google Sheets を叩くのを防ぐためキャッシュ内で実行する。
    """
    try:
        from src import sheet_loader
    except ImportError:
        return
    if not sheet_loader.credentials_available():
        return
    try:
        import pandas as pd
        d = sheet_loader.fetch_contract_status_counts()
        df = pd.DataFrame([d])
        con.register("sheet_contract_status", df)
    except Exception as e:
        import sys
        print(f"[sheet_loader/contract_status] WARNING: {type(e).__name__}: {e}", file=sys.stderr)


def _mysql_reachable(host: str, port: int, timeout: float = 2.0) -> bool:
    """TCP レベルで MySQL に到達できるか確認する。"""
    import socket
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return True
    except (socket.timeout, OSError):
        return False


@st.cache_resource(show_spinner="データを読み込んでいます...")
def get_connection() -> duckdb.DuckDBPyConnection:
    """
    サーバープロセス全体で1回だけ実行・キャッシュする。
    全ユーザーが同じ接続を共有するため、最初の1人だけが待つ。
    """
    import socket
    socket.setdefaulttimeout(10)
    con = duckdb.connect(":memory:")
    try:
        if config.DATA_SOURCE == "production_db":
            host = config.PROD_DB_HOST or ""
            port = int(config.PROD_DB_PORT or 3306)
            if _mysql_reachable(host, port, timeout=2.0):
                try:
                    _load_production_tables(con)
                except Exception as e:
                    print(f"[loader] MySQL 失敗: {e}", file=sys.stderr)
            else:
                print("[loader] MySQL 到達不能 — スキップ", file=sys.stderr)
        else:
            _load_csv_tables(con)

        for fn in [
            _load_contract_master_sheet,
            _load_individual_check_sheet,
            _load_adoption_counts_sheet,
            _load_uncollected_debts_sheet,
            _load_app_counts_sheet,
            _load_churn_detail_sheet,
            _load_timeline_source_sheet,
            _load_slack_churn_reports,
            _load_contract_status_sheet,
        ]:
            try:
                fn(con)
            except Exception as e:
                print(f"[loader] {fn.__name__} 失敗: {e}", file=sys.stderr)
    finally:
        socket.setdefaulttimeout(None)
    return con
