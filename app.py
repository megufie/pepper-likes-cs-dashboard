from datetime import date, timedelta
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from PIL import Image

from src.loader import get_connection
from src import analytics, queries, sheet_loader

# ── Page config ───────────────────────────────────────────────────────────────
_icon = Image.open("assets/logo.png")

st.set_page_config(
    page_title="PEPPER LIKES CS",
    page_icon=_icon,
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Color palette ─────────────────────────────────────────────────────────────

MINT       = "#4FB89A"   # primary accent
MINT_DARK  = "#3E9E83"
MINT_LIGHT = "#A8DCC9"
MINT_BG    = "#EAF6F1"
INK        = "#1A1A1A"
INK_2      = "#4A4A4A"
INK_3      = "#8A8A8A"
LINE       = "#E8E8E8"
PAGE_BG    = "#FAFAFA"
CARD_BG    = "#FFFFFF"

STATUS_COLORS = {
    "active":    "#4FB89A",
    "accepted":  "#3E9E83",
    "pending":   "#F5A623",
    "rejected":  "#D9534F",
    "withdrawn": "#999999",
    "hired":     "#4FB89A",
    "declined":  "#D9534F",
    "completed": "#7CC2A9",
    "new":       "#4FB89A",
}

# ── Global CSS ────────────────────────────────────────────────────────────────

st.markdown(f"""
<style>
html, body, [class*="css"] {{
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display",
                 "SF Pro Text", "Helvetica Neue", "Hiragino Kaku Gothic ProN",
                 Arial, sans-serif !important;
    -webkit-font-smoothing: antialiased;
}}
.stApp {{ background-color: {PAGE_BG}; }}

/* Hide Streamlit's hamburger and footer */
#MainMenu, footer {{ visibility: hidden; }}

/* Main container */
.main .block-container {{
    padding: 0.5rem 2rem 2rem 2rem !important;
    max-width: 1500px;
}}

/* ── Sidebar (light) ── */
[data-testid="stSidebar"] {{
    background-color: #FFFFFF !important;
    border-right: 1px solid {LINE} !important;
}}
[data-testid="stSidebar"] * {{ color: {INK_2} !important; }}

/* Brand area */
.brand {{
    padding: 16px 4px 18px 4px;
    border-bottom: 1px solid {LINE};
    margin-bottom: 14px;
}}
.brand-row {{
    display: flex;
    align-items: center;
    gap: 8px;
}}
.brand-mark {{
    width: 22px; height: 22px;
    border-radius: 6px;
    background: linear-gradient(135deg, {MINT} 0%, {MINT_DARK} 100%);
    display: inline-block;
}}
.brand-name {{
    font-size: 14px; font-weight: 700; color: {INK} !important;
    letter-spacing: -0.2px;
}}
.brand-suffix {{ font-size: 12px; font-weight: 600; color: {INK_3} !important; }}
.brand-tag {{
    display: inline-block;
    background: {MINT_BG}; color: {MINT_DARK} !important;
    font-size: 10px; font-weight: 700;
    padding: 2px 8px; border-radius: 10px;
    margin-top: 8px;
}}

/* Section headers in sidebar (rendered as pseudo-elements before radio items) */
[data-testid="stSidebar"] .stRadio > label {{ display: none !important; }}
[data-testid="stSidebar"] [role="radiogroup"] {{ gap: 0 !important; }}
[data-testid="stSidebar"] [role="radiogroup"] > label {{
    padding: 7px 10px !important;
    margin: 1px 0 !important;
    border-radius: 8px !important;
    cursor: pointer;
    transition: background 0.15s ease;
}}
[data-testid="stSidebar"] [role="radiogroup"] > label:hover {{
    background: {PAGE_BG} !important;
}}
[data-testid="stSidebar"] [role="radiogroup"] > label > div:first-child {{
    display: none !important;
}}
[data-testid="stSidebar"] [role="radiogroup"] > label p {{
    font-size: 13px !important;
    color: {INK_2} !important;
    margin: 0 !important;
    padding-left: 14px !important;
    position: relative;
}}
/* Active item highlight */
[data-testid="stSidebar"] [role="radiogroup"] > label:has(input:checked) {{
    background: {MINT_BG} !important;
}}
[data-testid="stSidebar"] [role="radiogroup"] > label:has(input:checked) p {{
    color: {MINT_DARK} !important;
    font-weight: 600 !important;
}}
[data-testid="stSidebar"] [role="radiogroup"] > label:has(input:checked) p::before {{
    content: "";
    position: absolute;
    left: 0; top: 50%; transform: translateY(-50%);
    width: 6px; height: 6px;
    border-radius: 50%;
    background: {MINT};
}}

/* ── Top app header bar ── */
.app-header {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 14px 0 12px 0;
    border-bottom: 1px solid {LINE};
    margin-bottom: 18px;
}}
.app-header-left {{
    display: flex; align-items: center; gap: 10px;
}}
.app-header-name {{
    font-size: 13px; font-weight: 700; color: {INK};
    letter-spacing: -0.2px;
}}
.app-header-cs {{
    font-size: 13px; font-weight: 600; color: {INK_3};
    letter-spacing: 0;
}}
.app-header-tag {{
    background: {MINT_BG}; color: {MINT_DARK};
    font-size: 10px; font-weight: 700;
    padding: 2px 8px; border-radius: 10px;
}}
.app-header-meta {{
    font-size: 11px; color: {INK_3};
}}

/* ── Page title ── */
.page-title {{
    font-size: 20px;
    font-weight: 700;
    color: {INK};
    letter-spacing: -0.4px;
    margin: 4px 0 2px 0;
}}
.page-sub {{
    font-size: 12px;
    color: {INK_3};
    margin-bottom: 18px;
}}

/* ── KPI cards ── */
.kpi-grid {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 14px;
    margin-bottom: 22px;
}}
.kpi {{
    background: {CARD_BG};
    border: 1px solid {LINE};
    border-radius: 10px;
    padding: 18px 22px 18px 22px;
}}
.kpi-label {{
    font-size: 12px;
    color: {INK_3};
    font-weight: 500;
    margin-bottom: 8px;
    letter-spacing: -0.1px;
}}
.kpi-row {{
    display: flex;
    align-items: baseline;
    gap: 6px;
}}
.kpi-value {{
    font-size: 30px;
    font-weight: 700;
    color: {INK};
    letter-spacing: -0.8px;
    line-height: 1;
}}
.kpi-unit {{
    font-size: 14px;
    color: {INK_2};
    font-weight: 500;
}}
.kpi-sub {{
    font-size: 11px;
    color: {INK_3};
    margin-top: 6px;
}}
.kpi-pill {{
    display: inline-block;
    background: {MINT_BG};
    color: {MINT_DARK};
    font-size: 10px;
    font-weight: 700;
    padding: 2px 6px;
    border-radius: 6px;
    margin-right: 6px;
}}

/* ── Section card ── */
[data-testid="stVerticalBlockBorderWrapper"] {{
    background: {CARD_BG} !important;
    border: 1px solid {LINE} !important;
    border-radius: 10px !important;
    box-shadow: none !important;
    padding: 14px 18px !important;
    margin-bottom: 14px !important;
}}
.section-title {{
    font-size: 13px;
    font-weight: 700;
    color: {INK};
    letter-spacing: -0.1px;
    margin: 0 0 2px 0;
}}
.section-sub {{
    font-size: 11px;
    color: {INK_3};
    margin: 0 0 10px 0;
}}

/* ── Headings inside Streamlit ── */
h1, h2, h3 {{ color: {INK} !important; }}

/* ── Dataframe ── */
[data-testid="stDataFrame"] {{
    border-radius: 8px;
    overflow: hidden;
}}

/* ── Selectbox ── */
[data-baseweb="select"] {{ border-radius: 8px !important; }}

/* ── Alert banner ── */
.alert-danger {{
    background: #FBECEC;
    border-left: 3px solid {STATUS_COLORS["rejected"]};
    border-radius: 0 8px 8px 0;
    padding: 10px 14px;
    margin-top: 12px;
    font-size: 13px;
    color: #5A2222;
}}

/* ── Rank pills ── */
.rank-pill {{
    display: inline-block;
    border-radius: 14px;
    padding: 3px 12px;
    font-size: 11px;
    font-weight: 700;
    margin-right: 6px;
}}

/* ── Status badges ── */
.status-badge {{
    display: inline-block;
    border-radius: 12px;
    padding: 2px 10px;
    font-size: 11px;
    font-weight: 600;
}}

/* ── Bucket cards (application volume) ── */
.bucket-grid {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
    margin-bottom: 14px;
}}
.bucket {{
    background: {CARD_BG};
    border: 1px solid {LINE};
    border-radius: 10px;
    padding: 14px 16px;
    min-height: 130px;
}}
.bucket.warning {{ border-left: 3px solid #F5A623; }}
.bucket.danger  {{ border-left: 3px solid #D9534F; }}
.bucket.success {{ border-left: 3px solid {MINT}; }}
.bucket-head {{
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    margin-bottom: 8px;
}}
.bucket-title {{
    font-size: 12px;
    font-weight: 700;
    color: {INK};
    letter-spacing: -0.1px;
}}
.bucket-count {{
    font-size: 22px;
    font-weight: 700;
    color: {INK};
    letter-spacing: -0.6px;
    line-height: 1;
}}
.bucket-desc {{
    font-size: 10px;
    color: {INK_3};
    margin-bottom: 8px;
}}
.bucket-list {{
    font-size: 11px;
    color: {INK_2};
    line-height: 1.5;
    max-height: 78px;
    overflow-y: auto;
}}
.bucket-list-empty {{
    font-size: 11px;
    color: {INK_3};
    font-style: italic;
}}

/* ── Continuation ranking row ── */
.rank-row {{
    display: grid;
    grid-template-columns: 24px minmax(160px, 1fr) 1fr 60px 60px;
    align-items: center;
    gap: 12px;
    padding: 7px 4px;
    border-bottom: 1px solid {LINE};
    font-size: 12px;
}}
.rank-row:last-child {{ border-bottom: none; }}
.rank-num {{ color: {INK_3}; font-weight: 600; text-align: right; font-size: 11px; }}
.rank-name {{ color: {INK}; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
.rank-bar-track {{
    height: 6px; background: {PAGE_BG}; border-radius: 3px; overflow: hidden;
}}
.rank-bar-fill {{
    height: 100%; background: linear-gradient(90deg, {MINT_LIGHT}, {MINT});
    border-radius: 3px;
}}
.rank-months {{ color: {INK_2}; text-align: right; font-weight: 600; font-size: 11px; }}
.rank-count {{ color: {INK_3}; text-align: right; font-size: 11px; }}

/* ── Refresh button ── */
[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"] {{
    background: transparent !important;
    border: 1px solid {LINE} !important;
    border-radius: 6px !important;
    color: {INK_3} !important;
    font-size: 10px !important;
    font-weight: 500 !important;
    letter-spacing: 0.02em !important;
    padding: 3px 0 !important;
    min-height: unset !important;
    height: 28px !important;
    transition: border-color 0.15s, color 0.15s, background 0.15s !important;
}}
[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"]:hover {{
    background: {MINT_BG} !important;
    border-color: {MINT} !important;
    color: {MINT_DARK} !important;
}}
[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"]:active {{
    background: {MINT_LIGHT} !important;
    border-color: {MINT_DARK} !important;
    color: {MINT_DARK} !important;
}}
</style>
""", unsafe_allow_html=True)

# ── Plotly base ───────────────────────────────────────────────────────────────

_FONT = ("-apple-system, BlinkMacSystemFont, 'SF Pro Text', "
         "'Helvetica Neue', Arial, sans-serif")

PLOTLY_BASE = dict(
    font=dict(family=_FONT, color=INK, size=11),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    margin=dict(l=0, r=0, t=10, b=0),
    xaxis=dict(showgrid=False, zeroline=False, linecolor=LINE,
               tickfont=dict(size=10, color=INK_3)),
    yaxis=dict(showgrid=True, gridcolor="#F2F2F2", zeroline=False,
               tickfont=dict(size=10, color=INK_3)),
    legend=dict(font=dict(size=11, color=INK_2), bgcolor="rgba(0,0,0,0)"),
)
RANK_COLORS = {"S": MINT_DARK, "A": MINT, "B": "#F5A623", "C": "#D9534F"}
CHART_CFG = {"displayModeBar": False}


def themed(fig: go.Figure, **extra) -> go.Figure:
    fig.update_layout(**{**PLOTLY_BASE, **extra})
    return fig


# ── Sidebar ───────────────────────────────────────────────────────────────────

PAGE_LABELS = ["概要", "継続率分析", "解約分析",
               "応募分析", "未回収債権", "CS業務用", "利用状況"]
PAGE_KEYS   = ["summary", "retention", "churn",
               "applications", "uncollected", "cs_ops", "usage"]

with st.sidebar:
    st.markdown(f"""
    <div class="brand">
      <div class="brand-row">
        <span class="brand-mark"></span>
        <span class="brand-name">PEPPER LIKES</span>
        <span class="brand-suffix">CS</span>
      </div>
      <span class="brand-tag">実データ</span>
    </div>
    """, unsafe_allow_html=True)

    selected_label = st.radio("nav", PAGE_LABELS, label_visibility="collapsed")

    st.markdown('<div style="height:16px"></div>', unsafe_allow_html=True)
    _c1, _c2, _c3 = st.columns([1, 4, 1])
    with _c2:
        if st.button("↻ 更新", use_container_width=True):
            get_connection.clear()
            st.rerun()

page_key = PAGE_KEYS[PAGE_LABELS.index(selected_label)]

con = get_connection()


# ── Top app header ────────────────────────────────────────────────────────────

today_str = date.today().strftime("%Y-%m-%d")
st.markdown(f"""
<div class="app-header">
  <div class="app-header-left">
    <span class="app-header-name">PEPPER LIKES</span>
    <span class="app-header-cs">CS</span>
    <span class="app-header-tag">実データ</span>
  </div>
  <div class="app-header-meta">最終更新: {today_str}</div>
</div>
""", unsafe_allow_html=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def kpi(label, value, unit="", sub=""):
    sub_html = f'<div class="kpi-sub">{sub}</div>' if sub else ""
    unit_html = f'<span class="kpi-unit">{unit}</span>' if unit else ""
    return (f'<div class="kpi">'
            f'<div class="kpi-label">{label}</div>'
            f'<div class="kpi-row"><span class="kpi-value">{value}</span>{unit_html}</div>'
            f'{sub_html}</div>')


def page_header(title, subtitle):
    st.markdown(f'<div class="page-title">{title}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="page-sub">{subtitle}</div>', unsafe_allow_html=True)


def section(title, sub=""):
    st.markdown(f'<div class="section-title">{title}</div>', unsafe_allow_html=True)
    if sub:
        st.markdown(f'<div class="section-sub">{sub}</div>', unsafe_allow_html=True)


# ── Page: 概要 (Summary) ──────────────────────────────────────────────────────

def render_summary():
    page_header("CSダッシュボード", "企業の継続利用・活動状況・提案データの概要")

    sheet_ok  = queries.sheet_available(con)
    ret_kpis  = queries.get_retention_kpis(con) if sheet_ok else {}
    dur_stats = queries.get_avg_duration_all(con) if sheet_ok else {}
    min_stats = queries.get_min_contract_analysis(con) if sheet_ok else {}

    # 月次チャーンレート（必須期間ベース）
    churn_rate_df = queries.get_monthly_churn_rate(con) if sheet_ok else pd.DataFrame()

    # 契約ステータス集計（D列）
    try:
        contract_status = sheet_loader.fetch_contract_status_counts()
    except Exception:
        contract_status = None

    # 今月の解約数・解約企業一覧 — sheet_contracts の churn_date が当月
    _this_month_ym = date.today().strftime("%Y-%m")
    try:
        _churn_this_month_df = con.execute(f"""
            SELECT company_name, churn_date, cs_owner, churn_status
            FROM sheet_contracts
            WHERE is_churned = 1
              AND strftime(CAST(churn_date AS DATE), '%Y-%m') = '{_this_month_ym}'
            ORDER BY churn_date
        """).df()
        _churn_this_month = len(_churn_this_month_df)
    except Exception:
        _churn_this_month = None
        _churn_this_month_df = pd.DataFrame()

    # 掲載中の案件数 — DB の job_postings.status='active'
    try:
        active_postings = int(con.execute(
            "SELECT COUNT(*) FROM job_postings WHERE status = 'active'"
        ).fetchone()[0])
    except Exception:
        active_postings = None

    # 応募0件案件数 — シート「★個別対策確認」をソースとする
    # 条件: G列='募集中' AND H列 IN ('解約連絡あり','公開中','空白') AND L列=0
    try:
        zero_app_count = int(con.execute("""
            SELECT COUNT(*) FROM sheet_individual_check
            WHERE status1 = '募集中'
              AND COALESCE(status2, '') IN ('解約連絡あり','公開中','')
              AND COALESCE(apps_count, 0) = 0
        """).fetchone()[0])
        zero_app_unique_companies = int(con.execute("""
            SELECT COUNT(DISTINCT contract_company) FROM sheet_individual_check
            WHERE status1 = '募集中'
              AND COALESCE(status2, '') IN ('解約連絡あり','公開中','')
              AND COALESCE(apps_count, 0) = 0
              AND contract_company != ''
        """).fetchone()[0])
        zero_app_source = "sheet"
    except Exception:
        zero_app_count = None
        zero_app_unique_companies = None
        zero_app_source = "none"

    if zero_app_source == "sheet":
        zero_app_kpi = kpi(
            "⚠️ 応募0件 案件数",
            f"{zero_app_count}", "件",
            f"募集中×応募0件（シート由来 / うち契約企業 {zero_app_unique_companies}社）",
        )
    else:
        zero_app_kpi = kpi("⚠️ 応募0件 案件数", "—", "",
                           "シート連携が必要です")

    # ── LTV・継続指標の計算 ───────────────────────────────────────────────────────
    # 変数初期化
    _avg_obs            = None   # 解約済み企業の実測平均継続月数
    _avg_active         = None   # 継続中企業の現時点での平均月数（必須込み）
    _avg_active_post    = None   # 継続中企業の必須後 平均滞在月数
    _mand_avg           = None   # 必須期間の加重平均
    _post_mand_avg      = None   # 必須期間後の平均滞在月数（解約済み / LTV算出用）
    _ltv_churn_rate     = None   # LTV用月次チャーンレート（1 / _post_mand_avg）
    _churned_count      = None   # 解約済み企業数
    _active_count       = None   # 継続中企業数
    _active_past_mand   = None   # 継続中のうち必須期間経過済み企業数
    _exit_rate          = None   # 必須期間終了当月離脱率（初回解約機会）

    if sheet_ok:
        # 解約済み / 継続中 それぞれの平均継続月数
        _obs_df = con.execute("""
            SELECT
                AVG(CASE WHEN is_churned=1
                     THEN CAST(billed_months AS DOUBLE) END) AS avg_churned,
                AVG(CASE WHEN is_churned=0
                     THEN CAST(billed_months AS DOUBLE) END) AS avg_active,
                SUM(CASE WHEN is_churned=1 THEN 1 ELSE 0 END) AS cnt_churned,
                SUM(CASE WHEN is_churned=0 THEN 1 ELSE 0 END) AS cnt_active
            FROM sheet_contracts
            WHERE billed_months IS NOT NULL AND billed_months > 0
        """).df()
        row = _obs_df.iloc[0]
        _avg_obs    = row["avg_churned"]
        _avg_active = row["avg_active"]
        _churned_count = int(row["cnt_churned"] or 0)
        _active_count  = int(row["cnt_active"] or 0)

        # 継続中企業のうち必須期間超えのみ：合計・必須・任意継続 の各平均
        _active_post_df = con.execute("""
            SELECT
                AVG(CAST(billed_months AS DOUBLE))                              AS avg_total,
                AVG(CAST(contract_months AS DOUBLE))                            AS avg_mand,
                AVG(CAST(billed_months AS DOUBLE) - CAST(contract_months AS DOUBLE))
                                                                                AS avg_post_mand,
                COUNT(*) AS past_mand_count
            FROM sheet_contracts
            WHERE is_churned = 0
              AND billed_months IS NOT NULL AND billed_months > 0
              AND contract_months IS NOT NULL
              AND billed_months >= contract_months
        """).df()
        _apr = _active_post_df.iloc[0]
        _avg_active_total = float(_apr["avg_total"])      if _apr["avg_total"]     is not None else None
        _avg_active_mand  = float(_apr["avg_mand"])       if _apr["avg_mand"]      is not None else None
        _avg_active_post  = float(_apr["avg_post_mand"])  if _apr["avg_post_mand"] is not None else None
        _active_past_mand = int(_apr["past_mand_count"])  if _apr["past_mand_count"] is not None else 0

        # 必須期間の加重平均
        _mand_df = con.execute("""
            SELECT AVG(CAST(contract_months AS DOUBLE)) AS wmean
            FROM sheet_contracts WHERE contract_months IS NOT NULL
        """).df()
        _mand_avg = float(_mand_df.iloc[0]["wmean"])

        # 必須後の平均滞在（解約済み企業の平均継続 − 必須期間）
        # ＝ LTV公式の逆数 → 月次チャーンレート（LTV用）
        if _avg_obs is not None and _mand_avg is not None and (_avg_obs - _mand_avg) > 0:
            _post_mand_avg  = _avg_obs - _mand_avg
            _ltv_churn_rate = 1.0 / _post_mand_avg

        # 必須期間終了「当月」の初回離脱率（モニタリング参考値）
        _exit_df = con.execute("""
            WITH base AS (
                SELECT
                    service_start_date,
                    CAST(contract_months AS INTEGER) AS contract_months,
                    churn_date,
                    CAST(is_churned AS INTEGER) AS is_churned
                FROM sheet_contracts
                WHERE service_start_date IS NOT NULL
                  AND contract_months IS NOT NULL
                  AND churn_date IS NOT NULL
                  AND is_churned = 1
            )
            SELECT
                COUNT(*) AS total_churned,
                SUM(CASE
                    WHEN DATE_TRUNC('month', churn_date) =
                         DATE_TRUNC('month',
                             service_start_date + INTERVAL (contract_months || ' months'))
                    THEN 1 ELSE 0 END) AS exit_at_mandatory
            FROM base
        """).df()
        _er = _exit_df.iloc[0]
        if _er["total_churned"] > 0:
            _exit_rate = _er["exit_at_mandatory"] / _er["total_churned"]

    # ── KPI カード生成 ────────────────────────────────────────────────────────
    if _avg_obs is not None:
        _pm_str  = f"{_post_mand_avg:.1f}" if _post_mand_avg else "—"
        _mn_str  = f"{_mand_avg:.1f}"      if _mand_avg      else "—"
        avg_cont_kpi = kpi(
            "平均継続月数（LTV基準）",
            f"{_avg_obs:.1f}",
            "ヶ月",
            f"必須 {_mn_str}ヶ月 ＋ 任意継続 {_pm_str}ヶ月"
            f"（解約済み{_churned_count}社の実測）",
        )
        # 継続中企業の任意継続月数 KPI
        if _avg_active_total is not None:
            _at_str = f"{_avg_active_total:.1f}"
            _am_str = f"{_avg_active_mand:.1f}" if _avg_active_mand else "—"
            _ap_str = f"{_avg_active_post:.1f}" if _avg_active_post else "—"
            active_cont_kpi = kpi(
                "継続中 平均継続月数（現状）",
                _at_str,
                "ヶ月",
                f"必須 {_am_str}ヶ月 ＋ 任意継続 {_ap_str}ヶ月"
                f"（必須超え継続中 {_active_past_mand}社 の実測）",
            )
        else:
            active_cont_kpi = kpi("継続中 平均継続月数（現状）", "—", "", "データ不足")

        if _ltv_churn_rate is not None:
            ltv_cr_kpi = kpi(
                "必須後チャーンレート（LTV用）",
                f"{_ltv_churn_rate * 100:.0f}",
                "%/月",
                f"必須後 平均{_pm_str}ヶ月で解約 → 1÷{_pm_str}ヶ月"
                f"（{_mand_avg:.1f} ＋ 1/{_ltv_churn_rate*100:.0f}% = {_avg_obs:.1f}ヶ月）",
            )
        else:
            ltv_cr_kpi = kpi("必須後チャーンレート（LTV用）", "—", "", "データ不足")
    else:
        avg_cont_kpi    = kpi("平均継続月数（LTV基準）", "—", "",
                              "⚠️ 契約マスタシートを読み込めませんでした")
        active_cont_kpi = kpi("継続中 任意継続月数（現状）", "—", "", "")
        ltv_cr_kpi      = kpi("必須後チャーンレート（LTV用）", "—", "", "")

    # ── 契約企業数カード ─────────────────────────────────────────────────────
    if contract_status:
        st.markdown(
            '<div class="kpi-grid" style="grid-template-columns: repeat(3, 1fr);">'
            + kpi("累計契約企業数", f"{contract_status['累計']}", "社",
                  "01.契約済み＋03.解約済み＋04.解約申し出あり の合計")
            + kpi("現在の契約企業数",
                  f"{contract_status['契約済み'] + contract_status['解約申し出あり']}", "社",
                  f"01.契約済み {contract_status['契約済み']} ＋ 04.解約申し出あり {contract_status['解約申し出あり']}")
            + (_churn_this_month is not None
               and kpi("🚨 今月の解約数", f"{_churn_this_month}", "社",
                       f"{_this_month_ym} に churn_date が入った企業数（シート由来）")
               or kpi("🚨 今月の解約数", "—", "社", "シート連携が必要です"))
            + "</div>",
            unsafe_allow_html=True,
        )
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # ── LTV・継続指標 KPI グリッド ────────────────────────────────────────────
    # Row A: LTV用指標（平均継続月数 / 必須後チャーンレート）+ モニタリング用（当月/前月）
    _cr_today = date.today().strftime("%Y-%m")
    _cr_prev  = (date.today().replace(day=1) - timedelta(days=1)).strftime("%Y-%m")

    def _cr_kpi(row, label_suffix=""):
        if row.empty or row.iloc[0]["churn_rate"] is None:
            return kpi(f"月次CR（モニタリング）{label_suffix}", "—", "%", "解約可能企業なし")
        r        = row.iloc[0]
        rate_str = f"{r['churn_rate']:.1f}"
        sub      = f"解約 {int(r['churned'])} 社 ／ 解約可能 {int(r['eligible'])} 社（必須期間経過済み）"
        return kpi(f"月次CR（モニタリング）{label_suffix}", rate_str, "%", sub)

    # 上段：継続月数の比較（解約済み実績 vs 継続中の現状）
    st.markdown(
        '<div class="kpi-grid" style="grid-template-columns: repeat(2, 1fr);">'
        + avg_cont_kpi
        + active_cont_kpi
        + "</div>",
        unsafe_allow_html=True,
    )
    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

    # 下段：チャーンレート（LTV用 / モニタリング当月 / 前月）
    if not churn_rate_df.empty:
        _cr_row_now  = churn_rate_df[churn_rate_df["month"] == _cr_today]
        _cr_row_prev = churn_rate_df[churn_rate_df["month"] == _cr_prev]
        st.markdown(
            '<div class="kpi-grid" style="grid-template-columns: repeat(3, 1fr);">'
            + ltv_cr_kpi
            + _cr_kpi(_cr_row_now,  f"（{_cr_today}）")
            + _cr_kpi(_cr_row_prev, f"（{_cr_prev}）")
            + "</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div class="kpi-grid" style="grid-template-columns: repeat(1, 1fr);">'
            + ltv_cr_kpi
            + "</div>",
            unsafe_allow_html=True,
        )

    # Row B: 掲載中 / 応募0件
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    st.markdown(
        '<div class="kpi-grid" style="grid-template-columns: repeat(3, 1fr);">'
        + kpi("掲載中の案件数", f"{active_postings:,}" if active_postings is not None else "—", "件",
              "現在公開中の募集（status=active）")
        + zero_app_kpi
        + "</div>",
        unsafe_allow_html=True,
    )

    # ── 今月の解約企業一覧 ───────────────────────────────────────────────────────
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    with st.container(border=True):
        section(f"🚨 今月の解約企業（{_this_month_ym}）",
                f"{_churn_this_month or 0} 社 — シート契約マスタのchurn_date基準")
        if not _churn_this_month_df.empty:
            for _, row in _churn_this_month_df.iterrows():
                churn_d = str(row["churn_date"])[:10] if row["churn_date"] else "—"
                owner   = row["cs_owner"] or "—"
                status  = row["churn_status"] or ""
                name    = row["company_name"] or "—"
                st.markdown(
                    f'<div style="display:flex;align-items:center;gap:12px;'
                    f'padding:8px 12px;margin-bottom:4px;border-radius:8px;'
                    f'background:#FFF5F5;border-left:3px solid #D9534F;">'
                    f'<span style="font-weight:700;color:#7A1E1E;flex:1">{name}</span>'
                    f'<span style="color:#999;font-size:12px;white-space:nowrap">解約日 {churn_d}</span>'
                    f'<span style="color:#555;font-size:12px;white-space:nowrap">担当：{owner}</span>'
                    + (f'<span style="color:#999;font-size:12px;white-space:nowrap">{status}</span>' if status else '')
                    + '</div>',
                    unsafe_allow_html=True,
                )
        elif _churn_this_month is not None:
            st.info("今月の解約企業はまだありません。")
        else:
            st.warning("シート連携が必要です。")

    # ── LTV の見方 ─────────────────────────────────────────────────────────────
    if _avg_obs is not None:
        with st.expander("💡 チャーンレートと平均継続月数の見方（LTV計算ガイド）"):
            _pm = f"{_post_mand_avg:.1f}" if _post_mand_avg else "—"
            _mn = f"{_mand_avg:.1f}"      if _mand_avg else "—"
            _ltv_pct = f"{_ltv_churn_rate*100:.0f}" if _ltv_churn_rate else "—"
            _er_pct  = f"{_exit_rate*100:.0f}"       if _exit_rate     else "—"
            st.markdown(f"""
**① 平均継続月数（LTV基準）：{_avg_obs:.1f}ヶ月**
- 解約済み{_churned_count}社の実測値。LTV計算の最も信頼できる基準値。
- 内訳：必須期間 **{_mn}ヶ月**（解約不可） ＋ 任意継続 **{_pm}ヶ月**（必須後の実測平均）
- 継続中のうち必須超え **{_active_past_mand}社** の平均継続：{ f"{_avg_active_total:.1f}ヶ月" if _avg_active_total is not None else "—" }（必須 { f"{_avg_active_mand:.1f}" if _avg_active_mand else "—" }ヶ月 ＋ 任意継続 { f"{_avg_active_post:.1f}" if _avg_active_post else "—" }ヶ月）。必須期間中の企業は除外。将来の実績はさらに伸びる可能性あり。

**② 必須後チャーンレート（LTV用）：{_ltv_pct}%/月**
- 必須期間後の平均滞在 {_pm}ヶ月 の逆数（1 ÷ {_pm}ヶ月）。
- LTV公式と整合：必須{_mn}ヶ月 ＋ 1/{_ltv_pct}% = **{_avg_obs:.1f}ヶ月 ✓**
- この数値を使うと公式が実測値に一致する。

**③ 月次CR（モニタリング用）：直近の値をKPIで確認**
- 計算式：当月解約企業数 ÷ 当月に解約権利があった企業数（必須期間経過済み）。
- 月ごとの動向追跡・アラート検知に適している。
- ⚠️ この値をLTV公式に使うと過大な継続月数が出るため **LTV計算には使わない**。
  （理由：長期継続企業が分母に繰り返しカウントされ、見かけの率が低くなる）

**④ 必須期間終了当月の初回離脱率：{_er_pct}%**
- 「解約できる最初の月に実際に解約した企業」の割合（解約済み{_churned_count}社中）。
- ✅ CSアクションのトリガー指標：必須期間終了 **1〜2ヶ月前** にフォローを入れることで改善できる可能性がある。
""")
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # ── 月次チャーンレート トレンドチャート ──────────────────────────────────
    if not churn_rate_df.empty:
        with st.container(border=True):
            section("📉 月次チャーンレート推移（モニタリング用）",
                    "解約企業数 ÷ 解約可能企業数（必須期間経過済み）｜LTV計算には「必須後CR」を使用")
            _cr_trend = churn_rate_df.dropna(subset=["churn_rate"]).tail(18).copy()
            if not _cr_trend.empty:
                fig_cr = go.Figure()
                # エリアチャート
                fig_cr.add_trace(go.Scatter(
                    x=_cr_trend["month"],
                    y=_cr_trend["churn_rate"],
                    mode="lines+markers+text",
                    line=dict(color="#D9534F", width=2),
                    marker=dict(size=7, color="#D9534F"),
                    fill="tozeroy",
                    fillcolor="rgba(217,83,79,0.08)",
                    text=[f"{v:.1f}%" for v in _cr_trend["churn_rate"]],
                    textposition="top center",
                    textfont=dict(size=10, color="#D9534F"),
                    hovertemplate=(
                        "<b>%{x}</b><br>"
                        "チャーンレート: %{y:.1f}%<br>"
                        "<extra></extra>"
                    ),
                    customdata=list(zip(_cr_trend["churned"], _cr_trend["eligible"])),
                ))
                # 平均ライン
                avg_cr = _cr_trend["churn_rate"].mean()
                fig_cr.add_hline(
                    y=avg_cr,
                    line_dash="dot",
                    line_color="#999",
                    annotation_text=f"平均 {avg_cr:.1f}%",
                    annotation_position="right",
                    annotation_font=dict(size=10, color="#999"),
                )
                fig_cr.update_layout(
                    height=280,
                    margin=dict(l=0, r=60, t=10, b=10),
                    plot_bgcolor="white",
                    paper_bgcolor="white",
                    xaxis=dict(showgrid=False, tickangle=-30, tickfont=dict(size=10)),
                    yaxis=dict(
                        showgrid=True, gridcolor="#eee",
                        ticksuffix="%", rangemode="tozero",
                        tickfont=dict(size=10),
                    ),
                    showlegend=False,
                )
                st.plotly_chart(fig_cr, use_container_width=True, config=CHART_CFG)
                # 詳細テーブル（折りたたみ）
                with st.expander("月別詳細を見る"):
                    disp_cr = _cr_trend[["month", "churned", "eligible", "churn_rate"]].copy()
                    disp_cr.columns = ["月", "解約数", "解約可能企業数", "チャーンレート(%)"]
                    disp_cr = disp_cr.sort_values("月", ascending=False).reset_index(drop=True)
                    st.dataframe(disp_cr, use_container_width=True, hide_index=True)

    # ── プラン別 平均継続月数 ─────────────────────────────────────────────
    if dur_stats and not dur_stats.get("by_plan", pd.DataFrame()).empty:
        with st.container(border=True):
            section("申し込みプラン別 平均継続月数",
                    "全企業（継続中は今日まで）／ 解約済み平均は解約日まで")
            plan_df = dur_stats["by_plan"].copy()
            plan_df = plan_df.rename(columns={
                "plan":                "プラン",
                "company_count":       "企業数",
                "avg_months":          "全社平均(月)",
                "avg_churned_months":  "解約済平均(月)",
                "active_count":        "継続中",
            })
            st.dataframe(
                plan_df.style
                .format({"全社平均(月)": "{:.1f}", "解約済平均(月)": "{:.1f}"})
                .set_properties(**{"font-size": "12px"}),
                use_container_width=True, hide_index=True,
                height=min(400, 60 + len(plan_df) * 35),
            )
            avg_u = dur_stats.get("avg_all_unfiltered")
            total_u = dur_stats.get("total_unfiltered", 0)
            if avg_u is not None:
                st.caption(
                    f"📌 参考（フィルターなし・全 {total_u} 社）："
                    f"平均継続月数 **{avg_u:.1f} ヶ月**"
                    "　※最低契約期間未経過の企業を含む"
                )

    # ── 最低契約期間（AN列）分析 ─────────────────────────────────────────
    if min_stats:
        with st.container(border=True):
            section("最低契約期間（AN列）比較",
                    "解約済み企業の実継続月数と最低契約期間の関係")
            c1, c2, c3 = st.columns(3)

            # 最低期間より前に解約
            with c1:
                st.markdown(
                    f'<div style="background:#FBECEC;border-radius:10px;padding:16px 20px;">'
                    f'<div style="font-size:11px;color:#7A1E1E;font-weight:700;margin-bottom:6px;">'
                    f'⚠️ 最低期間より早期解約</div>'
                    f'<div style="font-size:28px;font-weight:800;color:#7A1E1E;">'
                    f'{min_stats["before_count"]}<span style="font-size:14px;font-weight:500"> 社</span></div>'
                    f'</div>', unsafe_allow_html=True)
                if min_stats["before_names"]:
                    st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
                    for name in min_stats["before_names"]:
                        st.markdown(f'<div style="font-size:11px;color:#555;padding:2px 4px;">・{name}</div>',
                                    unsafe_allow_html=True)

            # 最低期間ぴったりで解約
            with c2:
                st.markdown(
                    f'<div style="background:#FFF8EC;border-radius:10px;padding:16px 20px;">'
                    f'<div style="font-size:11px;color:#8C5E00;font-weight:700;margin-bottom:6px;">'
                    f'📋 最低期間ちょうどで解約</div>'
                    f'<div style="font-size:28px;font-weight:800;color:#8C5E00;">'
                    f'{min_stats["exact_count"]}<span style="font-size:14px;font-weight:500"> 社</span></div>'
                    f'</div>', unsafe_allow_html=True)
                if min_stats["exact_names"]:
                    st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
                    for name in min_stats["exact_names"]:
                        st.markdown(f'<div style="font-size:11px;color:#555;padding:2px 4px;">・{name}</div>',
                                    unsafe_allow_html=True)

            # 最低期間以上継続
            with c3:
                st.markdown(
                    f'<div style="background:{MINT_BG};border-radius:10px;padding:16px 20px;">'
                    f'<div style="font-size:11px;color:{MINT_DARK};font-weight:700;margin-bottom:6px;">'
                    f'✅ 最低期間以上継続</div>'
                    f'<div style="font-size:28px;font-weight:800;color:{MINT_DARK};">'
                    f'{min_stats["beyond_count"]}<span style="font-size:14px;font-weight:500"> 社</span></div>'
                    f'<div style="font-size:12px;color:{MINT_DARK};margin-top:6px;">'
                    f'平均 {min_stats["beyond_avg"]:.1f} ヶ月</div>'
                    f'</div>', unsafe_allow_html=True)

    # ── 応募数バケット 積み上げ棒グラフ ─────────────────────────────────
    try:
        bucket_df = queries.get_apps_bucket_by_month(con)
        if not bucket_df.empty:
            with st.container(border=True):
                section("📊 月別 応募数分布（掲載中案件）",
                        "募集中×公開中or解約連絡あり の案件を応募数レンジ別に集計")

                bucket_order = ['0件','1〜4件','5〜9件','10〜14件','15〜19件','20〜24件','25〜29件','30件以上']
                bucket_colors = {
                    "0件":      "#FBECEC",
                    "1〜4件":   "#F9D5D3",
                    "5〜9件":   "#D4EEE6",
                    "10〜14件": "#A8DCC9",
                    "15〜19件": "#7DCAAF",
                    "20〜24件": "#4FB89A",
                    "25〜29件": "#3E9E83",
                    "30件以上": "#2A7A63",
                }
                color_seq = [bucket_colors[b] for b in bucket_order
                             if b in bucket_df["bucket"].cat.categories]

                fig = px.bar(
                    bucket_df,
                    x="month", y="案件数", color="bucket",
                    barmode="stack",
                    labels={"month": "", "案件数": "案件数", "bucket": "応募数"},
                    color_discrete_sequence=color_seq,
                    category_orders={"bucket": bucket_order},
                )
                fig.update_layout(
                    height=320,
                    margin=dict(l=0, r=0, t=10, b=0),
                    plot_bgcolor="white", paper_bgcolor="white",
                    legend=dict(orientation="h", yanchor="bottom",
                                y=1.02, xanchor="left", x=0),
                    xaxis=dict(showgrid=False),
                    yaxis=dict(showgrid=True, gridcolor="#eee"),
                )
                st.plotly_chart(fig, use_container_width=True)
    except Exception:
        pass

    # ── 応募0件案件 一覧（当月 + 先月）─────────────────────────────────
    if zero_app_source == "sheet":
        col_zero1, col_zero2 = st.columns(2)

        # 当月（L列=0）
        with col_zero1:
            with st.container(border=True):
                section("⚠️ 当月 応募0件 案件",
                        "公開日が古いほど優先度高 — 早めにCS介入")
                this_month = con.execute("""
                    SELECT
                        post_create_date AS 公開日,
                        contract_company AS 契約企業,
                        account_name     AS アカウント,
                        status2          AS 状況,
                        project_title    AS 案件名
                    FROM sheet_individual_check
                    WHERE status1 = '募集中'
                      AND COALESCE(status2, '') IN ('解約連絡あり','公開中','')
                      AND COALESCE(apps_count, 0) = 0
                    ORDER BY post_create_date
                """).df()
                if not this_month.empty:
                    # Replace empty 状況 with 「(空白)」
                    this_month["状況"] = this_month["状況"].replace({"": "(空白)"}).fillna("(空白)")
                    this_month["契約企業"] = this_month["契約企業"].replace({"": "—"}).fillna("—")
                    this_month["案件名"] = this_month["案件名"].str.slice(0, 35) + "..."

                    def _status_pill(v):
                        if "解約連絡" in str(v):
                            return ("background-color:#FBECEC;color:#7A1E1E;"
                                    "font-weight:700;text-align:center;border-radius:8px;")
                        if "公開中" in str(v):
                            return (f"background-color:{MINT_BG};color:{MINT_DARK};"
                                    "text-align:center;border-radius:8px;")
                        return "color:#999;text-align:center;"

                    styled = (this_month.style
                        .map(_status_pill, subset=["状況"])
                        .set_properties(**{"font-size":"11px"}))
                    st.dataframe(styled, use_container_width=True,
                                 hide_index=True, height=420)
                    st.caption(f"全 {len(this_month)} 件")

        # 先月（N列=0）
        with col_zero2:
            with st.container(border=True):
                section("📅 先月 応募0件 案件",
                        "今月より前に公開 かつ 前月応募数=0 のプロジェクト")
                last_month = con.execute("""
                    SELECT
                        post_create_date AS 公開日,
                        contract_company AS 契約企業,
                        account_name     AS アカウント,
                        status2          AS 状況,
                        apps_count       AS 当月,
                        project_title    AS 案件名
                    FROM sheet_individual_check
                    WHERE status1 = '募集中'
                      AND COALESCE(status2, '') IN ('解約連絡あり','公開中','')
                      AND COALESCE(prev_apps_count, 0) = 0
                      AND TRY_STRPTIME(post_create_date, '%m/%d/%Y') < DATE_TRUNC('month', CURRENT_DATE)
                    ORDER BY post_create_date
                """).df()
                if not last_month.empty:
                    last_month["状況"] = last_month["状況"].replace({"": "(空白)"}).fillna("(空白)")
                    last_month["契約企業"] = last_month["契約企業"].replace({"": "—"}).fillna("—")
                    last_month["案件名"] = last_month["案件名"].str.slice(0, 35) + "..."

                    def _status_pill(v):
                        if "解約連絡" in str(v):
                            return ("background-color:#FBECEC;color:#7A1E1E;"
                                    "font-weight:700;text-align:center;border-radius:8px;")
                        if "公開中" in str(v):
                            return (f"background-color:{MINT_BG};color:{MINT_DARK};"
                                    "text-align:center;border-radius:8px;")
                        return "color:#999;text-align:center;"

                    def _zero_highlight(v):
                        try:
                            n = int(v)
                            if n == 0:
                                return ("background-color:#FBECEC;color:#7A1E1E;"
                                        "font-weight:700;text-align:center;border-radius:8px;")
                        except: pass
                        return f"background-color:{MINT_BG};color:{MINT_DARK};text-align:center;font-weight:600;"

                    styled = (last_month.style
                        .map(_status_pill, subset=["状況"])
                        .map(_zero_highlight, subset=["当月"])
                        .set_properties(**{"font-size":"11px"}))
                    st.dataframe(styled, use_container_width=True,
                                 hide_index=True, height=420)
                    st.caption(f"全 {len(last_month)} 件 — 当月も0なら2ヶ月連続")



# ── Page: 継続・契約 (Continuity Matrix) ──────────────────────────────────────

def render_continuity():
    page_header("継続・契約", "企業ごとの月次活動状況（メッセージ送信または応募受付あり = 1）")

    matrix = analytics.compute_continuity_matrix(con)
    if matrix.empty:
        st.info("データがありません。")
        return

    month_cols = [c for c in matrix.columns if c != "継続月数"]

    def _cell(v):
        if v == 1:
            return (f"background-color:{MINT};color:white;font-weight:700;"
                    "text-align:center;border-radius:6px;")
        return f"background-color:#F7F7F7;color:#CCC;text-align:center;"

    def _total(v):
        return (f"background-color:{INK};color:white;font-weight:700;"
                "text-align:center;border-radius:6px;")

    with st.container(border=True):
        styled = (
            matrix.style
            .map(_cell,  subset=month_cols)
            .map(_total, subset=["継続月数"])
            .set_properties(**{"font-size": "12px"})
        )
        st.dataframe(styled, use_container_width=True, height=620)


# ── Page: 週次活動 (Weekly Activity) ──────────────────────────────────────────

def render_weekly():
    page_header(
        "週次活動",
        "🔴 直近3週連続メッセージ0件 ｜ 🟡 先週が4週前比50%以上減少 ｜ 🟢 正常",
    )

    weekly_tl = analytics.compute_weekly_traffic_lights(con)
    if weekly_tl.empty:
        st.info("データがありません。")
        return

    def _status(v):
        if v == "🔴": return "background-color:#FBECEC;font-size:14px;text-align:center;"
        if v == "🟡": return "background-color:#FEF6E5;font-size:14px;text-align:center;"
        return f"background-color:{MINT_BG};font-size:14px;text-align:center;"

    def _count(v):
        try: n = int(v)
        except: return ""
        if n == 0: return "color:#CCC;text-align:center;"
        alpha = min(0.55, 0.15 + n / 10 * 0.45)
        return (f"background-color:rgba(79,184,154,{alpha:.2f});"
                f"color:{MINT_DARK};font-weight:700;text-align:center;"
                "border-radius:8px;")

    week_cols = [c for c in weekly_tl.columns if c != "ステータス"]
    with st.container(border=True):
        styled = (
            weekly_tl.style
            .map(_status, subset=["ステータス"])
            .map(_count,  subset=week_cols)
            .set_properties(**{"font-size": "12px"})
        )
        st.dataframe(styled, use_container_width=True, height=560)

    silent = queries.get_silent_companies_3w(con)
    if not silent.empty:
        names = "、".join(silent["company_name"].tolist())
        st.markdown(
            f'<div class="alert-danger">'
            f'<strong>🔴 要対応企業 {len(silent)}社</strong> — {names}</div>',
            unsafe_allow_html=True,
        )


# ── Page: 解約分析 (Churn Analysis) ───────────────────────────────────────────

def render_churn():
    page_header("解約分析",
                "解約詳細シート（2025年12月〜）をベースに解約傾向を分析")

    if not queries.churn_detail_available(con):
        st.warning("📋 解約詳細シートに接続できません。credentials.json を確認してください。")
        return

    kpis           = queries.get_churn_detail_kpis(con)
    by_month       = queries.get_churn_by_month(con)
    reasons        = queries.get_churn_reasons(con)
    reasons_by_mon = queries.get_churn_reasons_by_month(con)
    sent_month     = queries.get_churn_sentiment_by_month(con)
    detail_list    = queries.get_churn_detail_list(con)

    # ── KPIs ─────────────────────────────────────────────────────────────────
    total = kpis["total"]
    st.markdown(
        '<div class="kpi-grid" style="grid-template-columns: repeat(4, 1fr);">'
        + kpi("累計解約数（2025/12〜）", str(total), "社", "新システム稼働後の解約合計")
        + kpi("😞 ネガティブ", str(kpis['negative']), "社",
              f"全体の {kpis['negative']/total*100:.0f}%" if total else "—")
        + kpi("😊 ポジティブ", str(kpis['positive']), "社",
              f"ニュートラル {kpis['neutral']} 社")
        + kpi("📋 アンケート未回答", str(kpis['unknown']), "社",
              f"センチメント未記入（全体の {kpis['unknown']/total*100:.0f}%）" if total else "—")
        + "</div>",
        unsafe_allow_html=True,
    )

    # ── 月別解約数 + センチメント積み上げ ────────────────────────────────────
    col_l, col_r = st.columns(2)

    with col_l:
        with st.container(border=True):
            section("📅 月別 解約数", "2025年12月以降")
            if not by_month.empty:
                fig_m = px.bar(
                    by_month, x="解約月", y="解約数",
                    text="解約数",
                    labels={"解約月": "", "解約数": "解約数"},
                    color_discrete_sequence=["#D9534F"],
                )
                fig_m.update_traces(marker_cornerradius=4,
                                    textposition="outside",
                                    textfont=dict(size=11, color=INK_2))
                fig_m.update_layout(height=300, margin=dict(l=0,r=0,t=10,b=0),
                                    plot_bgcolor="white", paper_bgcolor="white",
                                    xaxis=dict(showgrid=False, tickangle=-45),
                                    yaxis=dict(showgrid=True, gridcolor="#eee"))
                st.plotly_chart(fig_m, use_container_width=True, config=CHART_CFG)

    with col_r:
        with st.container(border=True):
            section("🎭 月別 センチメント内訳", "ポジティブ・ニュートラル・ネガティブ・不明")
            if not sent_month.empty:
                sent_colors = {
                    "ネガティブ":   "#D9534F",
                    "ニュートラル": "#F0AD4E",
                    "ポジティブ":   MINT,
                    "不明":         "#CCCCCC",
                }
                fig_s = px.bar(
                    sent_month, x="解約月", y="件数", color="センチメント",
                    barmode="stack",
                    color_discrete_map=sent_colors,
                    labels={"解約月": "", "件数": "社数"},
                )
                fig_s.update_layout(height=300, margin=dict(l=0,r=0,t=10,b=0),
                                    plot_bgcolor="white", paper_bgcolor="white",
                                    xaxis=dict(showgrid=False, tickangle=-45),
                                    yaxis=dict(showgrid=True, gridcolor="#eee"),
                                    legend=dict(orientation="h", y=1.08, x=0))
                st.plotly_chart(fig_s, use_container_width=True, config=CHART_CFG)

    # ── 解約理由 内訳 ────────────────────────────────────────────────────────
    with st.container(border=True):
        section("💬 解約理由 内訳（理由①②③ 合算）", "上位15理由")
        if not reasons.empty:
            fig_r = px.bar(
                reasons.sort_values("件数"),
                x="件数", y="reason", orientation="h",
                text="件数",
                labels={"件数": "件数", "reason": ""},
                color_discrete_sequence=["#D9534F"],
            )
            fig_r.update_traces(marker_cornerradius=3,
                                textposition="outside",
                                textfont=dict(size=10, color=INK_2))
            fig_r.update_layout(height=max(300, len(reasons) * 28),
                                margin=dict(l=0, r=30, t=10, b=0),
                                plot_bgcolor="white", paper_bgcolor="white",
                                xaxis=dict(showgrid=True, gridcolor="#eee"),
                                yaxis=dict(showgrid=False, tickfont=dict(size=10)))
            st.plotly_chart(fig_r, use_container_width=True, config=CHART_CFG)

    # ── 解約月別 理由内訳 ────────────────────────────────────────────────────
    with st.container(border=True):
        section("📅 解約月別 理由内訳", "各月の解約理由（理由①②③ 合算）の積み上げ")
        if not reasons_by_mon.empty:
            # 上位N理由をカラーで表示、残りは「その他」にまとめる
            TOP_N = 10
            top_reasons = (
                reasons_by_mon.groupby("reason")["件数"].sum()
                .sort_values(ascending=False)
                .head(TOP_N)
                .index.tolist()
            )
            rbm = reasons_by_mon.copy()
            rbm["reason_label"] = rbm["reason"].where(rbm["reason"].isin(top_reasons), "その他")
            rbm_agg = (
                rbm.groupby(["解約月", "reason_label"], as_index=False)["件数"].sum()
            )

            # 理由の並び順: 上位N → その他
            reason_order = top_reasons + (["その他"] if "その他" in rbm_agg["reason_label"].values else [])

            # カラーパレット（上位N件 + その他はグレー）
            palette = [
                "#D9534F", "#E8845A", "#F5A623", "#F7C948", "#7CC2A9",
                "#4FB89A", "#3E9E83", "#5B8DB8", "#9B6BB5", "#C2607A",
            ]
            color_map = {r: palette[i % len(palette)] for i, r in enumerate(top_reasons)}
            color_map["その他"] = "#CCCCCC"

            fig_rbm = px.bar(
                rbm_agg,
                x="解約月", y="件数", color="reason_label",
                category_orders={"reason_label": reason_order},
                color_discrete_map=color_map,
                labels={"reason_label": "理由", "件数": "件数", "解約月": "解約月"},
                text_auto=False,
            )
            fig_rbm.update_layout(
                height=380,
                margin=dict(l=0, r=0, t=10, b=0),
                plot_bgcolor="white", paper_bgcolor="white",
                legend=dict(
                    orientation="v", x=1.01, y=1,
                    font=dict(size=10), title=dict(text="理由", font=dict(size=10)),
                ),
                xaxis=dict(showgrid=False, tickangle=-30, tickfont=dict(size=11)),
                yaxis=dict(showgrid=True, gridcolor="#eee", title="件数"),
                barmode="stack",
            )
            st.plotly_chart(fig_rbm, use_container_width=True, config=CHART_CFG)

    # ── 解約企業一覧 ─────────────────────────────────────────────────────────
    with st.container(border=True):
        section("📋 解約企業一覧", "解約日の新しい順")

        def _sentiment_style(v):
            if v == "ネガティブ":
                return ("background-color:#FBECEC;color:#7A1E1E;"
                        "font-weight:700;text-align:center;border-radius:8px;")
            if v == "ポジティブ":
                return (f"background-color:{MINT_BG};color:{MINT_DARK};"
                        "font-weight:700;text-align:center;border-radius:8px;")
            if v == "ニュートラル":
                return ("background-color:#FFF8EC;color:#8C5E00;"
                        "text-align:center;border-radius:8px;")
            if v == "アンケート未回答":
                return ("background-color:#F0F0F0;color:#555;"
                        "font-weight:700;text-align:center;border-radius:8px;")
            return "color:#999;text-align:center;"

        styled_list = (detail_list.style
            .map(_sentiment_style, subset=["センチメント"])
            .set_properties(**{"font-size": "11px"}))
        st.dataframe(styled_list, use_container_width=True, hide_index=True,
                     height=min(600, 60 + len(detail_list) * 35))


# ── Page: 応募分析 (Application Analysis) ────────────────────────────────────

_BUCKET_DEFS = [
    ("zero", "応募 0件",     "応募がまったく届いていない企業",                   "danger"),
    ("le3",  "応募 3件以下", "応募が1〜3件と少ない企業",                          "warning"),
    ("le5",  "応募 5件以下", "応募が1〜5件の企業（要フォロー候補）",               "warning"),
    ("ge15", "応募 15件以上","応募が15件以上届いている人気企業",                   "success"),
    ("ge20", "応募 20件以上","応募が20件以上の高人気企業",                          "success"),
    ("ge25", "応募 25件以上","応募が25件以上のトップ企業",                          "success"),
]


def render_applications():
    page_header("応募分析", "応募件数の分布・都道府県別・ジャンル別の応募データ")

    monthly_total = queries.get_monthly_apps_from_sheet(con)
    buckets       = queries.get_application_buckets(con)
    pref_df       = queries.get_apps_by_prefecture_from_sheet(con)
    genre_df      = queries.get_apps_by_genre(con)

    # Total apps comes from the applications view directly
    # (bucket sum only counts apps whose company is in our buyer set)
    total_apps = int(con.execute(
        "SELECT COUNT(*) FROM applications").fetchone()[0])
    total_acc  = int(con.execute(
        "SELECT COUNT(*) FROM applications WHERE status='accepted'").fetchone()[0])
    rate       = (total_acc / total_apps * 100) if total_apps else 0
    active_postings = con.execute(
        "SELECT COUNT(*) FROM job_postings WHERE status = 'active'"
    ).fetchone()[0]

    st.markdown(
        '<div class="kpi-grid">'
        + kpi("累計 応募数",    f"{total_apps:,}",   "件", "全期間の応募合計")
        + kpi("採用数",         f"{total_acc:,}",    "件", '<span class="kpi-pill">accepted</span>')
        + kpi("採用率",         f"{rate:.1f}",       "%",  "採用 / 累計応募")
        + kpi("アクティブ募集", f"{active_postings}", "件", "現在公開中の募集")
        + "</div>",
        unsafe_allow_html=True,
    )

    # ── 掲載中案件 一覧 ──────────────────────────────────────────────────────
    with st.container(border=True):
        active_list = queries.get_active_postings_list(con)
        section("📋 掲載中&応募可 案件一覧",
                f"全 {len(active_list)} 件 — 応募者数の多い順")
        if active_list.empty:
            st.info("掲載中の案件がありません。")
        else:
            # Truncate long titles for display
            disp = active_list.copy()
            disp["案件名"] = disp["案件名"].apply(
                lambda v: str(v)[:50] + "…" if v and len(str(v)) > 50 else str(v)
            )
            disp["公開日"] = disp["公開日"].apply(
                lambda v: str(v)[:10] if v else "—"
            )

            def _apps_style(v):
                try:
                    n = int(v)
                    if n == 0:
                        return "background-color:#FBECEC;color:#7A1E1E;font-weight:700;text-align:right;"
                    if n >= 20:
                        return f"background-color:{MINT_BG};color:{MINT_DARK};font-weight:700;text-align:right;"
                    return "text-align:right;"
                except Exception:
                    return ""

            styled = (disp.style
                .map(_apps_style, subset=["応募者数"])
                .set_properties(**{"font-size": "11px"}))
            st.dataframe(styled, use_container_width=True, hide_index=True,
                         height=min(600, 80 + len(disp) * 35))

    # Combo chart: monthly applications (sheet source)
    with st.container(border=True):
        section("月別 応募数",
                "募集作成月ごとの応募数合計（応募者数シートより）")
        if monthly_total.empty:
            st.info("応募データがありません。")
        else:
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=monthly_total["month"], y=monthly_total["applied_count"],
                name="応募数",
                marker_color=MINT_LIGHT,
                marker_line_width=0,
                text=monthly_total["applied_count"],
                textposition="outside",
                textfont=dict(size=10, color=INK_2),
            ))
            fig.update_layout(
                height=300, bargap=0.45,
                legend=dict(orientation="h", y=1.12, x=0),
            )
            themed(fig)
            st.plotly_chart(fig, use_container_width=True, config=CHART_CFG)

    # Activity chart + status breakdown
    _col_act, _col_st = st.columns([2, 1])
    with _col_act:
        with st.container(border=True):
            section("月別 アクティブ企業数 / メッセージ送信数",
                    "棒：月次メッセージ数 ｜ 折れ線：アクティブ企業数")
            mm = queries.get_monthly_messages_and_apps(con)
            if not mm.empty:
                fig = make_subplots(specs=[[{"secondary_y": True}]])
                fig.add_trace(go.Bar(
                    x=mm["activity_month"], y=mm["message_count"],
                    name="メッセージ数",
                    marker_color=MINT_LIGHT,
                    marker_line_width=0,
                ), secondary_y=False)
                fig.add_trace(go.Scatter(
                    x=mm["activity_month"], y=mm["active_companies"],
                    name="アクティブ企業数", mode="lines+markers",
                    line=dict(color=MINT_DARK, width=2.5),
                    marker=dict(size=7, color=MINT_DARK,
                                line=dict(color="white", width=2)),
                ), secondary_y=True)
                fig.update_layout(
                    height=300, bargap=0.45,
                    legend=dict(orientation="h", y=1.12, x=0),
                )
                themed(fig)
                st.plotly_chart(fig, use_container_width=True, config=CHART_CFG)

    with _col_st:
        with st.container(border=True):
            section("応募ステータス内訳", "全応募")
            br = queries.get_application_status_breakdown(con)
            if not br.empty:
                colors = [STATUS_COLORS.get(s, "#CCC") for s in br["status"]]
                total = int(br["count"].sum())
                fig = go.Figure(data=[go.Pie(
                    labels=br["status"], values=br["count"],
                    hole=0.62,
                    marker=dict(colors=colors, line=dict(color="white", width=2)),
                    textinfo="none",
                    sort=False,
                )])
                fig.update_layout(
                    height=300, showlegend=True,
                    legend=dict(orientation="v", x=1.0, y=0.5,
                                yanchor="middle", xanchor="left",
                                font=dict(size=11)),
                    annotations=[dict(
                        text=f"<b style='font-size:18px;color:{INK}'>{total}</b>"
                             f"<br><span style='font-size:10px;color:{INK_3}'>件</span>",
                        x=0.5, y=0.5, showarrow=False, font_size=12,
                    )],
                    margin=dict(l=0, r=10, t=10, b=10),
                )
                themed(fig, margin=dict(l=0, r=10, t=10, b=10))
                st.plotly_chart(fig, use_container_width=True, config=CHART_CFG)

    # Application volume buckets
    section("応募件数バケット", "応募数別の企業ピックアップ — 低件数は要フォロー、高件数はベストプラクティス")
    cards_html = '<div class="bucket-grid">'
    for key, title, desc, klass in _BUCKET_DEFS:
        df = buckets[key]
        names = df["company_name"].tolist()
        if names:
            list_html = "<br>".join(f"・{n}" for n in names[:8])
            if len(names) > 8:
                list_html += f"<br><span style='color:#888'>…他 {len(names)-8} 社</span>"
        else:
            list_html = '<div class="bucket-list-empty">該当企業なし</div>'
        cards_html += (
            f'<div class="bucket {klass}">'
            f'<div class="bucket-head">'
            f'<span class="bucket-title">{title}</span>'
            f'<span class="bucket-count">{len(df)}</span>'
            f'</div>'
            f'<div class="bucket-desc">{desc}</div>'
            f'<div class="bucket-list">{list_html}</div>'
            f'</div>'
        )
    cards_html += "</div>"
    st.markdown(cards_html, unsafe_allow_html=True)

    # Prefecture and genre side-by-side
    col1, col2 = st.columns([3, 2])
    with col1:
        with st.container(border=True):
            section("都道府県別 応募者数（当月・上位10）",
                    "募集中 × 解約連絡あり/公開中/空白 のみ集計")
            if pref_df.empty:
                st.info("都道府県データがありません。")
            else:
                top = pref_df.head(10).sort_values("app_count_current")
                fig = go.Figure()
                fig.add_trace(go.Bar(
                    y=top["prefecture"], x=top["app_count_prev"],
                    name="先月", orientation="h",
                    marker_color=MINT_LIGHT, marker_line_width=0,
                ))
                fig.add_trace(go.Bar(
                    y=top["prefecture"], x=top["app_count_current"],
                    name="当月", orientation="h",
                    marker_color=MINT, marker_line_width=0,
                    text=top["app_count_current"], textposition="outside",
                    textfont=dict(size=10, color=INK_2),
                ))
                fig.update_layout(
                    barmode="group", height=320, yaxis_tickfont_size=11,
                    legend=dict(orientation="h", y=1.12, x=0),
                    margin=dict(l=0, r=40, t=10, b=0),
                )
                themed(fig, margin=dict(l=0, r=40, t=10, b=0))
                st.plotly_chart(fig, use_container_width=True, config=CHART_CFG)

    with col2:
        with st.container(border=True):
            section("ジャンル別 応募者数")
            if genre_df.empty:
                st.info("ジャンルデータがありません。")
            else:
                colors = [
                    MINT_DARK, MINT, MINT_LIGHT, "#7CC2A9",
                    "#A8DCC9", "#C8E8DA", "#DCEFE5", "#E8F4EE"
                ][:len(genre_df)]
                fig = go.Figure(data=[go.Pie(
                    labels=genre_df["category"],
                    values=genre_df["application_count"],
                    hole=0.55,
                    marker=dict(colors=colors, line=dict(color="white", width=2)),
                    textinfo="label+percent",
                    textfont=dict(size=11),
                    sort=False,
                )])
                total_g = int(genre_df["application_count"].sum())
                fig.update_layout(
                    height=320, showlegend=False,
                    annotations=[dict(
                        text=f"<b style='font-size:18px;color:{INK}'>{total_g}</b>"
                             f"<br><span style='font-size:10px;color:{INK_3}'>件</span>",
                        x=0.5, y=0.5, showarrow=False,
                    )],
                    margin=dict(l=0, r=0, t=10, b=10),
                )
                themed(fig, margin=dict(l=0, r=0, t=10, b=10))
                st.plotly_chart(fig, use_container_width=True, config=CHART_CFG)

    # Detailed prefecture / genre tables
    col3, col4 = st.columns(2)
    with col3:
        with st.container(border=True):
            section("都道府県別 詳細（当月 / 先月）")
            if not pref_df.empty:
                disp = pref_df.copy()
                disp["avg_current"] = (
                    disp["app_count_current"] / disp["posting_count"]
                ).round(1).fillna(0)
                disp["avg_prev"] = (
                    disp["app_count_prev"] / disp["posting_count"]
                ).round(1).fillna(0)
                disp = disp.rename(columns={
                    "prefecture":       "都道府県",
                    "posting_count":    "案件数",
                    "app_count_current": "当月応募",
                    "app_count_prev":   "先月応募",
                    "avg_current":      "当月平均",
                    "avg_prev":         "先月平均",
                })
                st.dataframe(
                    disp.style
                    .format({
                        "当月応募": "{:.0f}", "先月応募": "{:.0f}",
                        "当月平均": "{:.1f}", "先月平均": "{:.1f}",
                    })
                    .set_properties(**{"font-size": "12px"}),
                    use_container_width=True, hide_index=True, height=300,
                )
    with col4:
        with st.container(border=True):
            section("ジャンル別 詳細")
            if not genre_df.empty:
                gdf = genre_df.copy()
                gdf["採用率(%)"] = (gdf["accepted_count"] / gdf["application_count"] * 100
                                ).round(1).fillna(0)
                disp = gdf.rename(columns={
                    "category":          "ジャンル",
                    "application_count": "応募数",
                    "accepted_count":    "採用数",
                })
                st.dataframe(disp.style.set_properties(**{"font-size":"12px"}),
                             use_container_width=True, hide_index=True, height=300)


