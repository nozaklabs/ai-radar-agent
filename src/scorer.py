"""
Scoring engine — calls the AI API to score every fetched item against the
NoZak Labs project context.

For each item, the model returns structured JSON:

    {
        "score": int (0-100),
        "tier": "Act Now" | "Watch" | "Archive",
        "project_match": [...],
        "summary": str,
        "why_it_matters": str
    }

Items below MIN_SCORE_TO_KEEP are filtered out entirely.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time

import anthropic

from .context import (
    COMPANY_CONTEXT,
    CROSS_CUTTING,
    MIN_SCORE_TO_KEEP,
    NOISE_FILTERS,
    PROJECTS,
    TIER_THRESHOLDS,
)

log = logging.getLogger(__name__)

# Scoring model — fast and cheap, well-suited for structured JSON extraction.
_SCORING_MODEL = "claude-haiku-4-5-20251001"

# Rate limit handling
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 5


def _build_system_prompt() -> str:
    """Build the system prompt with full NoZak Labs context."""
    projects_block = "\n\n".join(
        f"## {name} (Tier {p['tier']}, {p['stage']})\n"
        f"{p['summary']}\n"
        f"**Tech stack:** {', '.join(p.get('tech_stack', []))}\n"
        f"**Looking for:**\n" + "\n".join(f"- {x}" for x in p["looking_for"])
        for name, p in PROJECTS.items()
    )

    cross_cutting_block = (
        f"## Cross-cutting interests (Tier {CROSS_CUTTING['tier']})\n"
        f"{CROSS_CUTTING['summary']}\n"
        f"**Looking for:**\n"
        + "\n".join(f"- {x}" for x in CROSS_CUTTING["looking_for"])
    )

    noise_block = "\n".join(f"- {x}" for x in NOISE_FILTERS)

    return f"""You are the scoring engine for NoZak Labs' AI Radar Agent.

# About NoZak Labs

{COMPANY_CONTEXT}

# Active projects

{projects_block}

{cross_cutting_block}

# Explicit noise — score these LOW (0-30):

{noise_block}

# Your job

For each item I send you, return a JSON object with these fields:

- "score": integer 0-100, how relevant this item is to NoZak Labs
- "tier": one of "Act Now" (≥{TIER_THRESHOLDS['act_now']}), "Watch" \
({TIER_THRESHOLDS['watch']}-{TIER_THRESHOLDS['act_now']-1}), or "Archive" (<{TIER_THRESHOLDS['watch']})
- "project_match": array of project names this item could help \
(from: "Brands of Eden", "lurniALP", "Hykers", "SE Job Hunt", "Cross-cutting"). \
Use [] if no match. Multiple matches allowed.
- "summary": 1-2 sentences plainly describing what the item IS
- "why_it_matters": 1-2 sentences explaining the specific NoZak Labs angle. \
If score is low, briefly say why (e.g., "Crypto — explicit noise filter"). \
If score is high, name the concrete project benefit.

# Scoring rubric

- 90-100: Directly unblocks or significantly improves a Tier 1 project this week.
- 75-89: Strong relevance to a Tier 1 project — worth evaluating during a radar slot.
- 50-74: Tangential relevance, or strong relevance to cross-cutting interests.
- 25-49: Weak relevance — keep for archive only.
- 0-24: Noise, irrelevant, or matches noise filters.

# Output format

Respond with ONLY a valid JSON object. No markdown, no preamble, no explanation \
before or after. The first character of your response must be {{ and the last \
must be }}.
"""


def _extract_json(text: str) -> dict | None:
    """Extract the first JSON object from a model response."""
    text = text.strip()
    # Strip markdown code fences if present
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find a JSON object substring
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                return None
    return None


def _tier_from_score(score: int) -> str:
    """Map a numeric score to a tier label. Used by outputs and email_digest."""
    if score >= TIER_THRESHOLDS["act_now"]:
        return "🔥 Act Now"
    if score >= TIER_THRESHOLDS["watch"]:
        return "👀 Watch"
    return "📦 Archive"


def _score_one(client: anthropic.Anthropic, item: dict, system_prompt: str) -> dict | None:
    """Score a single item. Returns None on unrecoverable failure."""
    user_msg = (
        f"Title: {item['title']}\n"
        f"Source: {item['source']}\n"
        f"Category: {item['category']}\n"
        f"URL: {item['url']}\n"
        f"Summary from source: {item.get('summary', '(none)')[:500]}"
    )

    for attempt in range(MAX_RETRIES):
        try:
            response = client.messages.create(
                model=_SCORING_MODEL,
                max_tokens=600,
                system=system_prompt,
                messages=[{"role": "user", "content": user_msg}],
            )
            text = response.content[0].text
            parsed = _extract_json(text)
            if not parsed:
                log.warning(f"Could not parse JSON for: {item['title'][:60]}")
                return None
            return parsed
        except anthropic.RateLimitError:
            wait = RETRY_BACKOFF_SECONDS * (attempt + 1)
            log.warning(f"Rate limit hit, sleeping {wait}s")
            time.sleep(wait)
        except Exception as e:
            log.error(f"Scoring failed for {item['title'][:60]}: {e}")
            return None
    return None


def score_items(items: list[dict]) -> list[dict]:
    """Score every item and return enriched list (filtered by MIN_SCORE_TO_KEEP)."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set in environment")

    client = anthropic.Anthropic(api_key=api_key)
    system_prompt = _build_system_prompt()

    scored: list[dict] = []
    for i, item in enumerate(items, start=1):
        log.info(f"[{i}/{len(items)}] Scoring: {item['title'][:60]}")
        result = _score_one(client, item, system_prompt)
        if not result:
            continue

        score = int(result.get("score", 0))
        if score < MIN_SCORE_TO_KEEP:
            continue

        item["score"] = score
        item["tier"] = _tier_from_score(score)
        item["project_match"] = result.get("project_match", []) or []
        item["ai_summary"] = result.get("summary", "")
        item["why_it_matters"] = result.get("why_it_matters", "")
        scored.append(item)

    # Sort highest score first
    scored.sort(key=lambda x: x["score"], reverse=True)
    log.info(f"Scored {len(scored)} items above threshold (from {len(items)})")
    return scored
