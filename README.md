# Anesthesia Journal Digest

Automated email service covering 10 leading anesthesia journals. Runs free on GitHub Actions.

## What You Get

| Day | Email |
|-----|-------|
| **Monday** | New **open-access** articles (most clinically relevant one per journal, chosen by Claude in a single batched call), journal podcast cards, and a ~15 min AI **two-host** audio summary played inline via GitHub Pages |
| **Saturday** | Week's top articles + 10 AI-generated self-assessment questions, plus a button to an interactive online quiz with instant grading, explanations, and a downloadable PDF completion record |
| **1st of month** | Top 5 monthly articles + Self-Assessment Tracker attached |

## Audio summary (two-host podcast)

Each digest generates a NotebookLM-style **two-host conversation** (Host A =
`en-US-AndrewMultilingualNeural`, Host B = `en-US-AvaMultilingualNeural`),
covering all of the day's selected articles with real back-and-forth. It targets
~2600 words at +25% playback rate ≈ 15 minutes. Optional intro/outro music is
mixed in from `assets/intro_music.mp3` and `assets/outro_music.mp3` (see
[`assets/README.md`](assets/README.md) — drop royalty-free CC0 MP3s there).

The MP3 is published to `docs/audio/` and played inline on a styled GitHub Pages
player. **Enable it once:** repo **Settings → Pages → Source: "Deploy from a
branch" → Branch: `main`, folder: `/docs` → Save.** Your player will live at:

> **https://&lt;your-username&gt;.github.io/&lt;repo-name&gt;/**

(The exact URL is derived automatically in the workflow — nothing is hardcoded.)

## Interactive CME quiz (Saturdays)

Each Saturday the digest builds an interactive, mobile-friendly quiz of **10
single-best-answer** questions from the week's articles and publishes it at a
dated URL under `docs/cme/`. Readers select answers, press **Submit Test** to get
their score with the correct answer + explanation revealed under each question
(nothing is revealed before submit), then can **Download a PDF completion record**
(built client-side with [jsPDF](https://github.com/parallax/jsPDF)) for their own
self-learning records (self-reportable under RCPSC MOC Section 2). The Saturday email shows the questions for preview and
links straight to that week's quiz. Past quizzes stay live:

> Quiz list: **https://&lt;your-username&gt;.github.io/&lt;repo-name&gt;/cme/**
> Each week:  **…/cme/YYYY-MM-DD.html**

Requires `ffmpeg` (preinstalled on GitHub Actions; `brew install ffmpeg` locally).

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

> Create a GitHub repo called anesthesia-digest, push all these files, and help me add four GitHub Secrets: `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD`, `ANTHROPIC_API_KEY`, and `RECIPIENT_EMAIL`.

Claude Code will walk you through each step.

**No personal info lives in the code.** Your email addresses come entirely from
GitHub Secrets:

| Secret | Used for |
|--------|----------|
| `RECIPIENT_EMAIL` | where the digest is sent |
| `GMAIL_ADDRESS` | the sending Gmail account (also used as the `From`) |
| `GMAIL_APP_PASSWORD` | Gmail app password (never your real password) |
| `ANTHROPIC_API_KEY` | Claude API key for the podcast + CME questions |

To run locally instead, export them as environment variables in your shell.

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

**`MODE = "api"`** (default) — Full features: AI audio podcast, AI self-assessment questions, article digest, Self-Assessment Tracker.

**`MODE = "free"`** — No AI: article links, podcast links, Self-Assessment Tracker only. $0/month total.

Change in `config.py` → `MODE`.

---

## Troubleshooting

**Empty emails?** Normal for the first run if between journal issues. The `INITIAL_LOOKBACK_DAYS = 30` setting pulls the last month to start. Reduce to `7` after 2-3 weeks (the digest now runs weekly on Monday, so a 7-day window covers everything since the last one).

**No audio / player empty?** Check that `ANTHROPIC_API_KEY` is set in GitHub Secrets, that GitHub Pages is enabled (Settings → Pages → `/docs` on `main`), and that the workflow has `permissions: contents: write` (already set) so it can push the episode.

**Email not arriving?** Check GitHub Actions for errors (red ❌). Verify Gmail App Password in Secrets. Check spam folder.
