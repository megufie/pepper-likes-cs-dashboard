"""
Read-only loader for the CS-team contract master spreadsheet.

Sheet: 1i1xZeo5Bjdv2yhPtOwbvlsYmg0WazvNFQsrsIbGcVTo
Tab:   CS_契約/請求管理・一言メモ

Headers are in row 2 (row 1 has merged section labels).
Row 3 onwards is data (one row per contract).

Key columns we extract:
  col 1  申込日                  → signup_date
  col 4  会社名                  → company_name
  col 6  取引先ID紐付け用        → user_id (links to DB users.id)
  col 11 ジャンル                → genre
  col 16 一言メモ                → notes
  col 17 接点経過日              → contact_days_ago
  col 18 対応状況                → response_status
  col 19 状況                    → status (公開中/解約済/...)
  col 20 解約日                  → churn_date
  col 22 ヒアリング網羅率        → hearing_coverage
  col 37 掲載開始日              → service_start_date
  col 38 契約獲得者/パートナー   → cs_owner
  col 39 解約状況                → churn_status (解約/継続)
  col 40 期間（ヶ月）            → contract_months
  col 42 申し込みプラン          → plan_name
  col 43 支払い方法              → payment_method
  col 44 NPS送付                 → nps_sent
  col 46-76 月別グリッド (24/05 〜 26/11) → monthly_active_grid (✅ = active that month)
"""
from __future__ import annotations
import os
from typing import Optional

import pandas as pd

CONTRACT_SHEET_ID = "1i1xZeo5Bjdv2yhPtOwbvlsYmg0WazvNFQsrsIbGcVTo"
CONTRACT_SHEET_TAB = "CS_契約/請求管理・一言メモ"

# ローデータシート（個別対策確認タブ）
ROWDATA_SHEET_ID = "1oVksbH61rrW--APuJ06qgSjHgejhohM0_N_FEWpabUw"
INDIVIDUAL_CHECK_TAB = "★個別対策確認"

# 1-indexed column positions
COL = {
    "signup_date":        1,
    "billing_cd":         2,
    "user_id":            6,    # 取引先ID紐付け用 — links to DB users.id
    "company_name":       4,
    "genre":             11,
    "db_company_name":   12,   # L列: DBに登録されている企業名
    "notes":             16,
    "contact_days_ago":  17,
    "response_status":   18,
    "status":            19,
    "churn_date":        20,
    "hearing_coverage":  22,
    "service_start_date": 37,
    "cs_owner":          38,
    "churn_status":      39,
    "contract_months":   40,
    "plan_name":         42,
    "payment_method":    43,
    "nps_sent":          44,
}

# Monthly grid columns (1-indexed). Each is one calendar month.
# (col_index, label)
MONTH_COLUMNS = [
    (46, "2024-05"), (47, "2024-06"), (48, "2024-07"), (49, "2024-08"),
    (50, "2024-09"), (51, "2024-10"), (52, "2024-11"), (53, "2024-12"),
    (54, "2025-01"), (55, "2025-02"), (56, "2025-03"), (57, "2025-04"),
    (58, "2025-05"), (59, "2025-06"), (60, "2025-07"), (61, "2025-08"),
    (62, "2025-09"), (63, "2025-10"), (64, "2025-11"), (65, "2025-12"),
    (66, "2026-01"), (67, "2026-02"), (68, "2026-03"), (69, "2026-04"),
    (70, "2026-05"), (71, "2026-06"), (72, "2026-07"), (73, "2026-08"),
    (74, "2026-09"), (75, "2026-10"), (76, "2026-11"),
]


def _get_credentials_path() -> str:
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), "credentials.json")


def _build_credentials():
    """
    認証情報オブジェクトを返す。
    優先順位:
      1. 環境変数 GOOGLE_CREDENTIALS_JSON（JSON文字列）← Streamlit Cloud
      2. credentials.json ファイル                    ← ローカル開発
    """
    import json
    from google.oauth2.service_account import Credentials as _Creds
    scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

    json_str = os.getenv("GOOGLE_CREDENTIALS_JSON", "")
    if json_str:
        info = json.loads(json_str)
        return _Creds.from_service_account_info(info, scopes=scopes)
    return _Creds.from_service_account_file(_get_credentials_path(), scopes=scopes)


