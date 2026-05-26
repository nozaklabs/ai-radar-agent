# 🛰️ AI Radar Agent

![Python](https://img.shields.io/badge/python-3.11-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Status](https://img.shields.io/badge/status-running%20Sun-success)
![Cost](https://img.shields.io/badge/cost-<%20%241%2Fmonth-brightgreen)

An autonomous agent that filters the AI/tech firehose into a curated, scored, project-aware digest — so a builder can stay informed without getting distracted.

Built by [Noha Zak](https://github.com/NohaZak) for **NoZak Labs** to defend focus while staying current.

---

## What it does

Once a week (Sunday at 11:00 AM Cairo), this agent:

1. **Fetches** items from 7 sources: Hacker News, Product Hunt, GitHub Trending, Ben's Bites, TLDR AI, Reddit (r/MachineLearning + r/SideProject), and Pega Community
2. **Dedupes** by URL and filters to the last 8 days
3. **Scores** every item against the NoZak Labs project context using **Claude Haiku 4.5**
4. **Tags** items with project relevance (Brands of Eden, lurniALP, Hykers, SE Job Hunt, Cross-cutting)
5. **Sends** an HTML email digest with one-tap triage actions (Adopt / Evaluate / Skip via mailto: Gmail filters)
6. **Updates** `radar.md` in this repo and commits it back

Total cost: **~$0.15/week (~$0.60/month)** in Claude API usage. Runs on GitHub Actions free tier.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  GitHub Actions (scheduled: Sunday, 09:00 UTC)              │
└────────────────────────┬────────────────────────────────────┘
                         ▼
        ┌────────────────────────────────────┐
        │  src/sources.py                    │
        │  Fetches from 7 sources via        │
        │  RSS + REST APIs                   │
        └────────────────┬───────────────────┘
                         ▼
        ┌────────────────────────────────────┐
        │  src/scorer.py                     │
        │  Claude Haiku 4.5 scores each item │
        │  against NoZak Labs context        │
        └────────────────┬───────────────────┘
                         ▼
        ┌────────────────────────────────────┐
        │  src/outputs.py + email_digest.py  │
        │  Sends Gmail digest + writes       │
        │  radar.md                          │
        └────────────────────────────────────┘
```

---

## Why this exists

The problem: dozens of new AI tools, GitHub repos, and launches drop every day. Trying to track them all destroys focus. Ignoring them entirely means missing genuinely useful tools.

The solution: a personal agent that knows what I'm building (three client projects + an active job search) and scores every item by relevance — so I check the radar once a week during a dedicated 30-min slot, not every five minutes during deep work.

---

## Scoring rubric

| Score | Tier | What it means |
|---|---|---|
| 90–100 | 🔥 Act Now | Directly unblocks or significantly improves a Tier 1 project this week |
| 75–89 | 🔥 Act Now | Strong relevance to a Tier 1 project — worth evaluating |
| 50–74 | 👀 Watch | Tangential relevance or strong relevance to cross-cutting interests |
| 25–49 | 📦 Archive | Weak relevance — kept for searchability only |
| 0–24 | _Dropped_ | Noise or hits an explicit noise filter |

The rubric and the full project context live in [`src/context.py`](src/context.py).

---

## Sample output

An excerpt from a real run. The agent fetched 45 items, scored each one against the NoZak Labs project context, and surfaced this as the highest-relevance item that week:

> ### 🔥 Act Now
>
> **[Aaseya Agentic Xcelerator](https://community.pega.com/marketplace/component/aaseya-agentic-xcelerator)** `78` · Pega Community · _SE Job Hunt, Cross-cutting_
>
> Aaseya's Agentic Xcelerator is a Pega Platform component enabling enterprises to build and deploy AI agents with governance frameworks, workflow orchestration, and automation capabilities.
>
> _Why it matters:_ Directly relevant to SE Job Hunt — Pega Robotics and Decisioning are growth areas, and agentic AI on Pega is an emerging platform capability. Understanding enterprise agentic patterns, governance, and workflow integration strengthens SA technical depth and interview readiness.

What makes this useful isn't the score — it's the _Why it matters_ line. The agent connects the item to specific active projects (SE Job Hunt, Cross-cutting), not just generic AI relevance. Lower-scoring items get the same treatment in [`radar.md`](radar.md), including explicit reasoning for why something is noise.

---

## Tech stack

- **Python 3.11**
- **Anthropic Claude Haiku 4.5** for scoring
- **Gmail SMTP** for the weekly digest
- **GitHub Actions** for scheduling and execution
- **feedparser + requests** for source fetching

---

## Project structure

```
ai-radar-agent/
├── .github/workflows/
│   └── radar.yml              # GitHub Actions schedule + workflow
├── src/
│   ├── __init__.py
│   ├── context.py             # NoZak Labs project priorities (the agent's "brain")
│   ├── sources.py             # Fetchers for each source
│   ├── scorer.py              # Claude scoring engine
│   ├── outputs.py             # radar.md writer
│   ├── email_digest.py        # Gmail SMTP digest sender
│   └── main.py                # Orchestrator
├── scripts/
│   └── verify_smtp.py         # Local SMTP credential check
├── docs/
│   └── SETUP.md               # Step-by-step setup instructions
├── radar.md                   # Auto-updated digest (don't edit manually)
├── requirements.txt
└── README.md
```

---

## Local development

```bash
# Install dependencies
pip install -r requirements.txt

# Set env vars (use a .env file or your shell)
# Windows cmd:
set ANTHROPIC_API_KEY=sk-ant-...
set GMAIL_USER=noha@nozaklabs.com
set GMAIL_APP_PASSWORD=xxxx_xxxx_xxxx_xxxx

# PowerShell:
$env:ANTHROPIC_API_KEY="sk-ant-..."
$env:GMAIL_USER="noha@nozaklabs.com"
$env:GMAIL_APP_PASSWORD="xxxx_xxxx_xxxx_xxxx"

# Unix/macOS:
export ANTHROPIC_API_KEY=sk-ant-...
export GMAIL_USER=noha@nozaklabs.com
export GMAIL_APP_PASSWORD=xxxx_xxxx_xxxx_xxxx

# Run the agent
python -m src.main
```

---

## Updating priorities

Project priorities live in `src/context.py`. Edit the `PROJECTS`, `CROSS_CUTTING`, or `NOISE_FILTERS` blocks, commit, and the next scheduled run will use the updated context. No other code changes needed.

---

## Roadmap

This is a living project. Active and planned improvements:

- [ ] **Broader score distribution** — current scoring buckets too many items at exactly 72. Refine the rubric prompt so cross-cutting items differentiate more sharply.
- [ ] **Triage feedback loop** — parse Gmail labels (Radar/Adopt, Radar/Evaluate, Radar/Skip) and feed adoption rate back into the scorer as a quality signal
- [ ] **Source quality feedback loop** — track which "Act Now" items actually convert to "Adopt" decisions, surface low-signal sources for pruning.
- [ ] **Multi-tenant context** — generalize the agent so other solo operators can fork the repo, swap in their own `context.py`, and run the same pipeline against their own projects.
- [ ] **Cost dashboard** — add a small monthly cost tracker that reads the Anthropic usage API and posts spend deltas alongside the digest.
- [ ] **Pega Community deep-dive source** — current Pega fetcher pulls the general RSS feed; tighten it to specifically surface Decisioning and Constellation content.

---

## License

MIT