# ── Page: 継続率分析 (Retention) ──────────────────────────────────────────────

def render_retention():
    page_header("継続率分析",
                "シート（契約マスタ）を真のソースに、コホート・プラン・担当別の継続率を分析")

    if not queries.sheet_available(con):
        st.warning(
            "📋 契約マスタシートに接続できていません。\n"
            "credentials.json を `/Users/megumitakahashi/Documents/cs-dashbord/` に "
            "配置し、シートをサービスアカウントに「閲覧者」共有してください。"
        )
        return

    kpis = queries.get_retention_kpis(con)

    # ── Headline KPIs ────────────────────────────────────────────────────────
    st.markdown(
        '<div class="kpi-grid">'
        + kpi("6ヶ月継続率", f"{kpis['six_m_rate']:.0f}", "%",
              f"{kpis['six_m_reached']} / {kpis['six_m_denom']} 社（最低契約期間経過済）")
        + kpi("12ヶ月継続率", f"{kpis['twelve_m_rate']:.0f}", "%",
              f"{kpis['twelve_m_reached']} / {kpis['twelve_m_denom']} 社（最低契約期間経過済）")
        + kpi("平均LTV", f"{kpis['avg_ltv_months']:.1f}", "ヶ月",
              "解約済み企業の平均アクティブ月数")
        + kpi("全体継続率",
              f"{(100 - kpis['churn_rate']):.0f}", "%",
              f"継続 {kpis['continuing']} / 全 {kpis['total']} 社")
        + "</div>",
        unsafe_allow_html=True,
    )

    # ── By plan ─────────────────────────────────────────────────────────────
    with st.container(border=True):
        section("📦 プラン別 継続率")
        byp = queries.get_retention_by_plan(con)
        if not byp.empty:
            disp = byp.rename(columns={
                "plan_name": "プラン",
                "total": "契約数",
                "continuing": "継続",
                "churned": "解約",
                "retention_pct": "継続率(%)",
                "avg_active_months": "平均月数",
            })

            def _pct(v):
                try: r = float(v) / 100
                except: return ""
                return (f"background-color:rgba(79,184,154,{0.10+r*0.50:.2f});"
                        f"color:{MINT_DARK};font-weight:700;text-align:center;")

            styled = (disp.style
                .format({"契約数": "{:.0f}", "継続": "{:.0f}", "解約": "{:.0f}",
                         "継続率(%)": "{:.1f}", "平均月数": "{:.1f}"})
                .map(_pct, subset=["継続率(%)"])
                .set_properties(**{"font-size":"12px"}))
            st.dataframe(styled, use_container_width=True, hide_index=True,
                         height=240)

    # ── By genre ────────────────────────────────────────────────────────────
    with st.container(border=True):
        section("🍴 ジャンル別 継続率")
        byg = queries.get_retention_by_genre(con)
        if not byg.empty:
            byg = byg.copy()
            byg["genre"] = byg["genre"].replace({"nan": "不明", "": "不明"}).fillna("不明")
            disp = byg.rename(columns={
                "genre": "ジャンル",
                "total": "契約数",
                "continuing": "継続",
                "retention_pct": "継続率(%)",
            })
            styled_g = (disp.style
                .format({"契約数": "{:.0f}", "継続": "{:.0f}",
                         "継続率(%)": "{:.1f}"})
                .set_properties(**{"font-size":"12px"}))
            st.dataframe(styled_g, use_container_width=True,
                         hide_index=True, height=300)

    # ── 掲載中企業の継続率分析 ──────────────────────────────────────────────
    act = queries.get_active_companies_retention(con)
    if act:
        with st.container(border=True):
            section("📊 掲載中企業の継続率分析",
                    "AK列（掲載開始日）あり・T列（解約日）なし・S列（状況）=公開中 or 解約連絡あり ／ AN列（最低契約期間）ベースの評価可能コホート")

            # KPIカード
            st.markdown(
                '<div class="kpi-grid" style="grid-template-columns: repeat(4, 1fr);">'
                + kpi("掲載中企業数", f"{act['total_active']}", "社",
                      f"うち評価可能（AN列経過済）{act['evaluable']} 社")
                + kpi("6ヶ月継続率", f"{act['rate_6m']:.0f}", "%",
                      f"{act['reached_6m']} / {act['evaluable']} 社（評価可能コホート）")
                + kpi("12ヶ月継続率", f"{act['rate_12m']:.0f}", "%",
                      f"{act['reached_12m']} / {act['evaluable']} 社（評価可能コホート）")
                + kpi("未評価企業数", f"{act['total_active'] - act['evaluable']}", "社",
                      "AN列の最低契約期間に未到達")
                + "</div>",
                unsafe_allow_html=True,
            )

            st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

            col_bucket, col_plan = st.columns(2)

            # 継続月数バケット
            with col_bucket:
                st.markdown("**継続月数 分布**")
                if not act["buckets"].empty:
                    fig_b = px.bar(
                        act["buckets"],
                        x="bucket", y="company_count",
                        labels={"bucket": "継続月数", "company_count": "社数"},
                        color_discrete_sequence=[MINT],
                    )
                    fig_b.update_layout(
                        height=260, margin=dict(l=0, r=0, t=10, b=0),
                        plot_bgcolor="white", paper_bgcolor="white",
                        xaxis=dict(showgrid=False),
                        yaxis=dict(showgrid=True, gridcolor="#eee"),
                    )
                    st.plotly_chart(fig_b, use_container_width=True)

            # プラン別内訳（評価可能）
            with col_plan:
                st.markdown("**プラン別 内訳（評価可能コホート）**")
                if not act["by_plan"].empty:
                    plan_disp = act["by_plan"].rename(columns={
                        "plan":          "プラン",
                        "company_count": "企業数",
                        "avg_months":    "平均継続(月)",
                        "reached_6m":    "6ヶ月達成",
                        "reached_12m":   "12ヶ月達成",
                    })
                    st.dataframe(
                        plan_disp.style
                        .format({"平均継続(月)": "{:.1f}"})
                        .set_properties(**{"font-size": "12px"}),
                        use_container_width=True,
                        hide_index=True,
                        height=min(300, 60 + len(plan_disp) * 35),
                    )

    # ── 継続月数ランキング ────────────────────────────────────────────────────
    with st.container(border=True):
        section("継続月数ランキング（上位15社）",
                "契約マスタシート由来 — 掲載開始日から解約日（or 現在）までの課金月数")
        ranking = queries.get_continuation_ranking(con, limit=15)
        if not ranking.empty:
            max_months = max(int(ranking["active_months"].max()), 1)
            has_status = "status" in ranking.columns
            rows = []
            for i, (_, r) in enumerate(ranking.iterrows(), 1):
                pct = int(r["active_months"]) / max_months * 100
                if has_status:
                    is_churned = r["status"] == "解約済"
                    badge_color = "#D9534F" if is_churned else MINT_DARK
                    badge_bg    = "#FBECEC" if is_churned else MINT_BG
                    badge = (f'<span style="background:{badge_bg};'
                             f'color:{badge_color};font-size:10px;font-weight:700;'
                             f'padding:2px 8px;border-radius:10px;">'
                             f'{r["status"]}</span>')
                else:
                    badge = (f'<span style="color:{INK_3};font-size:10px;">'
                             f'{int(r.get("activity_count", 0))} 件</span>')
                rows.append(
                    f'<div class="rank-row">'
                    f'<div class="rank-num">{i}</div>'
                    f'<div class="rank-name">{r["company_name"]}</div>'
                    f'<div><div class="rank-bar-track">'
                    f'<div class="rank-bar-fill" style="width:{pct:.0f}%"></div>'
                    f'</div></div>'
                    f'<div class="rank-months">{int(r["active_months"])}ヶ月</div>'
                    f'<div class="rank-count">{badge}</div>'
                    f'</div>'
                )
            st.markdown("".join(rows), unsafe_allow_html=True)

    # ── Cohort heatmap ───────────────────────────────────────────────────────
    with st.container(border=True):
        section("📈 コホート継続率ヒートマップ",
                "縦：申込月 ／ 横：契約からの月数 ／ セル：継続率%（緑が濃い＝高継続）")
        cohort_max_m = st.slider("表示月数（M+）", min_value=6, max_value=24,
                                  value=12, step=3, key="cohort_max_m")
        ch = queries.get_cohort_retention(con)
        if not ch.empty:
            pivot = ch.pivot_table(index="cohort", columns="m_offset",
                                   values="retention_pct", aggfunc="max")
            pivot = pivot.sort_index(ascending=True)
            pivot = pivot.iloc[:, :cohort_max_m + 1]
            pivot.columns = [f"M+{int(c)}" for c in pivot.columns]
            pivot.index.name = "申込月"

            cohort_sizes = (ch[ch["m_offset"] == 0]
                            .set_index("cohort")["total"].to_dict())

            display_pivot = pivot.copy()
            display_pivot.insert(0, "件数",
                pivot.index.map(lambda x: int(cohort_sizes.get(x, 0))))

            def _heat(v):
                if pd.isna(v): return "background-color:#FAFAFA;color:#CCC;"
                ratio = max(0, min(100, v)) / 100
                bg = (f"background-color:rgba(79,184,154,{0.15 + ratio*0.55:.2f});"
                      f"color:{MINT_DARK};font-weight:600;text-align:center;")
                return bg

            def _count(v):
                return f"background-color:{INK};color:white;font-weight:700;text-align:center;"

            month_cols_disp = [c for c in display_pivot.columns if c != "件数"]
            styled = (display_pivot.style
                      .format("{:.0f}%", subset=month_cols_disp, na_rep="")
                      .map(_heat, subset=month_cols_disp)
                      .map(_count, subset=["件数"])
                      .set_properties(**{"font-size":"11px"}))
            st.dataframe(styled, use_container_width=True, height=440)
        else:
            st.info("コホートデータが取得できません。")

    # ── 企業別 継続タイムライン ──────────────────────────────────────────────
    with st.container(border=True):
        section("🏢 企業別 継続タイムライン",
                "縦：企業（掲載開始日順）／ 横：カレンダー月 ／"
                " 🟢継続中 🔴解約月 🔵再開月（一度解約後に再契約した初月）")

        tl_raw = queries.get_company_retention_timeline(con)

        if tl_raw.empty:
            st.info("タイムラインデータが取得できません。")
        else:
            # ── フィルター ──────────────────────────────────────────────────
            c_f1, c_f2 = st.columns([3, 2])
            with c_f1:
                filter_opt = st.radio(
                    "表示対象",
                    ["全企業", "継続中のみ", "解約済みのみ", "再開企業のみ"],
                    horizontal=True,
                    key="tl_filter",
                )
            with c_f2:
                search_q = st.text_input("企業名で絞り込み", placeholder="企業名を入力…", key="tl_search")

            # 企業単位のフラグ
            has_churn  = set(tl_raw[tl_raw["code"] == 2]["company_name"])
            has_reopen = set(tl_raw[tl_raw["code"] == 3]["company_name"])
            has_active = set(tl_raw[tl_raw["code"].isin([1, 3])]["company_name"]) - has_churn

            if filter_opt == "継続中のみ":
                show_cos = has_active - has_churn
            elif filter_opt == "解約済みのみ":
                show_cos = has_churn
            elif filter_opt == "再開企業のみ":
                show_cos = has_reopen
            else:
                show_cos = set(tl_raw["company_name"])

            if search_q:
                show_cos = {c for c in show_cos if search_q.lower() in c.lower()}

            tl = tl_raw[tl_raw["company_name"].isin(show_cos)].copy()

            if tl.empty:
                st.info("該当企業がありません。")
            else:
                # ── ピボット（企業 × 月）──────────────────────────────────
                all_months_tl = sorted(tl_raw["ym"].unique())
                # 企業の順序: クエリ側でソート済みなので first_start 順を維持
                company_order = list(dict.fromkeys(
                    tl_raw[tl_raw["company_name"].isin(show_cos)]["company_name"]
                ))

                pivot_tl = tl.pivot_table(
                    index="company_name", columns="ym",
                    values="code", aggfunc="max",
                ).reindex(index=company_order, columns=all_months_tl, fill_value=0)

                n_rows = len(pivot_tl)
                n_cols = len(all_months_tl)

                # ── Plotly Heatmap ─────────────────────────────────────────
                # 離散カラースケール: 0=未契約(灰) 1=継続(緑) 2=解約月(赤) 3=再開月(青)
                cscale = [
                    [0.000, "#EBEBEB"],
                    [0.333, "#EBEBEB"],
                    [0.334, "#4FB89A"],
                    [0.666, "#4FB89A"],
                    [0.667, "#D9534F"],
                    [0.999, "#D9534F"],
                    [1.000, "#5B8DB8"],
                ]

                code_label = {0: "未契約", 1: "継続中", 2: "解約月", 3: "再開月"}
                z_vals = pivot_tl.values.tolist()
                hover = [
                    [f"<b>{comp}</b><br>{all_months_tl[ci]}<br>{code_label.get(z_vals[ri][ci], '')}"
                     for ci in range(n_cols)]
                    for ri, comp in enumerate(pivot_tl.index)
                ]

                # x軸ラベル: 年が変わる月だけ "YYYY/MM"、それ以外は "MM月"
                x_tick_tl = []
                prev_yr = None
                for m in all_months_tl:
                    yr = m[:4]
                    x_tick_tl.append(f"{yr}/{m[5:]}" if yr != prev_yr else f"{m[5:]}月")
                    prev_yr = yr

                # 初期表示: 直近15ヶ月（多すぎると被るため）
                _init_start = all_months_tl[max(0, len(all_months_tl) - 15)]
                _init_end   = all_months_tl[-1]

                cell_h = max(14, min(22, 1400 // max(n_rows, 1)))
                # rangeslider分の高さを追加
                h_tl   = max(300, n_rows * cell_h + 140)

                fig_tl = go.Figure(data=go.Heatmap(
                    z=z_vals,
                    x=all_months_tl,
                    y=list(pivot_tl.index),
                    text=hover,
                    hovertemplate="%{text}<extra></extra>",
                    colorscale=cscale,
                    showscale=False,
                    xgap=2, ygap=2,
                    zmin=0, zmax=3,
                ))

                fig_tl.update_layout(
                    height=h_tl,
                    margin=dict(l=10, r=20, t=40, b=10),
                    paper_bgcolor="#FFFFFF",
                    plot_bgcolor="#FFFFFF",
                    xaxis=dict(
                        tickmode="array",
                        tickvals=all_months_tl,
                        ticktext=x_tick_tl,
                        side="top",
                        tickfont=dict(size=10, color=INK_3),
                        showgrid=False,
                        tickangle=0,
                        # 初期表示範囲（直近15ヶ月）
                        range=[_init_start, _init_end],
                        # 横スライド用 rangeslider
                        rangeslider=dict(
                            visible=True,
                            thickness=0.05,
                            bgcolor="#F5F5F5",
                            bordercolor="#DDDDDD",
                            borderwidth=1,
                        ),
                    ),
                    yaxis=dict(
                        tickfont=dict(size=10, color=INK_2),
                        showgrid=False,
                        autorange="reversed",
                        # rangeslider と y軸を連動させる
                        fixedrange=False,
                    ),
                )

                # 凡例
                legend_html = (
                    '<div style="display:flex;gap:18px;margin:6px 0 2px;flex-wrap:wrap;">'
                    + "".join(
                        f'<span style="display:flex;align-items:center;gap:5px;font-size:12px;">'
                        f'<span style="width:14px;height:14px;border-radius:3px;'
                        f'background:{c};display:inline-block;"></span>{lbl}</span>'
                        for c, lbl in [
                            ("#4FB89A", "継続中"),
                            ("#D9534F", "解約月"),
                            ("#5B8DB8", "再開月（解約後に再契約）"),
                            ("#EBEBEB", "未契約"),
                        ]
                    )
                    + "</div>"
                )
                st.markdown(legend_html, unsafe_allow_html=True)
                st.caption(f"表示: {n_rows} 社 ／ 全 {tl_raw['company_name'].nunique()} 社")
                st.plotly_chart(fig_tl, use_container_width=True, config=CHART_CFG)

                # 再開企業ハイライトリスト
                reopened_in_view = [c for c in pivot_tl.index if c in has_reopen]
                if reopened_in_view:
                    st.markdown(
                        f'<div style="background:#EEF4FB;border-left:4px solid #5B8DB8;'
                        f'border-radius:6px;padding:8px 14px;margin-top:4px;">'
                        f'<span style="color:#5B8DB8;font-weight:700;font-size:12px;">'
                        f'🔵 再開企業 {len(reopened_in_view)} 社</span>'
                        f'<span style="color:#4A4A4A;font-size:11px;margin-left:10px;">'
                        + " / ".join(reopened_in_view)
                        + "</span></div>",
                        unsafe_allow_html=True,
                    )


# ── Page: 未回収債権 ──────────────────────────────────────────────────────────

def render_uncollected():
    page_header("未回収債権",
                "入金確認済チェックなし — 企業別残高・明細一覧")

    kpis = queries.get_uncollected_kpis(con)

    if not kpis:
        st.warning("🔌 未回収債権シートを読み込めませんでした。credentials.json を確認してください。")
        return

    def _yen(n):
        return f"¥{n:,.0f}"

    st.markdown(
        '<div class="kpi-grid">'
        + kpi("未回収件数",    str(kpis["invoice_count"]),       "件",   "入金確認済でない請求書の総数")
        + kpi("未回収総額",    _yen(kpis["total_amount"]),       "",     "未払い請求金額の合計")
        + kpi("対象企業数",    str(kpis["company_count"]),       "社",   "未回収が残っている企業数")
        + kpi("期日超過額",    _yen(kpis["overdue_amount"]),     "",     "決済期日が過ぎているもの")
        + "</div>",
        unsafe_allow_html=True,
    )

    # ── 企業別サマリー ────────────────────────────────────────────────────────
    with st.container(border=True):
        section("🏢 企業別 未回収サマリー",
                "決済残額（顧客合計）の大きい順")
        by_company = queries.get_uncollected_by_company(con)
        if not by_company.empty:
            def _amt_style(v):
                try:
                    n = int(str(v).replace(",", ""))
                    if n >= 100000:
                        return "background-color:#FBECEC;color:#7A1E1E;font-weight:700;text-align:right;"
                    if n >= 50000:
                        return "background-color:#FFF3CD;color:#856404;text-align:right;"
                    return "text-align:right;"
                except Exception:
                    return ""

            def _status_style(v):
                if not v:
                    return "color:#999;"
                return ""

            # Format amounts with ¥ and comma
            disp = by_company.copy()
            disp["決済残額"]  = disp["決済残額"].apply(lambda x: f"¥{int(x):,}" if x else "—")
            disp["未払い総額"] = disp["未払い総額"].apply(lambda x: f"¥{int(x):,}" if x else "—")
            disp["最終決済期日"] = disp["最終決済期日"].apply(
                lambda v: str(v)[:10] if v and str(v) != "None" else "—"
            )
            disp["連絡状況"] = disp["連絡状況"].fillna("—").apply(
                lambda v: str(v)[:40] + "…" if len(str(v)) > 40 else str(v)
            )

            st.dataframe(
                disp.style.set_properties(**{"font-size": "12px"}),
                use_container_width=True,
                hide_index=True,
                height=min(600, 60 + len(disp) * 35),
            )
        else:
            st.success("未回収債権なし 🎉")

    # ── 明細一覧 ──────────────────────────────────────────────────────────────
    with st.expander("📋 明細一覧（請求書単位）", expanded=False):
        detail = queries.get_uncollected_detail(con)
        if not detail.empty:
            detail["請求金額"] = detail["請求金額"].apply(lambda x: f"¥{int(x):,}" if x else "—")
            detail["決済残額"] = detail["決済残額"].apply(lambda x: f"¥{int(x):,}" if x else "—")
            detail["決済期日"] = detail["決済期日"].apply(lambda v: str(v)[:10] if v and str(v) != "None" else "—")
            detail["連絡状況"] = detail["連絡状況"].fillna("—").apply(
                lambda v: str(v)[:50] + "…" if len(str(v)) > 50 else str(v)
            )
            st.dataframe(
                detail.style.set_properties(**{"font-size": "11px"}),
                use_container_width=True,
                hide_index=True,
                height=400,
            )


# ── Page: CS業務用 ─────────────────────────────────────────────────────────────

# 外部レポートURL（profile_id = profiles.id = projects.author_id）
_REPORT_BASE = "https://report-pepper-likes.vercel.app/company"
_REPORT_KEY  = "3bbbe2916394fad36c328a7ff2f08c21676529070252052f7911e6137d028d48"

def _report_url(profile_id: str) -> str:
    return f"{_REPORT_BASE}/{profile_id}?key={_REPORT_KEY}"

def render_cs_ops():
    page_header("CS業務用", "企業を検索してリアルタイムの活動・案件・応募状況を確認")

    # ── 企業検索 ──────────────────────────────────────────────────────────────
    companies_df = queries.get_cs_company_list(con)
    if companies_df.empty:
        st.info("企業データがありません。")
        return

    # テキスト検索でフィルタリング
    search_col, _ = st.columns([3, 5])
    with search_col:
        search_q = st.text_input(
            "🔍 企業名で検索",
            placeholder="企業名を入力して絞り込み...",
            label_visibility="collapsed",
        )

    if search_q:
        mask = companies_df["company_name"].str.contains(
            search_q, case=False, na=False, regex=False
        )
        filtered_df = companies_df[mask]
    else:
        filtered_df = companies_df

    if filtered_df.empty:
        st.warning(f'「{search_q}」に一致する企業が見つかりません。')
        return

    sel_col, link_col = st.columns([5, 1])
    with sel_col:
        selected_name = st.selectbox(
            "企業を選択",
            filtered_df["company_name"].tolist(),
            label_visibility="collapsed",
        )

    # profile_id 取得（レポートURLのキー）
    sel_row   = filtered_df.loc[filtered_df["company_name"] == selected_name].iloc[0]
    cid       = sel_row["company_id"]
    sel_pid   = sel_row.get("profile_id", "")

    with link_col:
        if sel_pid:
            st.link_button(
                "📊 レポートを開く",
                _report_url(sel_pid),
                use_container_width=True,
            )
        else:
            st.link_button(
                "🔗 pepperlikes.com",
                "https://www.pepperlikes.com",
                use_container_width=True,
            )

    # ── 企業情報バー ──────────────────────────────────────────────────────────
    info_df = queries.get_company_info(con, cid)
    sheet_df = queries.get_cs_sheet_contract(con, selected_name)

    if not info_df.empty:
        row = info_df.iloc[0]
        db_status = row.get("status", "—")
        s_color = MINT_DARK if db_status == "active" else (
            "#D9534F" if db_status == "churned" else "#F5A623"
        )
        s_bg = MINT_BG if db_status == "active" else (
            "#FBECEC" if db_status == "churned" else "#FEF6E5"
        )
        status_label = {
            "active": "契約中", "churned": "解約済",
            "suspended": "停止中",
        }.get(db_status, db_status)

        # シートから追加情報
        sheet_status = "—"
        sheet_billed = "—"
        sheet_owner  = "—"
        sheet_start  = "—"
        if not sheet_df.empty:
            sr = sheet_df.iloc[0]
            sheet_status = str(sr.get("status", "—") or "—")
            bm = sr.get("billed_months")
            sheet_billed = f"{int(float(bm))} ヶ月" if bm and str(bm) not in ("", "nan") else "—"
            sheet_owner  = str(sr.get("sales_owner", "—") or "—")
            sd = sr.get("start_date")
            sheet_start  = str(sd)[:10] if sd and str(sd) not in ("None", "NaT", "nan", "") else "—"

        st.markdown(f"""
        <div class="kpi" style="margin-bottom:14px;display:flex;flex-wrap:wrap;
                                gap:28px;align-items:center;padding:16px 24px;">
            <div>
                <div class="kpi-label">企業名</div>
                <div style="font-size:16px;font-weight:700;color:{INK};">{selected_name}</div>
            </div>
            <div>
                <div class="kpi-label">ステータス（DB）</div>
                <span class="status-badge"
                      style="background:{s_bg};color:{s_color};padding:3px 10px;
                             border-radius:6px;font-size:12px;font-weight:700;">
                    {status_label}
                </span>
            </div>
            <div>
                <div class="kpi-label">ステータス（シート）</div>
                <div style="font-size:13px;font-weight:600;color:{INK};">{sheet_status}</div>
            </div>
            <div>
                <div class="kpi-label">プラン</div>
                <div style="font-size:13px;font-weight:600;color:{INK};">{row.get('plan_type','-')}</div>
            </div>
            <div>
                <div class="kpi-label">掲載開始日</div>
                <div style="font-size:13px;font-weight:600;color:{INK};">{sheet_start}</div>
            </div>
            <div>
                <div class="kpi-label">継続月数</div>
                <div style="font-size:20px;font-weight:700;color:{MINT_DARK};
                            letter-spacing:-0.5px;">{sheet_billed}</div>
            </div>
            <div>
                <div class="kpi-label">担当営業</div>
                <div style="font-size:13px;font-weight:600;color:{INK};">{sheet_owner}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # ── 3タブ: 案件 / 応募 / 活動推移 ─────────────────────────────────────────
    tab_proj, tab_apps, tab_trend = st.tabs(
        ["📋 掲載案件一覧", "📩 最近の応募", "📈 月別活動推移"]
    )

    # ── 掲載案件一覧 ──────────────────────────────────────────────────────────
    with tab_proj:
        proj_df = queries.get_cs_company_projects_with_apps(con, cid)
        if proj_df.empty:
            st.info("案件データがありません。")
        else:
            # ステータスバッジ用のスタイル
            def _proj_status_style(v):
                if v == "active":
                    return f"background-color:{MINT_BG};color:{MINT_DARK};font-weight:700;text-align:center;"
                return "color:#999;text-align:center;"

            disp = proj_df.copy()
            disp["status"] = disp["status"].map(
                {"active": "掲載中", "closed": "終了", "draft": "下書き"}
            ).fillna(disp["status"])

            disp_cols = {
                "title": "案件タイトル",
                "status": "状態",
                "category": "カテゴリ",
                "platforms": "SNS",
                "compensation_type": "報酬",
                "total_apps": "総応募",
                "accepted_apps": "採用",
                "pending_apps": "保留中",
                "created_date": "作成日",
            }
            avail = [c for c in disp_cols if c in disp.columns]
            st.dataframe(
                disp[avail].rename(columns=disp_cols)
                .style
                .map(_proj_status_style, subset=["状態"])
                .set_properties(**{"font-size": "12px"}),
                use_container_width=True,
                hide_index=True,
                height=min(600, 80 + len(disp) * 35),
            )

            # サマリーKPI
            active_cnt  = (proj_df["status"] == "active").sum()
            total_apps  = proj_df["total_apps"].sum()
            hired_cnt   = proj_df["accepted_apps"].sum()
            pending_cnt = proj_df["pending_apps"].sum()
            st.markdown(
                '<div class="kpi-grid" style="margin-top:12px;">'
                + kpi("掲載中案件", str(active_cnt), "件", "現在公開中の募集")
                + kpi("累計応募数",  str(int(total_apps)), "件", "全案件合計")
                + kpi("採用数",      str(int(hired_cnt)),  "件", "採用済みインフルエンサー")
                + kpi("保留中応募",  str(int(pending_cnt)),"件", "未対応の応募")
                + "</div>",
                unsafe_allow_html=True,
            )

    # ── 最近の応募 ────────────────────────────────────────────────────────────
    with tab_apps:
        apps_df = queries.get_cs_recent_applications(con, cid, limit=50)
        if apps_df.empty:
            st.info("応募データがありません（DBは2026-03-26以降の応募は含まれない場合があります）。")
        else:
            def _app_status_style(v):
                color_map = {
                    "採用":   f"background-color:{MINT_BG};color:{MINT_DARK};font-weight:700;",
                    "完了":   f"background-color:{MINT_BG};color:{MINT_DARK};font-weight:700;",
                    "審査中": "background-color:#FEF6E5;color:#856404;",
                    "不採用": "background-color:#FBECEC;color:#7A1E1E;",
                }
                return color_map.get(str(v), "color:#999;") + "text-align:center;"

            status_jp = {
                "hired": "採用", "completed": "完了",
                "declined": "不採用", "rejected": "不採用", "refunded": "不採用",
                "new": "審査中", "active": "審査中", "pending": "審査中",
                "draft": "下書き", "publish": "下書き",
            }
            apps_disp = apps_df.copy()
            apps_disp["応募状態"] = apps_disp["応募状態"].map(status_jp).fillna(apps_disp["応募状態"])

            st.dataframe(
                apps_disp.style
                .map(_app_status_style, subset=["応募状態"])
                .set_properties(**{"font-size": "12px"}),
                use_container_width=True,
                hide_index=True,
                height=min(600, 80 + len(apps_disp) * 35),
            )
            st.caption(f"直近 {len(apps_disp)} 件表示 ／ ⚠️ DBは2026-03-26以降のデータは同期されていません")

    # ── 月別活動推移 ──────────────────────────────────────────────────────────
    with tab_trend:
        trend_df = queries.get_cs_monthly_activity(con, cid)
        if trend_df.empty:
            st.info("月別活動データがありません。")
        else:
            fig = go.Figure()
            fig.add_bar(
                x=trend_df["month"],
                y=trend_df["app_count"],
                name="応募数",
                marker_color=MINT_LIGHT,
                marker_line_width=0,
            )
            fig.add_bar(
                x=trend_df["month"],
                y=trend_df["hired_count"],
                name="採用数",
                marker_color=MINT_DARK,
                marker_line_width=0,
            )
            fig.update_layout(
                barmode="overlay",
                xaxis_title="月",
                yaxis_title="件数",
                height=320,
                legend=dict(orientation="h", y=1.08, x=0),
            )
            themed(fig)
            with st.container(border=True):
                section("月別 応募数・採用数", "DBデータ / 2026-03-26以前")
                st.plotly_chart(fig, use_container_width=True, config=CHART_CFG)
                st.caption("⚠️ 2026-03-26以降のデータはDBに含まれていません")

        # メッセージ推移（直近12週）
        weekly_df = queries.get_company_weekly_messages(con, cid)
        if not weekly_df.empty:
            fig2 = px.bar(
                weekly_df, x="iso_week", y="message_count",
                labels={"iso_week": "週", "message_count": "送信数"},
            )
            fig2.update_traces(
                marker_color=MINT, marker_line_width=0, marker_cornerradius=4
            )
            fig2.update_layout(height=280)
            themed(fig2)
            with st.container(border=True):
                section("週次メッセージ送信数（直近12週）", "企業→インフルエンサー方向")
                st.plotly_chart(fig2, use_container_width=True, config=CHART_CFG)


# ── Page: 利用状況 ─────────────────────────────────────────────────────────────

def _build_usage_heatmap(
    pivot: pd.DataFrame,
    x_labels: list,
    title: str,
    unit: str = "件",
    x_tick_labels: list = None,   # 表示するラベル（Noneなら全列）
) -> go.Figure:
    """
    GitHub コントリビューショングラフ風ヒートマップ。
    - 0件: ライトグレー (#ebedf0)
    - 1件以上: GitHub グリーングラデーション
    - 全ての列（日付/期間）を表示（データなし=グレー）
    """
    companies = pivot.index.tolist()
    n_cols    = len(x_labels)
    n_rows    = len(companies)

    # GitHub ライトテーマのカラースケール
    # zmin=0 を前提: 0→グレー, 0超→グリーン段階
    cscale = [
        [0.000, "#ebedf0"],   # 0件: GitHub の空セル色
        [0.001, "#9be9a8"],   # level 1
        [0.25,  "#40c463"],   # level 2
        [0.60,  "#30a14e"],   # level 3
        [1.000, "#216e39"],   # level 4 (最大)
    ]

    z_vals = pivot.values.tolist()

    hover = []
    for r_i, comp in enumerate(companies):
        row_text = []
        for c_i, col in enumerate(x_labels):
            v = z_vals[r_i][c_i]
            row_text.append(f"<b>{comp}</b><br>{col}<br>{int(v)} {unit}")
        hover.append(row_text)

    # X軸チックラベル: 月の変わり目だけ表示してスッキリ見せる
    if x_tick_labels is None:
        # 列数が多い場合は間引く
        step = max(1, n_cols // 20)
        visible_ticks = {i: x_labels[i] for i in range(0, n_cols, step)}
    else:
        visible_ticks = {i: x_tick_labels[i] for i in range(len(x_tick_labels))}

    tick_vals = list(visible_ticks.keys())
    tick_text = list(visible_ticks.values())

    # セル高さ: 13px（GitHub準拠）、最低20px
    cell_h = max(20, min(26, 1200 // max(n_rows, 1)))
    h = max(200, n_rows * cell_h + 90)

    fig = go.Figure(data=go.Heatmap(
        z=z_vals,
        x=list(range(n_cols)),
        y=companies,
        text=hover,
        hovertemplate="%{text}<extra></extra>",
        colorscale=cscale,
        showscale=True,
        colorbar=dict(
            title=dict(text=unit, side="right"),
            thickness=10,
            len=min(0.8, 120 / h),
            tickfont=dict(size=9),
            outlinewidth=0,
        ),
        xgap=3,
        ygap=3,
        zmin=0,
    ))

    fig.update_layout(
        title=dict(text=title, font=dict(size=13, color=INK_2), x=0),
        height=h,
        margin=dict(l=10, r=60, t=50, b=10),
        xaxis=dict(
            tickmode="array",
            tickvals=tick_vals,
            ticktext=tick_text,
            side="top",
            tickfont=dict(size=10, color=INK_3),
            showgrid=False,
            zeroline=False,
            tickangle=0,
            range=[-0.5, n_cols - 0.5],
        ),
        yaxis=dict(
            tickfont=dict(size=11, color=INK_2),
            showgrid=False,
            zeroline=False,
            autorange="reversed",
        ),
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
    )
    return fig


def render_usage():
    page_header("利用状況", "企業×時間軸の活動ヒートマップ（DBリアルタイム）")
    st.caption("※ メッセージデータはDBの2026-03-26以前分。応募/採用/完了はDBの全期間。")

    # ── シート × DB 解約マッピング ──────────────────────────────────────────
    churn_df     = queries.get_company_churn_mapping(con)
    pid_to_churn = churn_df.set_index("profile_id")["is_churned"].to_dict()

    # 解約済み企業には「（解約: YYYY-MM）」を表示名に付与（全タブ共通）
    pid_to_display: dict = {}
    for _, row in churn_df.iterrows():
        pid  = str(row["profile_id"])
        name = str(row["display_name"])
        cm   = str(row.get("churn_month", "") or "")
        if row["is_churned"] == 1 and cm:
            name = f"{name}（解約: {cm}）"
        pid_to_display[pid] = name

    # ── セクションヘッダー描画ヘルパー ──────────────────────────────────────
    def _section_header(label: str, n: int, is_churned: bool):
        color = "#D9534F" if is_churned else MINT_DARK
        bg    = "#FBECEC" if is_churned else MINT_BG
        st.markdown(
            f'<div style="background:{bg};border-radius:6px;padding:6px 14px;'
            f'margin:10px 0 4px;border-left:4px solid {color};">'
            f'<span style="color:{color};font-weight:700;font-size:13px;">'
            f'{label}（{n}社）</span></div>',
            unsafe_allow_html=True,
        )

    # ── 企業名クリックリンク描画ヘルパー ────────────────────────────────────
    def _company_links(names_pids):
        html = '<div style="display:flex;flex-wrap:wrap;gap:5px;margin-top:6px;">'
        for name, pid in names_pids:
            pid = str(pid or "").strip()
            url = _report_url(pid) if pid else "#"
            html += (
                f'<a href="{url}" target="_blank" style="display:inline-block;'
                f'background:{MINT_BG};color:{MINT_DARK};padding:3px 10px;'
                f'border-radius:4px;font-size:11px;text-decoration:none;'
                f'border:1px solid {MINT_LIGHT};">{name} ↗</a>'
            )
        html += "</div>"
        st.markdown(html, unsafe_allow_html=True)

    # ── pivot に display_name / is_churned を付与して 継続/解約 に分割 ──────
    def _enrich_and_split(raw_df, index_col, value_col, all_columns):
        raw_df = raw_df.copy()
        raw_df["display_name"] = (
            raw_df["profile_id"].astype(str).map(pid_to_display)
            .fillna(raw_df[index_col])
        )
        raw_df["is_churned"] = (
            raw_df["profile_id"].astype(str).map(pid_to_churn)
            .fillna(0).astype(int)
        )
        pivot = raw_df.pivot_table(
            index="display_name", columns=value_col,
            values=index_col, aggfunc="sum", fill_value=0,
        )
        pivot = pivot.reindex(columns=all_columns, fill_value=0)
        pivot = pivot.loc[pivot.sum(axis=1) > 0]

        dedup         = raw_df.drop_duplicates("display_name").set_index("display_name")
        name_to_pid   = dedup["profile_id"].to_dict()
        name_to_churn = dedup["is_churned"].to_dict()

        pa = pivot.loc[[n for n in pivot.index if name_to_churn.get(n, 0) == 0]]
        pc = pivot.loc[[n for n in pivot.index if name_to_churn.get(n, 0) == 1]]
        if not pa.empty:
            pa = pa.loc[pa.sum(axis=1).sort_values(ascending=False).index]
        if not pc.empty:
            pc = pc.loc[pc.sum(axis=1).sort_values(ascending=False).index]
        return pa, pc, name_to_pid

    # ── ヒートマップ + リンクをまとめて描画 ─────────────────────────────────
    def _draw_heatmap_section(pivot_sub, x_labels, x_tick_labels,
                               title, unit, name_to_pid, label, is_churned):
        if pivot_sub.empty:
            return
        _section_header(label, len(pivot_sub), is_churned)
        fig = _build_usage_heatmap(
            pivot_sub, x_labels,
            title=title, unit=unit, x_tick_labels=x_tick_labels,
        )
        st.plotly_chart(fig, use_container_width=True, config=CHART_CFG)
        st.caption(f"合計 {int(pivot_sub.values.sum()):,} {unit}")
        _company_links([(n, name_to_pid.get(n, "")) for n in pivot_sub.index])

    # ── 期間選択ヘルパー ──────────────────────────────────────────────────────
    _PRESET_OPTS   = ["1ヶ月", "3ヶ月", "6ヶ月", "12ヶ月", "24ヶ月", "カスタム"]
    _PRESET_MONTHS = {"1ヶ月": 1, "3ヶ月": 3, "6ヶ月": 6, "12ヶ月": 12, "24ヶ月": 24}
    _DATA_START    = date(2024, 5, 1)   # シートデータの最古

    def _date_range_ui(key: str, default: str = "6ヶ月"):
        """プリセットラジオ + カスタム日付入力 → (start_date, end_date) を返す。"""
        _today = date.today()
        c1, c2 = st.columns([3, 2])
        with c1:
            preset = st.radio(
                "期間",
                _PRESET_OPTS,
                index=_PRESET_OPTS.index(default),
                horizontal=True,
                key=f"preset_{key}",
            )
        if preset == "カスタム":
            with c2:
                dr = st.date_input(
                    "開始日 〜 終了日",
                    value=(date(_today.year - 1, _today.month, 1), _today),
                    min_value=_DATA_START,
                    max_value=_today,
                    key=f"custom_{key}",
                )
            if isinstance(dr, (list, tuple)) and len(dr) == 2:
                return dr[0], dr[1]
            return _today.replace(day=1), _today
        else:
            n_months = _PRESET_MONTHS[preset]
            _base    = _today.year * 12 + _today.month - 1
            _tm      = _base - n_months + 1
            return date(_tm // 12, _tm % 12 + 1, 1), _today

    # ── 月リスト・期間ラベル生成ヘルパー ────────────────────────────────────
    def _months_in_range(start: date, end: date):
        """start〜end の YYYY-MM リストを返す。"""
        result = []
        base = start.year * 12 + start.month - 1
        top  = end.year   * 12 + end.month   - 1
        for tm in range(base, top + 1):
            result.append(f"{tm // 12:04d}-{tm % 12 + 1:02d}")
        return result

    def _periods_in_range(start: date, end: date):
        """start〜end の 'YYYY-MM 1〜10日' 形式リストを返す（1ヶ月3区切り）。"""
        result = []
        for ym in _months_in_range(start, end):
            for p in ["1〜10日", "11〜20日", "21〜31日"]:
                result.append(f"{ym} {p}")
        return result

    def _ym_tick_labels(cols: list[str]):
        """月変わり目だけラベルを出す tick list を返す（YYYY-MM または 'YYYY-MM period' 形式に対応）。"""
        ticks, prev = [], None
        for col in cols:
            ym = col[:7]
            ticks.append(ym[5:] + "/" + ym[:4] if ym != prev else "")
            prev = ym
        return ticks

    def _date_tick_labels(dates: list[str]):
        """日付リスト（YYYY-MM-DD）から月変わり目ラベルを返す。"""
        ticks, prev = [], None
        for d in dates:
            ym = d[:7]
            ticks.append(d[5:7] + "/" + d[:4] if ym != prev else "")
            prev = ym
        return ticks

    def _dates_in_range(start: date, end: date):
        """start〜end の YYYY-MM-DD リストを返す。"""
        result, cur = [], start
        while cur <= end:
            result.append(cur.strftime("%Y-%m-%d"))
            cur += timedelta(days=1)
        return result

    # ── ヒートマップ共通: pivot生成 + 継続/解約分割 ─────────────────────────
    def _make_pivot(raw_df, col_key, val_col, all_cols):
        raw_df = raw_df.copy()
        raw_df["display_name"] = (
            raw_df["profile_id"].astype(str).map(pid_to_display)
            .fillna(raw_df["company_name"])
        )
        raw_df["is_churned"] = (
            raw_df["profile_id"].astype(str).map(pid_to_churn)
            .fillna(0).astype(int)
        )
        piv = raw_df.pivot_table(
            index="display_name", columns=col_key,
            values=val_col, aggfunc="sum", fill_value=0,
        )
        piv = piv.reindex(columns=all_cols, fill_value=0)
        piv = piv.loc[piv.sum(axis=1) > 0]
        dedup = raw_df.drop_duplicates("display_name").set_index("display_name")
        n2pid  = dedup["profile_id"].to_dict()
        n2chur = dedup["is_churned"].to_dict()
        import re as _re
        pa = piv.loc[[n for n in piv.index if n2chur.get(n, 0) == 0]]
        pc = piv.loc[[n for n in piv.index if n2chur.get(n, 0) == 1]]
        # 継続中: 合計件数降順
        if not pa.empty:
            pa = pa.loc[pa.sum(axis=1).sort_values(ascending=False).index]
        # 解約済み: 解約日が浅い（直近）順。日付不明は末尾
        if not pc.empty:
            def _churn_ym(name):
                m = _re.search(r'解約: (\d{4}-\d{2})', name)
                return m.group(1) if m else "0000-00"
            pc = pc.loc[sorted(pc.index, key=_churn_ym, reverse=True)]
        return pa, pc, n2pid

    def _draw_split(pa, pc, all_cols, tick_labels, label_a, label_c, unit, n2pid, caption_extra=""):
        total = int(pa.values.sum() if not pa.empty else 0) + int(pc.values.sum() if not pc.empty else 0)
        st.caption(
            f"対象 {len(pa)+len(pc)} 社 ／ 合計 {total:,} {unit}"
            + (f" ／ {caption_extra}" if caption_extra else "")
        )
        _draw_heatmap_section(pa, all_cols, tick_labels, label_a, unit, n2pid, "🟢 継続中", False)
        _draw_heatmap_section(pc, all_cols, tick_labels, label_c, unit, n2pid, "🔴 解約済み", True)

    # ── 5タブ ─────────────────────────────────────────────────────────────────
    tab_msg, tab_app, tab_hire, tab_done, tab_monthly = st.tabs(
        ["💬 メッセージ数", "📩 応募数", "✅ 採用数", "🎉 完了数", "📅 月別"]
    )

    # ─────────────────────── メッセージ数（日次）──────────────────────────────
    with tab_msg:
        s_msg, e_msg = _date_range_ui("msg", default="3ヶ月")
        raw = queries.get_usage_heatmap_messages(
            con,
            start_date=s_msg.strftime("%Y-%m-%d"),
            end_date=e_msg.strftime("%Y-%m-%d"),
            active_only=False,
        )
        all_dates = _dates_in_range(s_msg, e_msg)
        if raw.empty:
            st.info("メッセージデータがありません。（DBは2026-03-26以降同期停止）")
        else:
            raw["day"] = raw["day"].astype(str)
            pa_m, pc_m, n2pid_m = _make_pivot(raw, "day", "cnt", all_dates)
            period_label = f"{s_msg.strftime('%Y/%m/%d')} 〜 {e_msg.strftime('%Y/%m/%d')}"
            _draw_split(
                pa_m, pc_m, all_dates, _date_tick_labels(all_dates),
                f"メッセージ送信数（{period_label}） — 継続中",
                f"メッセージ送信数（{period_label}） — 解約済み",
                "件", n2pid_m,
                caption_extra="⚠️ DBは2026-03-26以降のメッセージは未同期",
            )

    # ─────── 応募数 / 採用数 / 完了数（1ヶ月3区切り）─────────────────────────
    def _render_proposal_tab(col_name: str, label: str, unit: str, tab):
        with tab:
            s_p, e_p = _date_range_ui(col_name, default="6ヶ月")
            raw_p = queries.get_usage_heatmap_proposals(
                con,
                start_date=s_p.strftime("%Y-%m-%d"),
                end_date=e_p.strftime("%Y-%m-%d"),
                active_only=False,
            )
            all_periods = _periods_in_range(s_p, e_p)
            if raw_p.empty:
                st.info("データがありません。")
                return
            raw_p["col_label"] = raw_p["ym"] + " " + raw_p["period"]
            period_order = {"1〜10日": 0, "11〜20日": 1, "21〜31日": 2}
            raw_p["period_ord"] = raw_p["period"].map(period_order)
            raw_p = raw_p.sort_values(["ym", "period_ord"])
            pa_p, pc_p, n2pid_p = _make_pivot(raw_p, "col_label", col_name, all_periods)
            if pa_p.empty and pc_p.empty:
                st.info(f"{label}データがありません。")
                return
            period_label = f"{s_p.strftime('%Y/%m/%d')} 〜 {e_p.strftime('%Y/%m/%d')}"
            _draw_split(
                pa_p, pc_p, all_periods, _ym_tick_labels(all_periods),
                f"{label}（{period_label} / 1ヶ月3区切り） — 継続中",
                f"{label}（{period_label} / 1ヶ月3区切り） — 解約済み",
                unit, n2pid_p,
            )

    _render_proposal_tab("app_count",      "応募数", "件", tab_app)
    _render_proposal_tab("hire_count",     "採用数", "件", tab_hire)
    _render_proposal_tab("complete_count", "完了数", "件", tab_done)

    # ─────────────────────── 月別サマリー ────────────────────────────────────
    with tab_monthly:
        metric_sel = st.radio(
            "指標",
            ["💬 メッセージ数", "📩 応募数", "✅ 採用数", "🎉 完了数"],
            horizontal=True,
            key="monthly_metric",
        )
        s_m, e_m = _date_range_ui("monthly", default="12ヶ月")
        all_months = _months_in_range(s_m, e_m)
        x_tick_m   = _ym_tick_labels(all_months)

        def _render_monthly(raw_df, value_col, label, unit, extra_caption=""):
            if raw_df.empty:
                st.info(f"{label}データがありません。")
                return
            pa, pc, n2pid = _make_pivot(raw_df, "ym", value_col, all_months)
            if pa.empty and pc.empty:
                st.info(f"{label}データがありません。")
                return
            period_label = f"{s_m.strftime('%Y/%m/%d')} 〜 {e_m.strftime('%Y/%m/%d')}"
            _draw_split(
                pa, pc, all_months, x_tick_m,
                f"{label}（{period_label}） — 継続中",
                f"{label}（{period_label}） — 解約済み",
                unit, n2pid,
                caption_extra=extra_caption,
            )

        if "メッセージ" in metric_sel:
            raw_mm = queries.get_usage_heatmap_messages_monthly(
                con,
                start_date=s_m.strftime("%Y-%m-%d"),
                end_date=e_m.strftime("%Y-%m-%d"),
                active_only=False,
            )
            _render_monthly(
                raw_mm, "cnt", "メッセージ送信数", "件",
                extra_caption="⚠️ DBは2026-03-26以降のメッセージは未同期",
            )
        else:
            col_map   = {"📩 応募数": "app_count", "✅ 採用数": "hire_count", "🎉 完了数": "complete_count"}
            label_map = {"📩 応募数": "応募数",    "✅ 採用数": "採用数",     "🎉 完了数": "完了数"}
            raw_pm = queries.get_usage_heatmap_proposals_monthly(
                con,
                start_date=s_m.strftime("%Y-%m-%d"),
                end_date=e_m.strftime("%Y-%m-%d"),
                active_only=False,
            )
            _render_monthly(raw_pm, col_map[metric_sel], label_map[metric_sel], "件")


# ── Router ────────────────────────────────────────────────────────────────────

{
    "summary":      render_summary,
    "retention":    render_retention,
    "churn":        render_churn,
    "applications": render_applications,
    "uncollected":  render_uncollected,
    "cs_ops":       render_cs_ops,
    "usage":        render_usage,
}[page_key]()