def credentials_available() -> bool:
    """credentials.json ファイルまたは環境変数のどちらかがあれば True。"""
    if os.getenv("GOOGLE_CREDENTIALS_JSON", ""):
        return True
    return os.path.exists(_get_credentials_path())


def fetch_contract_master() -> pd.DataFrame:
    """
    Returns one row per contract with structured columns + a wide monthly grid
    (`m_2024-05`, `m_2024-06`, …) where 1 = active that month, 0 = not.
    """
    import gspread
    from google.oauth2.service_account import Credentials

    creds = _build_credentials()
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(CONTRACT_SHEET_ID)
    ws = sh.worksheet(CONTRACT_SHEET_TAB)

    all_values = ws.get_all_values()
    # Row 1 = section headers, row 2 = column headers, row 3+ = data
    data_rows = all_values[2:]

    rows = []
    for raw in data_rows:
        if len(raw) < 5:
            continue
        # Pad to expected length
        r = raw + [""] * (max(80, len(raw)) - len(raw))

        signup     = (r[COL["signup_date"] - 1] or "").strip()
        company    = (r[COL["company_name"] - 1] or "").strip()
        user_id    = (r[COL["user_id"] - 1] or "").strip()

        # Filter out completely blank rows (no signup date AND no company name)
        if not signup and not company:
            continue

        record = {
            "signup_date":        signup or None,
            "user_id":            user_id or None,
            "company_name":       company or None,
            "billing_cd":         (r[COL["billing_cd"] - 1] or "").strip() or None,
            "genre":              (r[COL["genre"] - 1] or "").strip() or None,
            "db_company_name":    (r[COL["db_company_name"] - 1] or "").strip() or None,
            "notes":              (r[COL["notes"] - 1] or "").strip(),
            "contact_days_ago":   (r[COL["contact_days_ago"] - 1] or "").strip(),
            "response_status":    (r[COL["response_status"] - 1] or "").strip() or None,
            "status":             (r[COL["status"] - 1] or "").strip() or None,
            "churn_date":         (r[COL["churn_date"] - 1] or "").strip() or None,
            "hearing_coverage":   (r[COL["hearing_coverage"] - 1] or "").strip() or None,
            "service_start_date": (r[COL["service_start_date"] - 1] or "").strip() or None,
            "cs_owner":           (r[COL["cs_owner"] - 1] or "").strip() or None,
            "churn_status":       (r[COL["churn_status"] - 1] or "").strip() or None,
            "contract_months":    (r[COL["contract_months"] - 1] or "").strip() or None,
            "plan_name":          (r[COL["plan_name"] - 1] or "").strip() or None,
            "payment_method":     (r[COL["payment_method"] - 1] or "").strip() or None,
            "nps_sent":           (r[COL["nps_sent"] - 1] or "").strip() or None,
        }
        # Monthly grid: presence of any non-empty value (✅ or other) means active
        for col_idx, month_label in MONTH_COLUMNS:
            cell = (r[col_idx - 1] if col_idx - 1 < len(r) else "").strip()
            record[f"m_{month_label}"] = 1 if cell else 0
        rows.append(record)

    if not rows:
        import sys
        print("[sheet_loader] WARNING: contract master sheet returned 0 valid rows", file=sys.stderr)
        return pd.DataFrame()

    df = pd.DataFrame(rows)

    # Type coercions
    df["signup_date"]        = pd.to_datetime(df["signup_date"],        errors="coerce")
    df["churn_date"]         = pd.to_datetime(df["churn_date"],         errors="coerce")
    df["service_start_date"] = pd.to_datetime(df["service_start_date"], errors="coerce")

    # 請求は 掲載開始日 から発生 → これを契約開始日の真のソースとして使用
    df["start_date"] = df["service_start_date"]

    # 解約日が空の場合は今日まで継続している扱い
    today = pd.Timestamp.today().normalize()
    df["effective_end_date"] = df["churn_date"].fillna(today)

    # 課金月数 = 掲載開始日から解約日（or 今日）までのカレンダー月数
    #   解約日の「日」が開始日の「日」以上なら +1（月末まで使っている場合）
    #   例: 3/4開始, 6/3解約 → 3 + (3>=4? No) = 3ヶ月
    #   例: 7/1開始, 9/30解約 → 2 + (30>=1? Yes) = 3ヶ月
    def _calc_billed_months(row):
        start = row["start_date"]
        end = row["effective_end_date"]
        if pd.isna(start) or pd.isna(end) or end < start:
            return None
        months = (end.year - start.year) * 12 + (end.month - start.month)
        if end.day >= start.day:
            months += 1
        return max(1, months)

    df["billed_months"] = df.apply(_calc_billed_months, axis=1)

    # Normalize genre: take only the first line (drop trailing 都市 like "飲食\n東京" → "飲食")
    df["genre"] = df["genre"].apply(
        lambda v: (str(v).split("\n")[0].strip() if v else None)
    )

    df["contract_months"] = pd.to_numeric(df["contract_months"], errors="coerce")

    # Normalize hearing_coverage (e.g. "80%" → 0.8)
    def _parse_pct(v):
        if v is None or v == "":
            return None
        s = str(v).strip().rstrip("%")
        try: return float(s) / 100 if "%" in str(v) else float(s)
        except: return None
    df["hearing_coverage"] = df["hearing_coverage"].apply(_parse_pct)

    # Computed: total active months from grid (legacy, kept for reference)
    month_cols = [f"m_{lbl}" for _, lbl in MONTH_COLUMNS]
    df["total_active_months"] = df[month_cols].sum(axis=1)

    # Computed: is_churned flag — 解約日 set OR status/churn_status contains 解約
    df["is_churned"] = (
        df["churn_date"].notna()
        | df["churn_status"].fillna("").str.contains("解約", regex=False)
        | df["status"].fillna("").str.contains("解約", regex=False)
    ).astype(int)

    return df


