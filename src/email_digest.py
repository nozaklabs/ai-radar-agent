"""
Send the weekly radar digest via Gmail SMTP.

Public API:
    send_email_digest(items: list[dict]) -> bool
"""

from __future__ import annotations

import hashlib
import logging
import os
import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from urllib.parse import quote

log = logging.getLogger(__name__)

GITHUB_REPO_URL = "https://github.com/NohaZak/ai-radar-agent"


# ─── HELPERS ─────────────────────────────────────────────────────────────────


def _item_id(url: str) -> str:
    return hashlib.sha1(url.encode()).hexdigest()[:8]


def _week_label() -> str:
    """Return 'DD Mmm' for the Sunday of the current run."""
    now = datetime.now(timezone.utc)
    return now.strftime("%-d %b") if hasattr(now, "strftime") else now.strftime("%d %b").lstrip("0")


def _mailto_buttons_html(item_id: str, title: str, url: str, score: int, gmail_user: str) -> str:
    body = quote(f"Item: {title}\nURL: {url}\nScore: {score}")
    subj_adopt    = quote(f"Radar Adopt: {item_id}")
    subj_evaluate = quote(f"Radar Evaluate: {item_id}")
    subj_skip     = quote(f"Radar Skip: {item_id}")
    base = f"mailto:{gmail_user}"
    btn_style = "padding:8px 14px;border-radius:4px;color:white;text-decoration:none;margin-right:8px;font-size:13px;font-weight:500;display:inline-block;"
    return (
        f'<div style="margin-top:10px;">'
        f'<a href="{base}?subject={subj_adopt}&body={body}" style="{btn_style}background:#16a34a;">Adopt</a>'
        f'<a href="{base}?subject={subj_evaluate}&body={body}" style="{btn_style}background:#d97706;">Evaluate</a>'
        f'<a href="{base}?subject={subj_skip}&body={body}" style="{btn_style}background:#6b7280;">Skip</a>'
        f'</div>'
    )


def _mailto_buttons_text(item_id: str, title: str, url: str, score: int, gmail_user: str) -> str:
    body = quote(f"Item: {title}\nURL: {url}\nScore: {score}")
    subj_adopt    = quote(f"Radar Adopt: {item_id}")
    subj_evaluate = quote(f"Radar Evaluate: {item_id}")
    subj_skip     = quote(f"Radar Skip: {item_id}")
    base = f"mailto:{gmail_user}"
    return (
        f"  [Adopt]    {base}?subject={subj_adopt}&body={body}\n"
        f"  [Evaluate] {base}?subject={subj_evaluate}&body={body}\n"
        f"  [Skip]     {base}?subject={subj_skip}&body={body}"
    )


# ─── HTML BUILDER ─────────────────────────────────────────────────────────────


def _build_html(items: list[dict], gmail_user: str) -> str:
    act_now = [i for i in items if i["tier"] == "🔥 Act Now"]
    watch   = [i for i in items if i["tier"] == "👀 Watch"]

    top_score     = max((i["score"] for i in items), default=0)
    project_count = sum(1 for i in items if i.get("project_match"))

    hero = (
        f'<div style="background:#f3f4f6;padding:16px;border-radius:8px;margin-bottom:24px;">'
        f'<p style="margin:0;font-size:14px;color:#374151;">'
        f'<strong>{len(items)}</strong> items scored &nbsp;·&nbsp; '
        f'top score <strong>{top_score}</strong> &nbsp;·&nbsp; '
        f'<strong>{project_count}</strong> with project matches'
        f'</p></div>'
    )

    act_now_html = ""
    if act_now:
        act_now_html = '<h2 style="font-size:18px;margin-bottom:16px;">🔥 Act Now</h2>'
        for item in act_now:
            iid      = _item_id(item["url"])
            title    = item["title"]
            url      = item["url"]
            score    = item["score"]
            source   = item.get("source", "")
            projects = ", ".join(item.get("project_match", [])) or "—"
            why      = item.get("why_it_matters", "")
            buttons  = _mailto_buttons_html(iid, title, url, score, gmail_user)
            act_now_html += (
                f'<div style="border-bottom:1px solid #e5e7eb;padding-bottom:16px;margin-bottom:16px;">'
                f'<a href="{url}" style="color:#111;font-weight:600;font-size:16px;text-decoration:none;">{title}</a>'
                f'&nbsp;<span style="background:#dc2626;color:white;padding:2px 8px;border-radius:4px;font-size:12px;">{score}</span>'
                f'<p style="color:#6b7280;font-size:13px;margin:4px 0;">{source} · {projects}</p>'
                f'<p style="color:#374151;font-size:14px;line-height:1.5;margin:8px 0;">{why}</p>'
                f'{buttons}'
                f'</div>'
            )

    watch_html = ""
    if watch:
        watch_html = '<h2 style="font-size:18px;margin-bottom:16px;">👀 Watch</h2>'
        for item in watch:
            title = item["title"]
            url   = item["url"]
            score = item["score"]
            watch_html += (
                f'<div style="margin-bottom:10px;">'
                f'<a href="{url}" style="color:#111;font-weight:600;font-size:14px;text-decoration:none;">{title}</a>'
                f'&nbsp;<span style="background:#dc2626;color:white;padding:2px 8px;border-radius:4px;font-size:12px;">{score}</span>'
                f'</div>'
            )

    archive_link = (
        f'<p style="font-size:13px;color:#374151;">📦 <strong>Archive link (incl. archive tier):</strong> '
        f'<a href="{GITHUB_REPO_URL}/blob/main/radar.md">{GITHUB_REPO_URL}/blob/main/radar.md</a></p>'
    )

    footer = (
        '<p style="color:#9ca3af;font-size:12px;text-align:center;margin-top:32px;">'
        'Sent weekly · Sunday 11am Cairo · Reply STOP to disable<br>'
        'NoZak Labs · ai-radar-agent'
        '</p>'
    )

    return (
        '<div style="max-width:600px;margin:0 auto;font-family:-apple-system,BlinkMacSystemFont,\'Segoe UI\',Roboto,sans-serif;color:#111;">'
        + hero
        + act_now_html
        + watch_html
        + archive_link
        + footer
        + '</div>'
    )


