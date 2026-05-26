# 🛠️ Setup Guide — AI Radar Agent

This documents the one-time setup completed when this agent was built. Useful as reference if anything needs to be re-created or rotated.

---

## Prerequisites

- [x] **Anthropic API key** with billing enabled
- [x] **Gmail account** with 2-Step Verification enabled
- [x] **GitHub repo** with Actions enabled

---

## 1. Anthropic API setup

1. Sign up at [console.anthropic.com](https://console.anthropic.com)
2. Add billing — $5 of prepaid credit is enough for ~6 months of radar runs
3. Create an API key named `nozak-radar-agent`
4. Save the key in a password manager or Windows Credential Manager
5. Add it to GitHub Actions secrets as `ANTHROPIC_API_KEY` (see step 3 below)

---

## 2. Gmail SMTP setup

**Prerequisite:** Gmail account with 2-Step Verification enabled (App Passwords require it)

1. **Step 1:** Visit [https://myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
2. **Step 2:** Create an app password named `nozak-radar-agent`
3. **Step 3:** Copy the 16-character password (Google shows it once)
4. **Step 4:** Add to GitHub Actions secrets:
   - `GMAIL_USER` = `noha@nozaklabs.com`
   - `GMAIL_APP_PASSWORD` = the 16-char password
5. **Step 5:** Log the credential in your password manager:
   - Entry name: `Gmail App Password — nozak-radar-agent`
   - Notes: created date, scope, GitHub secret name, revocation URL (`https://myaccount.google.com/apppasswords`)
6. **Step 6:** Create three Gmail filters so triage replies auto-label:
   - `subject:"Radar Adopt:"` → label `Radar/Adopt`, skip inbox
   - `subject:"Radar Evaluate:"` → label `Radar/Evaluate`, skip inbox
   - `subject:"Radar Skip:"` → label `Radar/Skip`, skip inbox
7. **Step 7:** Run `python scripts/verify_smtp.py` locally with the env vars set. Confirm the test email arrives.

---

## 3. GitHub Actions secrets

In the repo: **Settings → Secrets and variables → Actions → New repository secret**

Add three secrets:

| Name | Value |
|---|---|
| `ANTHROPIC_API_KEY` | Your Anthropic API key |
| `GMAIL_USER` | `noha@nozaklabs.com` |
| `GMAIL_APP_PASSWORD` | 16-char Gmail App Password |

---

## 4. Verify the setup

### Local SMTP test

Before relying on the scheduled run, confirm Gmail credentials work end-to-end:

```bash
# Windows cmd
set GMAIL_USER=noha@nozaklabs.com
set GMAIL_APP_PASSWORD=xxxx_xxxx_xxxx_xxxx
python scripts/verify_smtp.py

# PowerShell
$env:GMAIL_USER="noha@nozaklabs.com"
$env:GMAIL_APP_PASSWORD="xxxx_xxxx_xxxx_xxxx"
python scripts/verify_smtp.py

# Unix/macOS
export GMAIL_USER=noha@nozaklabs.com
export GMAIL_APP_PASSWORD=xxxx_xxxx_xxxx_xxxx
python scripts/verify_smtp.py
```

### Manual workflow test run

In the GitHub repo, go to **Actions → AI Radar Agent → Run workflow**. This triggers the agent immediately so you can confirm everything works without waiting for Sunday.

Check the workflow logs. You should see:

```
🛰️  Starting NoZak Labs Radar Agent
Step 1/3: Fetching from sources…
  Hacker News: N items
  Product Hunt: N items
  …
Step 2/3: Scoring with Claude…
  [1/N] Scoring: ...
Step 3/3: Writing outputs…
  Wrote radar.md
  Email digest sent to noha@nozaklabs.com
✅ Radar run complete
```

Then check:
- The digest email arrived in `noha@nozaklabs.com`
- `radar.md` was updated and committed

---

## 5. Schedule

The workflow runs on cron `0 9 * * 0` — that's **09:00 UTC every Sunday**.

- = 11:00 Cairo standard time (UTC+2, Nov–Mar)
- = 12:00 Cairo DST (UTC+3, Apr–Oct)

You can manually trigger a run anytime from the Actions tab.

---

## 6. Calendar blocks

**Sunday 1:30–2:00pm Cairo** (already created on `noha@nozaklabs.com` calendar, recurs 8 weeks then checkpoint).

---

## Cost expectations

| Item | Monthly cost |
|---|---|
| Anthropic API (Haiku 4.5, ~100 items × 1 run/week) | ~$0.15–0.50 |
| Gmail SMTP | $0 |
| GitHub Actions (well within free 2000 min/month) | $0 |
| **Total** | **~$0.15–0.50/month** |

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `Missing required environment variables` | GitHub secret not set | Add all 3 secrets in repo settings |
| Workflow runs but no email arrives | App Password wrong or revoked | Run `scripts/verify_smtp.py` locally to confirm credentials |
| Authentication error in logs | 2FA not enabled on Google account | Enable 2FA, regenerate App Password |
| Email lands in spam | First-time sender warmup | Mark "Not spam" once; Gmail learns |
| Triage buttons don't open mail app on mobile | Default mail app not set | iOS: Settings → Mail → Default Mail App; Android: Settings → Apps → Default apps |
| All scores are 0 | Claude returned malformed JSON | Check workflow logs, may be rate-limited |
| `radar.md` not updating in repo | Workflow lacks write permission | Verify `permissions: contents: write` is in workflow |

---

## Rotating credentials

If a key is compromised:

1. Revoke the old key in the source console (Anthropic console or Google App Passwords page)
2. Generate a new key with the same name + `-v2`
3. Update the corresponding GitHub Actions secret
4. Update the password manager entry
5. Run `scripts/verify_smtp.py` to confirm the new App Password works before the next Sunday run