# ── 個別対策確認シート（ローデータ）───────────────────────────────────────────

def fetch_individual_check() -> pd.DataFrame:
    """
    ローデータ「★個別対策確認」タブを読み込む。

    抽出する主な列：
      col1  ID
      col2  案件名 (project_title)
      col3  企業アカウント名 (account_name)
      col4  契約企業名 (contract_company)
      col5  作成日 (created_at)
      col6  解約日 (churn_date)
      col7  ステータス1 (status1: 募集中/応募不可/審査中)
      col8  ステータス2 (status2: 公開中/解約済/解約連絡あり/空白 etc.)
      col9  募集作成日
      col10 地域
      col11 対応可否
      col12 応募数 (apps_count)
      col14 前月応募数 (prev_apps_count)
      col15 要対応 (action_required: 要対応/OK)
      col16 連続要対応カウント
    """
    import gspread
    from google.oauth2.service_account import Credentials

    creds = _build_credentials()
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(ROWDATA_SHEET_ID)
    ws = sh.worksheet(INDIVIDUAL_CHECK_TAB)
    all_values = ws.get_all_values()

    rows = []
    # 1行目=ヘッダ, 2行目=説明, 3行目以降=データ
    for raw in all_values[2:]:
        if len(raw) < 13:
            continue
        if not raw[1].strip():
            continue  # blank row
        r = raw + [""] * (max(20, len(raw)) - len(raw))

        def _int(v):
            try: return int(str(v).strip()) if str(v).strip() else None
            except: return None

        rows.append({
            "id":               r[0].strip(),
            "project_title":    r[1].strip(),
            "account_name":     r[2].strip(),
            "contract_company": r[3].strip(),
            "created_at":       r[4].strip(),
            "churn_date":       r[5].strip(),
            "status1":          r[6].strip(),  # G列
            "status2":          r[7].strip(),  # H列
            "post_create_date": r[8].strip(),
            "region":           r[9].strip(),
            "action_status":    r[10].strip(),
            "apps_count":       _int(r[11]),   # L列
            "prev_apps_count":  _int(r[13]) if len(r) > 13 else None,
            "action_required":  r[14].strip() if len(r) > 14 else "",
            "consecutive_alert": r[15].strip() if len(r) > 15 else "",
        })

    df = pd.DataFrame(rows)
    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
    df["churn_date"] = pd.to_datetime(df["churn_date"], errors="coerce")
    return df