# ─── PLAIN TEXT BUILDER ───────────────────────────────────────────────────────


def _build_text(items: list[dict], gmail_user: str) -> str:
    act_now = [i for i in items if i["tier"] == "🔥 Act Now"]
    watch   = [i for i in items if i["tier"] == "👀 Watch"]

    top_score     = max((i["score"] for i in items), default=0)
    project_count = sum(1 for i in items if i.get("project_match"))

    lines: list[str] = [
        "=" * 60,
        f"{len(items)} items scored | top score {top_score} | {project_count} with project matches",
        "=" * 60,
        "",
    ]

    if act_now:
        lines.append("🔥 ACT NOW")
        lines.append("-" * 40)
        for item in act_now:
            iid      = _item_id(item["url"])
            title    = item["title"]
            url      = item["url"]
            score    = item["score"]
            source   = item.get("source", "")
            projects = ", ".join(item.get("project_match", [])) or "—"
            why      = item.get("why_it_matters", "")
            lines += [
                f"{title} [{score}]",
                f"  {url}",
                f"  {source} · {projects}",
                f"  Why it matters: {why}",
                _mailto_buttons_text(iid, title, url, score, gmail_user),
                "",
            ]

    if watch:
        lines.append("👀 WATCH")
        lines.append("-" * 40)
        for item in watch:
            lines.append(f"{item['title']} [{item['score']}]  {item['url']}")
        lines.append("")

    lines += [
        "📦 Full archive (incl. archive tier):",
        f"  {GITHUB_REPO_URL}/blob/main/radar.md",
        "",
        "Sent weekly · Sunday 11am Cairo · Reply STOP to disable",
        "NoZak Labs · ai-radar-agent",
    ]

    return "\n".join(lines)


# ─── SUBJECT ─────────────────────────────────────────────────────────────────


def _build_subject(items: list[dict]) -> str:
    act_now_count = sum(1 for i in items if i["tier"] == "🔥 Act Now")
    watch_count   = sum(1 for i in items if i["tier"] == "👀 Watch")
    # strftime %d gives zero-padded day; strip the leading zero manually
    now = datetime.now(timezone.utc)
    day = str(now.day)
    month = now.strftime("%b")
    return f"🛰️ Radar — Week of {day} {month} ({act_now_count} Act Now, {watch_count} Watch)"


# ─── PUBLIC API ───────────────────────────────────────────────────────────────


def send_email_digest(items: list[dict]) -> bool:
    """Build and send the weekly radar digest. Returns True on success."""
    gmail_user = os.environ.get("GMAIL_USER")
    gmail_pw   = os.environ.get("GMAIL_APP_PASSWORD")
    if not gmail_user or not gmail_pw:
        raise RuntimeError(
            "GMAIL_USER and GMAIL_APP_PASSWORD must be set in environment"
        )

    subject   = _build_subject(items)
    html_body = _build_html(items, gmail_user)
    text_body = _build_text(items, gmail_user)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = gmail_user
    msg["To"]      = gmail_user

    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html",  "utf-8"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(gmail_user, gmail_pw)
            smtp.send_message(msg)
        log.info(f"Email digest sent to {gmail_user}")
        return True
    except (smtplib.SMTPException, OSError) as exc:
        log.error(f"Email digest failed: {type(exc).__name__}: {exc}")
        return False
