"""
Output writers — push scored items to Notion DB and write the radar.md file.

Two destinations:
1. Notion database (filterable, structured, primary review surface)
2. radar.md (lightweight, version-controlled, easy to grep)
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import requests

log = logging.getLogger(__name__)

NOTION_API_VERSION = "2022-06-28"
NOTION_API_BASE = "https://api.notion.com/v1"


# ─── NOTION ──────────────────────────────────────────────────────────────────


def _notion_headers() -> dict:
    token = os.environ.get("NOTION_TOKEN")
    if not token:
        raise RuntimeError("NOTION_TOKEN not set in environment")
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_API_VERSION,
        "Content-Type": "application/json",
    }


def _safe_text(value: str | None, limit: int = 1900) -> list[dict]:
    """Build a rich_text array safely. Empty strings allowed."""
    s = (value or "").strip()[:limit]
    if not s:
        return []
    return [{"type": "text", "text": {"content": s}}]


def _safe_select(value: str | None) -> dict | None:
    """Build a select property safely. None if value is empty/missing."""
    s = (value or "").strip()
    return {"name": s} if s else None


def _build_notion_page(item: dict, database_id: str) -> dict:
    """Build the JSON payload for a single Notion page (database row)."""
    today_iso = datetime.now(timezone.utc).date().isoformat()

    properties: dict = {
        "Title": {
            "title": [{"type": "text", "text": {"content": item["title"][:200]}}]
        },
        "Score": {"number": item["score"]},
        "Date Added": {"date": {"start": today_iso}},
        "Reviewed": {"checkbox": False},
        "Summary": {"rich_text": _safe_text(item.get("claude_summary"))},
        "Why It Matters": {"rich_text": _safe_text(item.get("why_it_matters"))},
    }

    # Select fields — only include if we have a value
    if (sel := _safe_select(item.get("tier"))):
        properties["Tier"] = {"select": sel}
    if (sel := _safe_select(item.get("category"))):
        properties["Category"] = {"select": sel}
    if (sel := _safe_select(item.get("source"))):
        properties["Source"] = {"select": sel}
    properties["Decision"] = {"select": {"name": "⏳ Unreviewed"}}

    # Multi-select for Project Match
    pm = item.get("project_match") or []
    if pm:
        properties["Project Match"] = {
            "multi_select": [{"name": p} for p in pm if p]
        }

    # URL — only include if non-empty (Notion rejects empty string URLs)
    url = (item.get("url") or "").strip()
    if url:
        properties["URL"] = {"url": url}

    return {
        "parent": {"database_id": database_id},
        "properties": properties,
    }


def push_to_notion(items: list[dict]) -> int:
    """Push every item to the Notion database. Returns count successfully written."""
    database_id = os.environ.get("NOTION_DATABASE_ID")
    if not database_id:
        raise RuntimeError("NOTION_DATABASE_ID not set in environment")

    headers = _notion_headers()
    success = 0
    failure_count = 0

    log.info(f"Notion: starting writes for {len(items)} items "
             f"to DB {database_id[:8]}…")

    for i, item in enumerate(items, start=1):
        payload = _build_notion_page(item, database_id)
        try:
            resp = requests.post(
                f"{NOTION_API_BASE}/pages",
                headers=headers,
                json=payload,
                timeout=20,
            )
            if resp.status_code == 200:
                success += 1
            else:
                failure_count += 1
                log.error(
                    f"[{i}/{len(items)}] Notion FAILED ({resp.status_code}) "
                    f"for '{item['title'][:60]}': {resp.text[:500]}"
                )
                # Log the full payload of the FIRST failure so we can debug
                if failure_count == 1:
                    log.error(f"FIRST FAILURE PAYLOAD:\n{json.dumps(payload, indent=2)[:2500]}")
        except Exception as e:
            failure_count += 1
            log.error(
                f"[{i}/{len(items)}] Notion EXCEPTION for "
                f"'{item['title'][:60]}': {type(e).__name__}: {e}"
            )

    log.info(f"Notion: {success}/{len(items)} written, {failure_count} failed")
    return success


# ─── RADAR.MD ────────────────────────────────────────────────────────────────


def _md_section(title: str, items: list[dict]) -> str:
    """Render one tier section of radar.md."""
    if not items:
        return f"### {title}\n\n_No items in this tier._\n\n"

    out = [f"### {title}\n"]
    for it in items:
        projects = ", ".join(it.get("project_match", [])) or "—"
        out.append(
            f"- **[{it['title']}]({it['url']})** "
            f"`{it['score']}` · {it['source']} · {projects}  \n"
            f"  {it.get('claude_summary', '')}  \n"
            f"  _Why it matters:_ {it.get('why_it_matters', '')}\n"
        )
    return "\n".join(out) + "\n"


def write_radar_md(items: list[dict], output_path: Path) -> None:
    """Write the human-readable radar.md digest."""
    now = datetime.now(timezone.utc)
    act_now = [i for i in items if i["tier"] == "🔥 Act Now"]
    watch = [i for i in items if i["tier"] == "👀 Watch"]
    archive = [i for i in items if i["tier"] == "📦 Archive"]

    content = f"""# 📡 NoZak Labs — AI Radar

> _Last updated: {now.strftime("%Y-%m-%d %H:%M UTC")}_
> _Total items this run: {len(items)} \
({len(act_now)} act now, {len(watch)} watch, {len(archive)} archive)_

Review during your Mon 8:00 PM + Fri 8:00 PM Cairo slots. \
Full filtering and decision tracking happens in [Notion](https://www.notion.so/).

---

## 🔥 Act Now ({len(act_now)})

_High-relevance items — evaluate during your radar slot._

{_md_section("", act_now)}

---

## 👀 Watch ({len(watch)})

_Tangential relevance — skim if time permits._

{_md_section("", watch)}

---

## 📦 Archive ({len(archive)})

_Low-relevance — kept for searchability only._

{_md_section("", archive)}

---

_Generated by the [AI Radar Agent](https://github.com/nozaklabs/ai-radar-agent)._
"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    log.info(f"Wrote radar.md ({len(items)} items) to {output_path}")