# ── 未回収債権シート ──────────────────────────────────────────────────────────

UNCOLLECTED_SHEET_GID = 1479892012  # CS_未回収債権_Likes tab


def fetch_uncollected_debts() -> pd.DataFrame:
    """
    CS_未回収債権_Likes タブから未回収行を読み込む。
    B列「入金確認済」が TRUE でない行（空白など）を対象とする。

    返却列:
      no, company, invoice_amount, remaining,
      due_date, payment_scheduled, confirmed_type,
      invoice_no, contact_date, status
    """
    import gspread
    from google.oauth2.service_account import Credentials

    creds = _build_credentials()
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(CONTRACT_SHEET_ID)
    ws = sh.get_worksheet_by_id(UNCOLLECTED_SHEET_GID)
    all_values = ws.get_all_values()

    def _parse_amount(v):
        try:
            return int(str(v).replace(",", "").replace("¥", "").replace(" ", "").strip()) if str(v).strip() else 0
        except Exception:
            return 0

    rows = []
    # Row 1=description, Row 2=headers, Row 3+=data
    for raw in all_values[2:]:
        if len(raw) < 10:
            continue
        no = raw[0].strip()
        confirmed = raw[1].strip()   # B: 入金確認済
        in_review = raw[2].strip()   # C: 確認中
        on_hold = raw[3].strip()     # D: 保留
        company = raw[9].strip()     # J: 取引先

        if not no and not company:
            continue
        if confirmed == "TRUE":
            continue  # 入金確認済 → スキップ

        rows.append({
            "no":                no or None,
            "confirmed_type":    "確認中" if in_review == "TRUE" else ("保留" if on_hold == "TRUE" else "未回収"),
            "company":           company or None,
            "due_date":          (raw[8].strip() or None),   # I: 決済期日
            "invoice_amount":    _parse_amount(raw[10]) if len(raw) > 10 else 0,   # K: 取引金額
            "remaining":         _parse_amount(raw[11]) if len(raw) > 11 else 0,   # L: 決済残額
            "payment_scheduled": (raw[12].strip() or None) if len(raw) > 12 else None,  # M: 支払予定日
            "invoice_no":        (raw[15].strip() or None) if len(raw) > 15 else None,  # P: 請求書番号
            "contact_date":      (raw[16].strip() or None) if len(raw) > 16 else None,  # Q: 入金依頼連絡日
            "status":            (raw[18].strip() or None) if len(raw) > 18 else None,  # S: 連絡ステータス
        })

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df["due_date"]          = pd.to_datetime(df["due_date"],          errors="coerce")
    df["payment_scheduled"] = pd.to_datetime(df["payment_scheduled"], errors="coerce")
    df["contact_date"]      = pd.to_datetime(df["contact_date"],      errors="coerce")
    return df


# ── 採用・投稿数シート ─────────────────────────────────────────────────────────

ADOPTION_TAB = "採用・投稿数"

# Columns (1-indexed):
#   1: 登録アカウント名
#   2: 契約企業名
#   3-16: per-month pairs (採用, 投稿) for 25/11 〜 26/05 (7 months × 2 = 14 cols)
ADOPTION_MONTHS = [
    "2025-11", "2025-12", "2026-01", "2026-02",
    "2026-03", "2026-04", "2026-05",
]


APP_COUNTS_TAB_GID = 1887096175


