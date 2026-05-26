"""
NoZak Labs AI Radar Agent — main entry point.

Pipeline:
    1. Fetch items from all configured sources
    2. Score each item via the AI scoring engine against NoZak Labs context
    3. Write radar.md (durable archive)
    4. Send email digest via Gmail SMTP

Run locally:
    python -m src.main

Run via GitHub Actions: configured in .github/workflows/radar.yml
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

# Allow running both as `python -m src.main` and `python src/main.py`
if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from src.email_digest import send_email_digest
    from src.outputs import write_radar_md
    from src.scorer import score_items
    from src.sources import fetch_all_sources
else:
    from .email_digest import send_email_digest
    from .outputs import write_radar_md
    from .scorer import score_items
    from .sources import fetch_all_sources


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    # Silence noisy libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def check_environment() -> None:
    """Fail fast if required env vars are missing."""
    required = ["ANTHROPIC_API_KEY", "GMAIL_USER", "GMAIL_APP_PASSWORD"]
    missing = [v for v in required if not os.environ.get(v)]
    if missing:
        raise RuntimeError(
            f"Missing required environment variables: {', '.join(missing)}.\n"
            f"Set these in GitHub Actions secrets or your local .env file."
        )


def main() -> int:
    setup_logging()
    log = logging.getLogger("radar")

    try:
        check_environment()
    except RuntimeError as e:
        log.error(str(e))
        return 1

    log.info("🛰️  Starting NoZak Labs Radar Agent")

    # 1. Fetch
    log.info("Step 1/3: Fetching from sources…")
    items = fetch_all_sources()
    if not items:
        log.warning("No items fetched. Nothing to score.")
        return 0
    log.info(f"Fetched {len(items)} unique items")

    # 2. Score
    log.info("Step 2/3: Scoring items…")
    scored = score_items(items)
    if not scored:
        log.warning("No items survived scoring threshold.")
        return 0

    # 3. Write outputs
    log.info("Step 3/3: Writing outputs…")
    # Write radar.md FIRST — that's the durable archive
    radar_path = Path(__file__).resolve().parent.parent / "radar.md"
    write_radar_md(scored, radar_path)
    # Then send email — if it fails, the archive still exists
    send_email_digest(scored)

    log.info("✅ Radar run complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
