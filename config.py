"""
Anesthesia Journal Digest — Configuration
==========================================
10 leading anesthesia journals. Nothing else.

No personal info is hardcoded here. Email addresses are read from environment
variables / GitHub Secrets so this repo is safe to make public.
"""

import os

# ── Your Settings ────────────────────────────────────────────────────────────
# Set these as environment variables (locally) or GitHub Secrets (in CI).
RECIPIENT_EMAIL = os.environ.get("RECIPIENT_EMAIL", "")
SENDER_EMAIL    = os.environ.get("SENDER_EMAIL", os.environ.get("GMAIL_ADDRESS", ""))
TIMEZONE        = os.environ.get("TIMEZONE", "America/Toronto")  # Eastern Time

# ── Mode ─────────────────────────────────────────────────────────────────────
# "free"  → article links + podcast links + MOC tracker only
# "api"   → adds AI audio summary + AI-generated CME questions
MODE = "api"

# ── Claude API (only needed if MODE = "api") ─────────────────────────────────
# ALWAYS read from the ANTHROPIC_API_KEY environment variable / GitHub Secret.
# Never paste a key here — this repo is public. Kept only as an empty fallback.
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
# Strong model — used only where reasoning quality matters most (CME questions).
CLAUDE_MODEL = "claude-sonnet-4-6"
# Cheaper/faster model — used for the simpler tasks (article selection,
# podcast script writing) to cut cost while keeping quality.
CLAUDE_MODEL_FAST = "claude-haiku-4-5"

# Cap how much article source text is sent to the API per CME article (chars).
# The fetcher already extracts only Results/Discussion/Conclusions sections;
# this truncates them further to keep token cost down.
CME_SOURCE_CHARS = 1600

# ── Audio Settings (only if MODE = "api") ────────────────────────────────────
# Two-host NotebookLM-style conversation. Host A = male, Host B = female.
HOST_A_VOICE = "en-US-AndrewMultilingualNeural"  # Host A — male, warm
HOST_B_VOICE = "en-US-AvaMultilingualNeural"     # Host B — female, bright
TTS_VOICE = HOST_A_VOICE        # Back-compat single-voice fallback
TTS_VOICE_ALT = HOST_B_VOICE
TTS_RATE = "+10%"               # Gentle speed-up — natural pace, not rushed
# ~2400 words at +10% speed ≈ 15 minutes of actual listening time.
PODCAST_MINUTES_TARGET = 15
PODCAST_WORD_TARGET = 2400

# ── Music / Mixing (assets/intro_music.mp3, assets/outro_music.mp3) ──────────
INTRO_MUSIC = "assets/intro_music.mp3"
OUTRO_MUSIC = "assets/outro_music.mp3"
MUSIC_DUCK_DB = -12             # Lower music this many dB so it sits under voices
INTRO_SOLO_MS = 6000            # Intro plays SOLO this long before the hosts start
OUTRO_SOLO_MS = 6000            # Outro plays SOLO this long after the hosts finish
MUSIC_CROSSFADE_MS = 1200       # Smooth crossfade between music and voices

# ── GitHub Pages (inline podcast playback) ───────────────────────────────────
# Project Pages served from the /docs folder on the main branch. The full URL
# is read from the environment so no username is hardcoded — the GitHub Actions
# workflow derives it automatically from the repo context.
GITHUB_PAGES_URL = os.environ.get("GITHUB_PAGES_URL", "")
DOCS_DIR = "docs"
AUDIO_SUBDIR = "audio"

# ── Initial Run Settings ─────────────────────────────────────────────────────
# For the first few weeks, pull from older issues so emails aren't empty.
# Set to 30 to get the last month of articles; reduce to 4 once running.
INITIAL_LOOKBACK_DAYS = 30  # Change to 4 after the first 2-3 weeks