def fetch_app_counts_sheet() -> pd.DataFrame:
    """
    応募者数タブ（gid=1887096175）を読み込む。
    1案件あたり1行。返却カラム:
      posting_id, posting_name, company_account, company_name,
      posting_date, region, app_count
    """
    import gspread
    from google.oauth2.service_account import Credentials

    creds = _build_credentials()
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(CONTRACT_SHEET_ID)
    ws = sh.get_worksheet_by_id(APP_COUNTS_TAB_GID)
    all_values = ws.get_all_values()

    rows = []
    # Row 0 = header labels, Row 1 = field-type row, Row 2+ = data
    for raw in all_values[2:]:
        if len(raw) < 12:
            continue
        posting_id = raw[0].strip()
        # Skip blank/junk rows
        if not posting_id or posting_id in ("table", "table (2)"):
            continue

        # Parse 募集作成日 (col 8): MM/DD/YYYY
        raw_date = raw[8].strip() if len(raw) > 8 else ""
        posting_date = None
        if raw_date:
            try:
                from datetime import datetime
                posting_date = datetime.strptime(raw_date, "%m/%d/%Y").date().strftime("%Y-%m-%d")
            except ValueError:
                try:
                    posting_date = datetime.strptime(raw_date, "%Y/%m/%d").date().strftime("%Y-%m-%d")
                except ValueError:
                    pass

        try:
            app_count = int(raw[11].strip()) if len(raw) > 11 and raw[11].strip() else 0
        except (ValueError, IndexError):
            app_count = 0

        try:
            prev_app_count = int(raw[13].strip()) if len(raw) > 13 and raw[13].strip() else 0
        except (ValueError, IndexError):
            prev_app_count = 0

        status1 = raw[6].strip() if len(raw) > 6 else ""
        status2 = raw[7].strip() if len(raw) > 7 else ""

        rows.append({
            "posting_id":      posting_id,
            "posting_name":    raw[1].strip() if len(raw) > 1 else None,
            "company_account": raw[2].strip() if len(raw) > 2 else None,
            "company_name":    raw[3].strip() if len(raw) > 3 else None,
            "posting_date":    posting_date,
            "region":          (raw[9].strip() if len(raw) > 9 else None) or None,
            "status1":         status1,
            "status2":         status2,
            "app_count":       app_count,
            "prev_app_count":  prev_app_count,
        })

    return pd.DataFrame(rows)


def fetch_adoption_counts() -> pd.DataFrame:
    """
    採用・投稿数 タブを読み込む。
    1社あたり 1行で、月ごとの 採用 と 投稿 のカウントを保持する。
    """
    import gspread
    from google.oauth2.service_account import Credentials

    creds = _build_credentials()
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(ROWDATA_SHEET_ID)
    ws = sh.worksheet(ADOPTION_TAB)
    all_values = ws.get_all_values()

    rows = []
    # Row 1 = totals, row 2 = 採用/投稿 labels, row 3 = headers, row 4+ = data
    for raw in all_values[3:]:
        if len(raw) < 3:
            continue
        account  = raw[0].strip() if len(raw) > 0 else ""
        contract = raw[1].strip() if len(raw) > 1 else ""
        # Skip junk rows (no name in either column, or header repeats)
        if not account and not contract:
            continue
        if account in ("登録アカウント名", "table (3)"):
            continue

        rec = {
            "account_name":     account or None,
            "contract_company": contract or None,
            "display_name":     contract if contract else account,
        }
        # Each month: 2 columns (採用, 投稿)
        for idx, m in enumerate(ADOPTION_MONTHS):
            hire_col = 2 + idx * 2     # 0-indexed
            post_col = 3 + idx * 2
            try: rec[f"hire_{m}"] = int(raw[hire_col].strip()) if hire_col < len(raw) and raw[hire_col].strip() else 0
            except: rec[f"hire_{m}"] = 0
            try: rec[f"post_{m}"] = int(raw[post_col].strip()) if post_col < len(raw) and raw[post_col].strip() else 0
            except: rec[f"post_{m}"] = 0
        rows.append(rec)

    return pd.DataFrame(rows)


# ── 解約詳細シート（gid=363386561）──────────────────────────────────────────────

CHURN_DETAIL_GID = 363386561  # 解約詳細タブ（2025/12以降）

