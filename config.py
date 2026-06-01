"""
Anesthesia Journal Digest — Configuration
==========================================
10 leading anesthesia journals. Nothing else.
"""

# ── Your Settings ────────────────────────────────────────────────────────────
RECIPIENT_EMAIL = "you@example.com"     # ← Replace with your email
SENDER_EMAIL    = "you@example.com"     # ← Usually the same
TIMEZONE        = "America/Toronto"            # Eastern Time (Ontario)

# ── Mode ─────────────────────────────────────────────────────────────────────
# "free"  → article links + podcast links + MOC tracker only
# "api"   → adds AI audio summary + AI-generated CME questions
MODE = "api"

# ── Claude API (only needed if MODE = "api") ─────────────────────────────────
# Set via environment variable ANTHROPIC_API_KEY, or paste here for testing
ANTHROPIC_API_KEY = ""  # Leave blank; use env var in production
CLAUDE_MODEL = "claude-sonnet-4-6"

# ── Audio Settings (only if MODE = "api") ────────────────────────────────────
TTS_VOICE = "en-US-AndrewMultilingualNeural"  # Male, clear, professional
TTS_VOICE_ALT = "en-US-AvaMultilingualNeural" # Female alternative
PODCAST_MINUTES_TARGET = 7  # Aim for ~7 min (roughly 1000 words)

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