# ── Journal Registry ─────────────────────────────────────────────────────────
JOURNALS = [
    {
        "name": "British Journal of Anaesthesia",
        "abbreviation": "BJA",
        "issn": "0007-0912",
        "rss_url": "https://www.bjanaesthesia.org/rss/current",
        "rss_url_inpress": "https://www.bjanaesthesia.org/rss/inpress",
        "website": "https://www.bjanaesthesia.org",
        "impact_factor": 9.2,
        "publisher": "elsevier",
        "podcast": {
            "name": "BJA Podcast",
            "rss_url": "https://feed.podbean.com/bjajournal/feed.xml",
            "website": "https://podcasts.apple.com/podcast/id649829936",
        },
    },
    {
        "name": "Anesthesiology",
        "abbreviation": "Anesthesiology",
        "issn": "0003-3022",
        "rss_url": "https://pubs.asahq.org/anesthesiology/pages/rss",
        "website": "https://pubs.asahq.org/anesthesiology",
        "impact_factor": 9.1,
        "publisher": "lww",
        "podcast": {
            "name": "Anesthesiology Journal Podcast",
            "rss_url": "https://anesthesiology.libsyn.com/rss",
            "website": "https://anesthesiology.libsyn.com/",
        },
    },
    {
        "name": "Anaesthesia",
        "abbreviation": "Anaesthesia",
        "issn": "0003-2409",
        "rss_url": "https://associationofanaesthetists-publications.onlinelibrary.wiley.com/feed/13652044/most-recent",
        "website": "https://associationofanaesthetists-publications.onlinelibrary.wiley.com/journal/13652044",
        "impact_factor": 6.9,
        "publisher": "wiley",
        "podcast": {
            "name": "Anaesthesia Journal Podcast",
            "rss_url": "https://feed.podbean.com/anaepodcasts/feed.xml",
            "website": "https://anaepodcasts.podbean.com/",
        },
    },
    {
        "name": "European Journal of Anaesthesiology",
        "abbreviation": "EJA",
        "issn": "0265-0215",
        "rss_url": "https://journals.lww.com/ejanaesthesiology/_layouts/15/OAKS.Journals/feed.aspx?FeedType=MostRecentIssue",
        "website": "https://journals.lww.com/ejanaesthesiology",
        "impact_factor": 6.8,
        "publisher": "lww",
        "podcast": {
            "name": "EJA Author Audio Q&A",
            "rss_url": None,
            "website": "https://journals.lww.com/ejanaesthesiology",
        },
    },
    {
        "name": "Journal of Clinical Anesthesia",
        "abbreviation": "JCA",
        "issn": "0952-8180",
        "rss_url": "https://www.sciencedirect.com/journal/journal-of-clinical-anesthesia/rss",
        "website": "https://www.sciencedirect.com/journal/journal-of-clinical-anesthesia",
        "impact_factor": 5.1,
        "publisher": "elsevier",
        "podcast": None,
    },
    {
        "name": "Anaesthesia Critical Care & Pain Medicine",
        "abbreviation": "ACCPM",
        "issn": "2352-5568",
        "rss_url": "https://www.sciencedirect.com/journal/anaesthesia-critical-care-and-pain-medicine/rss",
        "website": "https://www.sciencedirect.com/journal/anaesthesia-critical-care-and-pain-medicine",
        "impact_factor": 4.7,
        "publisher": "elsevier",
        "podcast": None,
    },
    {
        "name": "Anesthesia & Analgesia",
        "abbreviation": "A&A",
        "issn": "0003-2999",
        "rss_url": "https://journals.lww.com/anesthesia-analgesia/_layouts/15/OAKS.Journals/feed.aspx?FeedType=MostRecentIssue",
        "website": "https://journals.lww.com/anesthesia-analgesia",
        "impact_factor": 3.8,
        "publisher": "lww",
        "podcast": {
            "name": "OpenAnesthesia Podcast",
            "rss_url": "https://openanesthesia.libsyn.com/rss",
            "website": "https://www.openanesthesia.org/",
        },
    },
    {
        "name": "Regional Anesthesia & Pain Medicine",
        "abbreviation": "RAPM",
        "issn": "1098-7339",
        "rss_url": "https://rapm.bmj.com/rss/current.xml",
        "website": "https://rapm.bmj.com",
        "impact_factor": 3.5,
        "publisher": "bmj",
        "podcast": {
            "name": "RAPM Focus",
            "rss_url": "https://feed.podbean.com/rapmfocusbmj/feed.xml",
            "website": "https://rapmfocusbmj.podbean.com/",
        },
    },
    {
        "name": "Canadian Journal of Anesthesia",
        "abbreviation": "CJA",
        "issn": "0832-610X",
        "rss_url": "https://link.springer.com/journal/12630.rss",
        "website": "https://link.springer.com/journal/12630",
        "impact_factor": 3.3,
        "publisher": "springer",
        "podcast": None,
    },
    {
        "name": "International Journal of Obstetric Anesthesia",
        "abbreviation": "IJOA",
        "issn": "0959-289X",
        "rss_url": "https://www.sciencedirect.com/journal/international-journal-of-obstetric-anesthesia/rss",
        "website": "https://www.sciencedirect.com/journal/international-journal-of-obstetric-anesthesia",
        "impact_factor": 2.3,
        "publisher": "elsevier",
        "podcast": None,
    },
]

# ── Bonus Podcasts (free, from journal publishers) ───────────────────────────
BONUS_PODCASTS = [
    {
        "name": "ASA Central Line",
        "rss_url": "https://feed.podbean.com/asahq/feed.xml",
        "website": "https://www.asahq.org/podcasts/central-line",
        "description": "ASA's monthly podcast covering anesthesiology issues",
    },
]

# ── Schedule Reference ───────────────────────────────────────────────────────
# Monday & Thursday  → biweekly digest (articles + podcasts + audio if API)
# Saturday           → weekly CME questions (API) + week's highlights
# 1st of month       → monthly top-5 + MOC tracker attachment