def fetch_churn_detail() -> pd.DataFrame:
    """
    解約詳細タブ（gid=363386561）を読み込む。2025年12月以降のデータを対象。

    列構成:
      A: 企業名          → company_name
      B: 掲載開始日      → start_date
      C: 解約日          → churn_date
      D: 利用月数        → billed_months
      E: 契約プラン      → plan_name
      F: 解約理由①      → reason1
      G: 解約理由②      → reason2
      H: 解約理由③      → reason3
      I: センチメント    → sentiment
      J: 解約理由詳細    → reason_detail
    """
    import gspread
    from google.oauth2.service_account import Credentials

    creds = _build_credentials()
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(CONTRACT_SHEET_ID)
    ws = sh.get_worksheet_by_id(CHURN_DETAIL_GID)
    all_values = ws.get_all_values()

    rows = []
    for raw in all_values[1:]:  # 1行目はヘッダー
        if not raw or not any(v.strip() for v in raw[:3]):
            continue
        r = raw + [""] * max(0, 10 - len(raw))
        churn_date = r[2].strip()
        # 2025/12以降のみ対象
        if not churn_date or churn_date < "2025/12":
            continue
        rows.append({
            "company_name":  r[0].strip() or None,
            "start_date":    r[1].strip() or None,
            "churn_date":    churn_date,
            "billed_months": r[3].strip() or None,
            "plan_name":     r[4].strip() or None,
            "reason1":       r[5].strip() or None,
            "reason2":       r[6].strip() or None,
            "reason3":       r[7].strip() or None,
            "sentiment":     r[8].strip() or None,
            "reason_detail": r[9].strip() or None,
        })

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["churn_date"]    = pd.to_datetime(df["churn_date"],  errors="coerce")
    df["start_date"]    = pd.to_datetime(df["start_date"],  errors="coerce")
    df["billed_months"] = pd.to_numeric(df["billed_months"], errors="coerce")
    df["churn_ym"]      = df["churn_date"].dt.to_period("M").astype(str)
    return df


# ── タイムライン用ソースシート（gid=0）────────────────────────────────────────
# E列（index 4）= 取引先名 を company_name として使用。
# 同名企業が複数行 → 再開契約としてタイムラインで検出する。
# 日付系列は2行目（ヘッダー行）のキーワードで列位置を自動検出する。

TIMELINE_TAB_GID = 0   # gid=0 = スプレッドシートの最初のタブ

# ヘッダー行で検索するキーワード → フィールド名
_TL_HEADER_KEYWORDS: dict[str, list[str]] = {
    "start_date":       ["掲載開始日", "開始日", "service_start", "start"],
    "churn_date":       ["解約日", "churn_date", "解約"],
    "contract_months":  ["期間（ヶ月", "契約期間", "最低契約", "contract_months"],
    "status":           ["状況", "ステータス", "status"],
    "churn_status":     ["解約状況", "churn_status"],
}

# E列（0-indexed: 4）= 取引先名
_TL_COMPANY_COL = 4


