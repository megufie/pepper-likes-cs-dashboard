"""
Higher-level KPI computations built on top of queries.py.
No SQL here — only pandas / Python logic.
"""
from __future__ import annotations

import duckdb
import pandas as pd

from src import queries


# ── DB-01 Summary KPIs ────────────────────────────────────────────────────────

def compute_summary_kpis(con: duckdb.DuckDBPyConnection) -> dict:
    """Returns a dict with 5 metric values for the summary page."""
    active_df   = queries.get_active_this_month(con)
    active_count = len(active_df)

    churn_df    = queries.get_churn_rate(con)
    churn_rate  = float(churn_df["churn_rate_pct"].iloc[0]) if len(churn_df) else 0.0

    avg_cont    = queries.get_avg_continuation_months(con)

    silent_df   = queries.get_silent_companies_3w(con)
    silent_count = len(silent_df)

    scores_df   = queries.get_attractiveness_scores(con)
    active_scores = scores_df[scores_df["status"] == "active"]["attractiveness_score"]
    avg_score   = float(active_scores.mean()) if len(active_scores) else 0.0

    return {
        "active_this_month": active_count,
        "churn_rate":        churn_rate,
        "avg_continuation":  avg_cont,
        "silent_companies":  silent_count,
        "avg_attractiveness": round(avg_score, 2),
    }


# ── DB-02 Continuity Matrix ───────────────────────────────────────────────────

def compute_continuity_matrix(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """
    Returns a DataFrame with companies as rows, months as columns (YYYY-MM),
    values 0/1, plus a '継続月数' column. Sorted by that column desc.
    Index is the company_name; if duplicates exist, suffixes the company_id.
    """
    raw = queries.get_continuity_matrix_raw(con)
    if raw.empty:
        return pd.DataFrame()

    matrix = raw.pivot_table(
        index=["company_id", "company_name"],
        columns="activity_month",
        values="is_active",
        aggfunc="max",
        fill_value=0,
    )
    matrix.columns.name = None
    matrix["継続月数"] = matrix.sum(axis=1)
    matrix = matrix.sort_values("継続月数", ascending=False).reset_index()

    # Make company_name unique for the visible index (real data may have collisions)
    name_counts = matrix["company_name"].value_counts()
    dups = name_counts[name_counts > 1].index
    matrix["display_name"] = matrix.apply(
        lambda r: (f"{r['company_name']} (#{r['company_id']})"
                   if r["company_name"] in dups else r["company_name"]),
        axis=1,
    )
    matrix = matrix.set_index("display_name").drop(columns=["company_id", "company_name"])
    matrix.index.name = "企業名"
    return matrix


# ── DB-03 Weekly Traffic Lights ───────────────────────────────────────────────

def compute_weekly_traffic_lights(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """
    Returns a wide DataFrame: company_name × iso_week message counts,
    plus a 'ステータス' column with 🔴/🟡/🟢.
    All active companies are included (zeros for missing weeks).
    """
    active_companies = queries.get_all_active_companies(con)
    weekly = queries.get_weekly_messages(con)

    if weekly.empty:
        pivot = pd.DataFrame(index=active_companies["company_name"])
    else:
        pivot = weekly.pivot_table(
            index="company_name",
            columns="iso_week",
            values="message_count",
            aggfunc="sum",
            fill_value=0,
        )
        pivot.columns.name = None

    # Ensure all active companies appear (add rows of zeros for missing ones)
    all_names = active_companies["company_name"].tolist()
    for name in all_names:
        if name not in pivot.index:
            pivot.loc[name] = 0

    pivot = pivot.sort_index()

    # Determine last 3 ISO weeks in the data
    week_cols = sorted([c for c in pivot.columns], reverse=True)
    last3 = week_cols[:3]
    last_week = week_cols[0] if week_cols else None
    week_4ago = week_cols[4] if len(week_cols) > 4 else None

    def traffic_light(row: pd.Series) -> str:
        # Red: 0 messages in each of the 3 most recent weeks
        if last3 and all(row.get(w, 0) == 0 for w in last3):
            return "🔴"
        # Yellow: last week's count is less than 50% of count 4 weeks ago
        if last_week and week_4ago:
            recent = row.get(last_week, 0)
            older  = row.get(week_4ago, 0)
            if older > 0 and recent < older * 0.5:
                return "🟡"
        return "🟢"

    pivot["ステータス"] = pivot.apply(traffic_light, axis=1)

    # Re-order: status first, then weeks ascending
    week_cols_asc = sorted([c for c in pivot.columns if c != "ステータス"])
    return pivot[["ステータス"] + week_cols_asc]


# ── DB-04 Posting Quality ─────────────────────────────────────────────────────

_RANK_MAP = {7: "S", 8: "S", 5: "A", 6: "A", 3: "B", 4: "B",
             0: "C", 1: "C", 2: "C"}

_RANK_ORDER = {"S": 0, "A": 1, "B": 2, "C": 3, "D": 4}


def _assign_rank(score: int) -> str:
    """0-12 scale rank assignment (matches new 12-point scoring)."""
    if score >= 9:  return "S"
    if score >= 7:  return "A"
    if score >= 5:  return "B"
    if score >= 3:  return "C"
    return "D"


def compute_posting_quality(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """
    Returns merged table of attractiveness scores + adoption rates with rank column.
    Columns: posting_id, company_name, title, status, attractiveness_score, rank,
             total_applications, accepted_count, adoption_rate_pct
    """
    scores = queries.get_attractiveness_scores(con)
    rates  = queries.get_application_rates(con)

    merged = scores.merge(rates, on="posting_id", how="left")
    merged["ランク"] = merged["attractiveness_score"].apply(_assign_rank)
    merged["rank_order"] = merged["ランク"].map(_RANK_ORDER)
    merged = merged.sort_values(["rank_order", "attractiveness_score"],
                                ascending=[True, False]).drop(columns="rank_order")
    return merged


# ── DB-05 Company Detail ──────────────────────────────────────────────────────

def get_company_detail_summary(con: duckdb.DuckDBPyConnection, company_id: str) -> dict:
    """Returns dict with keys: company_info, active_months, weekly_messages, postings."""
    info    = queries.get_company_info(con, company_id)
    months  = queries.get_company_active_months(con, company_id)
    weekly  = queries.get_company_weekly_messages(con, company_id)
    postings = queries.get_company_postings(con, company_id)

    postings["ランク"] = postings["attractiveness_score"].apply(_assign_rank)

    avg_score = float(postings["attractiveness_score"].mean()) \
        if len(postings) else 0.0

    return {
        "company_info":   info,
        "active_months":  months,
        "avg_score":      round(avg_score, 1),
        "weekly_messages": weekly,
        "postings":       postings,
    }
