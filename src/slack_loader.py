"""
Read-only loader for the Slack #likes_解約報告 channel.

Fetches recent messages and parses them to extract:
  - posted_at (datetime)
  - reporter (Slack username)
  - company_name (parsed from "■ 企業名" line)
  - subsidiary_name (the optional "（...）" part)
  - reason (parsed from "■ (解約の主な)理由：" line)
  - raw_text (full message)
  - permalink (jump link to Slack)

Caches list of users (id → real_name) to avoid per-message lookups.
"""
from __future__ import annotations
import os
import re
from datetime import datetime
from typing import Optional

import pandas as pd

# Regex patterns for the structured churn report format
# Example match for company:
#   ■株式会社CS-C（株式会社うる虎ダイニング）
#   ■合同会社TERRAS
#   ■ 株式会社MENSHO
RE_COMPANY = re.compile(
    r"^\s*[■◼︎▪︎]\s*"           # bullet (variants)
    r"(?!理由|解約の|満足|改善|金額|支払|サービス|対応|料金)"  # not a different field
    r"(?:解約)?"                 # sometimes prefixed with 解約
    r"\s*"
    r"(?P<name>[^（()]+?)"       # company name (no parens)
    r"(?:[（(](?P<sub>[^）)]+)[)）])?"  # optional subsidiary
    r"\s*$",
    re.MULTILINE,
)

# Reason can be:
#   ■ 解約の主な理由：xxx
#   ■理由：xxx
#   ■ 解約理由 : xxx
RE_REASON = re.compile(
    r"^\s*[■◼︎▪︎]\s*"
    r"(?:解約の主な|解約)?\s*理由"
    r"\s*[：:]\s*"
    r"(?P<reason>.+?)\s*$",
    re.MULTILINE,
)

# Skip prefixes/patterns
SKIP_LINES = (
    "解約希望がございますので",
    "解約希望がございましたので",
    "ご報告いたします",
    "以下、",
)


def credentials_available() -> bool:
    return bool(os.getenv("SLACK_BOT_TOKEN") and os.getenv("SLACK_CHURN_CHANNEL_ID"))


def _strip_mentions(text: str) -> str:
    """Remove leading <@U...> and cc lines."""
    lines = text.split("\n")
    out = []
    skip_mention_block = True
    for line in lines:
        s = line.strip()
        if not s:
            if not skip_mention_block:
                out.append("")
            continue
        # Skip pure-mention lines and cc-mention lines
        if skip_mention_block:
            stripped = re.sub(r"<@[A-Z0-9]+>", "", s).strip()
            stripped = re.sub(r"^[ｃcCＣ㏄]+\s*", "", stripped).strip()
            if not stripped or stripped.lower().startswith("cc"):
                continue
            skip_mention_block = False
        out.append(line)
    return "\n".join(out)


def _parse_message(text: str) -> dict:
    """Extract company_name + reason from a raw Slack message text."""
    cleaned = _strip_mentions(text)

    company_name = None
    subsidiary = None
    reason = None

    # Find company: first ■ line that is NOT a reason/satisfaction/improvement field
    for m in RE_COMPANY.finditer(cleaned):
        nm = m.group("name").strip()
        # Reject if it looks like a field label (e.g. starts with 解約 + 主な)
        if any(kw in nm for kw in ("理由", "満足", "改善", "金額", "支払", "対応", "料金", "サービス")):
            continue
        if not nm:
            continue
        company_name = nm
        subsidiary = (m.group("sub") or "").strip() or None
        break

    # Find reason: first ■理由 line
    rm = RE_REASON.search(cleaned)
    if rm:
        reason = rm.group("reason").strip()

    return {
        "company_name": company_name,
        "subsidiary":   subsidiary,
        "reason":       reason,
    }


def fetch_churn_reports(limit: int = 200) -> pd.DataFrame:
    """
    Returns one row per message in #likes_解約報告 with parsed company/reason.
    """
    from slack_sdk import WebClient
    from slack_sdk.errors import SlackApiError

    token = os.getenv("SLACK_BOT_TOKEN")
    channel = os.getenv("SLACK_CHURN_CHANNEL_ID")
    if not token or not channel:
        return pd.DataFrame()

    client = WebClient(token=token)

    # Fetch messages (paginate up to `limit`)
    messages = []
    cursor = None
    fetched = 0
    while fetched < limit:
        try:
            resp = client.conversations_history(
                channel=channel,
                limit=min(100, limit - fetched),
                cursor=cursor,
            )
        except SlackApiError as e:
            raise RuntimeError(f"Slack API error: {e.response.get('error')}")
        messages.extend(resp.get("messages", []))
        fetched = len(messages)
        cursor = resp.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break

    # Resolve user IDs → real names (cache one bulk call)
    user_ids = {m.get("user") for m in messages if m.get("user")}
    user_map = {}
    for uid in user_ids:
        try:
            u = client.users_info(user=uid)
            profile = u["user"].get("profile", {})
            user_map[uid] = (profile.get("real_name_normalized")
                             or profile.get("display_name")
                             or u["user"].get("name", uid))
        except SlackApiError:
            user_map[uid] = uid

    rows = []
    for m in messages:
        if m.get("subtype") in ("channel_join", "channel_leave",
                                 "channel_topic", "channel_purpose"):
            continue
        text = m.get("text", "")
        if not text or len(text) < 20:
            continue

        ts = m.get("ts", "")
        try:
            posted_at = datetime.fromtimestamp(float(ts))
        except Exception:
            posted_at = None

        parsed = _parse_message(text)
        # Only keep messages that successfully parsed a company name
        # OR that mention "解約希望" anywhere (so we don't lose unparseable reports)
        if not parsed["company_name"] and "解約" not in text:
            continue

        rows.append({
            "ts":             ts,
            "posted_at":      posted_at,
            "reporter":       user_map.get(m.get("user"), m.get("user")),
            "company_name":   parsed["company_name"],
            "subsidiary":     parsed["subsidiary"],
            "reason":         parsed["reason"] or "未分類",
            "raw_text":       text,
        })

    return pd.DataFrame(rows)