def fetch_timeline_source() -> pd.DataFrame:
    """
    gid=0 タブを読み込み、タイムライン用の契約一覧を返す。

    必須カラム: company_name, start_date, churn_date, is_churned, contract_months
    E列（0-indexed 4）を取引先名として使用。
    日付列はヘッダー行のキーワードで自動検出。
    """
    import gspread
    from google.oauth2.service_account import Credentials

    creds = _build_credentials()
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(CONTRACT_SHEET_ID)
    ws = sh.get_worksheet_by_id(TIMELINE_TAB_GID)
    all_values = ws.get_all_values()

    if len(all_values) < 2:
        import sys
        print("[sheet_loader/timeline] WARNING: gid=0 が空です", file=sys.stderr)
        return pd.DataFrame()

    # ── ヘッダー行を探す（最初の5行内でキーワードが1つ以上ヒットした行）
    header_row_idx = None
    for i, row in enumerate(all_values[:6]):
        joined = " ".join(row)
        hits = sum(
            1 for kws in _TL_HEADER_KEYWORDS.values()
            for kw in kws if kw in joined
        )
        if hits >= 2:
            header_row_idx = i
            break

    if header_row_idx is None:
        # ヘッダーが見つからない場合は2行目（index 1）をヘッダーとみなす
        header_row_idx = 1

    headers = [str(h).strip() for h in all_values[header_row_idx]]
    data_rows = all_values[header_row_idx + 1 :]

    # ── 列位置を自動検出
    col_map: dict[str, int | None] = {k: None for k in _TL_HEADER_KEYWORDS}
    for field, kws in _TL_HEADER_KEYWORDS.items():
        for ci, h in enumerate(headers):
            if any(kw in h for kw in kws):
                col_map[field] = ci
                break

    def _get(r: list[str], ci: int | None) -> str:
        if ci is None or ci >= len(r):
            return ""
        return r[ci].strip()

    rows = []
    for raw in data_rows:
        if len(raw) <= _TL_COMPANY_COL:
            continue
        company = raw[_TL_COMPANY_COL].strip()
        if not company:
            continue

        start_raw   = _get(raw, col_map["start_date"])
        churn_raw   = _get(raw, col_map["churn_date"])
        cm_raw      = _get(raw, col_map["contract_months"])
        status_raw  = _get(raw, col_map["status"])
        cs_raw      = _get(raw, col_map["churn_status"])

        rows.append({
            "company_name":    company,
            "start_date":      start_raw  or None,
            "churn_date":      churn_raw  or None,
            "contract_months": cm_raw     or None,
            "status":          status_raw or None,
            "churn_status":    cs_raw     or None,
        })

    if not rows:
        import sys
        print("[sheet_loader/timeline] WARNING: gid=0 のデータ行が0件です", file=sys.stderr)
        return pd.DataFrame()

    df = pd.DataFrame(rows)

    # 型変換
    df["start_date"]      = pd.to_datetime(df["start_date"],      errors="coerce")
    df["churn_date"]      = pd.to_datetime(df["churn_date"],       errors="coerce")
    df["contract_months"] = pd.to_numeric(df["contract_months"],   errors="coerce")

    today = pd.Timestamp.today().normalize()
    df["effective_end_date"] = df["churn_date"].fillna(today)

    # 課金月数（掲載開始日 → 解約日 or 今日）
    def _billed(row):
        s, e = row["start_date"], row["effective_end_date"]
        if pd.isna(s) or pd.isna(e) or e < s:
            return None
        months = (e.year - s.year) * 12 + (e.month - s.month)
        if e.day >= s.day:
            months += 1
        return max(1, months)

    df["billed_months"] = df.apply(_billed, axis=1)

    # is_churned: 解約日あり OR status/churn_status に「解約」含む
    df["is_churned"] = (
        df["churn_date"].notna()
        | df["churn_status"].fillna("").str.contains("解約", regex=False)
        | df["status"].fillna("").str.contains("解約", regex=False)
    ).astype(int)

    # start_date がない行は除外
    df = df[df["start_date"].notna()].reset_index(drop=True)
    return df


# ── 契約ステータス集計（D列）───────────────────────────────────────────────────

CONTRACT_STATUS_GID = 1840131021  # 契約ステータスタブ

def fetch_contract_status_counts() -> dict:
    """
    gid=1840131021 タブのD列から契約ステータスを集計して返す。
    D列の値: 契約済み / 解約済み / 解約申し出あり

    返却:
      {
        "累計":        int,  # 全行数（契約済み + 解約済み + 解約申し出あり）
        "契約済み":    int,
        "解約済み":    int,
        "解約申し出あり": int,
      }
    """
    import gspread
    from google.oauth2.service_account import Credentials

    creds = _build_credentials()
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(CONTRACT_SHEET_ID)
    ws = sh.get_worksheet_by_id(CONTRACT_STATUS_GID)
    all_values = ws.get_all_values()

    # 1行目はヘッダーとして除外、D列 = index 3（0-based）
    counts = {"01.契約済み": 0, "03.解約済み": 0, "04.解約申し出あり": 0}
    for row in all_values[1:]:
        if len(row) < 4:
            continue
        val = row[3].strip()
        if val in counts:
            counts[val] += 1

    total = sum(counts.values())
    return {
        "累計":            total,
        "契約済み":        counts["01.契約済み"],
        "解約済み":        counts["03.解約済み"],
        "解約申し出あり":  counts["04.解約申し出あり"],
    }
