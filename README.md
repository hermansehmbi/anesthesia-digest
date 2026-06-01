# Anesthesia Journal Digest

Automated email service covering 10 leading anesthesia journals. Runs free on GitHub Actions.

## What You Get

| Day | Email |
|-----|-------|
| **Monday & Thursday** | New articles (open access flagged), journal podcast links, AI audio summary (~7 min MP3 attached) |
| **Saturday** | Week's top articles + 5 AI-generated CME questions (RCPSC Section 2 & 3) |
| **1st of month** | Top 5 monthly articles + MOC Excel tracker attached |

## Journals

1. British Journal of Anaesthesia (IF 9.2) — podcast ✅
2. Anesthesiology (IF 9.1) — podcast ✅
3. Anaesthesia (IF 6.9) — podcast ✅
4. European Journal of Anaesthesiology (IF 6.8)
5. Journal of Clinical Anesthesia (IF 5.1)
6. Anaesthesia Critical Care & Pain Medicine (IF 4.7)
7. Anesthesia & Analgesia (IF 3.8) — podcast ✅
8. Regional Anesthesia & Pain Medicine (IF 3.5) — podcast ✅
9. Canadian Journal of Anesthesia (IF 3.3)
10. International Journal of Obstetric Anesthesia (IF 2.3)

## Cost

| Component | Cost |
|-----------|------|
| GitHub Actions | Free |
| Edge TTS (audio) | Free |
| Claude API (script + CME) | ~$1-2/month |
| Gmail sending | Free |

---

## Setup Instructions (Mac)

### Step 1 — Gmail App Password (3 min)

1. Go to https://myaccount.google.com/security
2. Enable **2-Step Verification** if not already on
3. Go to https://myaccount.google.com/apppasswords
4. Create app password → name it "Anesthesia Digest"
5. Copy the 16-character code (e.g., `abcd efgh ijkl mnop`)

### Step 2 — Anthropic API Key (2 min)

1. Go to https://console.anthropic.com
2. Create an account (or sign in)
3. Go to API Keys → Create Key
4. Copy the key (starts with `sk-ant-...`)
5. Add a $5 spending limit under Billing if you want a safety cap

### Step 3 — Install Claude Code (2 min)

Open Terminal and run:
```bash
curl -fsSL https://claude.ai/install.sh | bash -s latest
```
Close Terminal, open a new window, then type:
```bash
claude
```
Log in with your Anthropic account when the browser opens.

### Step 4 — Deploy (5 min)

Download and unzip the project. In Terminal:
```bash
cd ~/Downloads/anesthesia-digest
claude
```

Then tell Claude Code:

> First, open config.py and change RECIPIENT_EMAIL and SENDER_EMAIL to my-email@gmail.com (use your actual email). Then create a GitHub repo called anesthesia-digest, push all these files, and help me add three GitHub Secrets: GMAIL_ADDRESS, GMAIL_APP_PASSWORD, and ANTHROPIC_API_KEY.

Claude Code will walk you through each step.

### Step 5 — Test It

1. Go to github.com → your repo → **Actions** tab
2. Click **Anesthesia Digest** on the left
3. Click **Run workflow** → pick "digest" → **Run workflow**
4. Wait 2-3 minutes, check your email

---

## How to Change Things Later

Open Terminal, navigate to your repo, run `claude`, and ask in plain English:

- "Change my email to newemail@gmail.com"
- "Add the Journal of Neurosurgical Anesthesiology"
- "Change digest to Monday/Wednesday/Friday"
- "Reduce the podcast to 5 minutes"
- "Make CME questions easier / harder"

---

## Modes

**`MODE = "api"`** (default) — Full features: AI audio podcast, AI CME questions, article digest, MOC tracking.

**`MODE = "free"`** — No AI: article links, podcast links, MOC tracking only. $0/month total.

Change in `config.py` → `MODE`.

---

## Troubleshooting

**Empty emails?** Normal for the first run if between journal issues. The `INITIAL_LOOKBACK_DAYS = 30` setting pulls the last month to start. Reduce to `4` after 2-3 weeks.

**Audio not attached?** Check that `ANTHROPIC_API_KEY` is set in GitHub Secrets.

**Email not arriving?** Check GitHub Actions for errors (red ❌). Verify Gmail App Password in Secrets. Check spam folder.
