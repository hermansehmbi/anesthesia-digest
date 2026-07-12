"""
Anesthesia Journal Digest — Main
==================================
Runs monthly (see .github/workflows): digest on the 1st, CME on the 7th,
monthly reconciliation on the 25th.
Usage:
    python main.py digest          # Monthly article digest (+ podcast + Deep Dive)
    python main.py saturday        # CME self-assessment for the month's articles
    python main.py monthly         # Monthly top-5 + MOC tracker
    python main.py preview         # Preview digest locally (no email)
    python main.py preview-sat     # Preview self-assessment email locally
    python main.py preview-month   # Preview monthly email locally
"""

import sys
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

from config import (
    JOURNALS, BONUS_PODCASTS, RECIPIENT_EMAIL, SENDER_EMAIL,
    MODE, INITIAL_LOOKBACK_DAYS, MONTHLY_LOOKBACK_DAYS,
)
from fetcher import fetch_articles, fetch_podcast_episodes, fetch_bonus_podcasts
from article_selector import select_digest_articles
from email_builder import build_digest_email, build_saturday_email, build_monthly_email
from email_sender import send_email
from moc_tracker import log_articles, log_cme, update_summary, MOC_FILE
import gsheets

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

CACHE_FILE = "articles_cache.json"
# The EXACT final list of articles emailed in the most recent digest (now the
# month's featured set). The CME step reads ONLY from this file — no re-fetching,
# no new articles — so the self-assessment is locked to that month's digest.
# (Filename kept as-is to preserve the CI cache path.)
MONDAY_FEATURED_FILE = "monday_featured.json"
# The digest's Deep Dive summaries + the published page URL. The CME step reuses
# these to ground its questions (Option B) and to link the same page in the email.
WEEKLY_SUMMARIES_FILE = "weekly_summaries.json"


def run_digest(preview=False):
    """Monthly digest (1st): articles + podcasts + audio (if API mode)."""
    logger.info("=" * 50)
    logger.info("DIGEST — fetching articles and podcasts")
    logger.info("=" * 50)

    # The digest now runs once a month (on the 1st), so look back a full month
    # to cover every article published since the previous month's digest — never
    # just the past week. Use the larger initial-backfill window if it exceeds a
    # month (e.g. for the very first run).
    since = max(INITIAL_LOOKBACK_DAYS, MONTHLY_LOOKBACK_DAYS)

    all_articles = []
    for j in JOURNALS:
        all_articles.extend(fetch_articles(j, since_days=since))

    all_pods = []
    for j in JOURNALS:
        all_pods.extend(fetch_podcast_episodes(j, max_episodes=1))
    bonus = fetch_bonus_podcasts(BONUS_PODCASTS, max_episodes=1)

    logger.info(f"Total: {len(all_articles)} articles, {len(all_pods)} podcast eps")

    # Cache the full set first so the month's review sees everything.
    _cache_articles(all_articles)

    # Digest email shows a tight selection: the single most clinically relevant
    # article per journal (chosen by Claude), capped at 10 total.
    selected = select_digest_articles(all_articles, per_journal=1, max_total=10)
    logger.info(f"Selected {len(selected)} articles for the digest email")

    # Save the EXACT final list emailed in this month's digest (overwrite). The
    # CME step reads only from this so it tests precisely these articles.
    _write_monday_featured(selected)

    # Rolling MOC log: append these articles (Google Sheets, or xlsx fallback).
    if not preview:
        _track_digest(selected)

    # API mode: generate the two-host audio podcast from the same selection so
    # the audio summary matches the articles shown in the email, then publish
    # it to GitHub Pages for inline playback.
    has_audio = False
    podcast_url = None
    if MODE == "api" and selected:
        try:
            from podcast_generator import generate_podcast
            audio_name = f"Anesthesia_Digest_{datetime.now().strftime('%Y_%m_%d')}.mp3"
            audio_file = generate_podcast(selected, output_path=audio_name)
            if audio_file:
                from publisher import publish_episode
                # In preview mode, build the docs/ files but don't push.
                podcast_url = publish_episode(audio_file, datetime.now(),
                                              push=not preview)
                has_audio = podcast_url is not None
        except Exception as e:
            logger.error(f"Podcast generation/publishing failed: {e}")

    # API mode: generate the structured "Deep Dive" summaries for each featured
    # article, publish them as one dated GitHub Pages page, and persist them so
    # Saturday's CME can reuse them. Bottom-line teasers go inline in the email.
    summaries = None
    deepdive_url = None
    if MODE == "api" and selected:
        try:
            from summary_generator import generate_summaries
            summaries = generate_summaries(selected)
        except Exception as e:
            logger.error(f"Deep Dive summary generation failed: {e}")
        if summaries:
            try:
                from publisher import publish_deepdive
                deepdive_url = publish_deepdive(summaries, datetime.now(),
                                                push=not preview)
            except Exception as e:
                logger.error(f"Deep Dive publishing failed: {e}")
    if not preview:
        _write_weekly_summaries(summaries, deepdive_url)

    # Build and send. The podcast is played inline via GitHub Pages, so the MP3
    # is no longer attached to the email.
    subject, html = build_digest_email(selected, all_pods, bonus,
                                       has_audio=has_audio,
                                       podcast_url=podcast_url,
                                       deepdive_url=deepdive_url,
                                       summaries=summaries)

    if preview:
        _save(subject, html, "digest")
    else:
        send_email(RECIPIENT_EMAIL, subject, html, SENDER_EMAIL)


def run_saturday(preview=False):
    """CME self-assessment built from EXACTLY this month's digest articles."""
    logger.info("=" * 50)
    logger.info("SELF-ASSESSMENT — CME for the month's articles")
    logger.info("=" * 50)

    # Locked to the month's digest: read ONLY the exact articles that were emailed
    # in this month's digest. No re-fetching, no newly-appeared articles.
    week = _load_monday_featured()
    logger.info(f"Monthly digest articles: {len(week)} "
                f"(locked to {MONDAY_FEATURED_FILE})")

    # The digest's Deep Dive summaries + page URL (for CME grounding and the link).
    wk = _load_weekly_summaries()
    summaries = wk.get("summaries") or None
    deepdive_url = wk.get("deepdive_url") or None

    # Free mode has no CME — just a highlights review of the month's set.
    if MODE != "api":
        subject, html = build_saturday_email(week, cme_questions=None, quiz_url=None,
                                             deepdive_url=deepdive_url)
        if preview:
            _save(subject, html, "saturday")
        else:
            send_email(RECIPIENT_EMAIL, subject, html, SENDER_EMAIL)
        return

    # API mode: CME is required. Never send a question-less email — if anything
    # fails, flag it (non-zero exit) so the failure is visible instead of silent.
    if not week:
        logger.error(f"No digest articles in {MONDAY_FEATURED_FILE} — "
                     "run the digest first. NOT sending a CME email.")
        if not preview:
            sys.exit(1)
        return

    cme = None
    try:
        from cme_generator import generate_cme_questions
        # One question per featured article (no repeats). Usually 10; fewer if a
        # journal had no open-access article that month. Grounded in the digest's
        # Deep Dive summaries when available (Option B), else cached full text.
        cme = generate_cme_questions(week, num_questions=len(week),
                                     summaries=summaries)
    except Exception as e:
        logger.error(f"CME generation raised: {e}")

    if not cme:
        logger.error("CME generation failed (no questions produced) — "
                     "NOT sending a question-less email.")
        if not preview:
            sys.exit(1)
        return

    if not preview:
        _track_cme(cme)

    quiz_url = None
    try:
        from publisher import publish_cme_quiz
        quiz_url = publish_cme_quiz(cme, datetime.now(), push=not preview)
    except Exception as e:
        logger.error(f"CME quiz publishing failed: {e}")

    subject, html = build_saturday_email(week, cme_questions=cme, quiz_url=quiz_url,
                                         deepdive_url=deepdive_url)
    if preview:
        _save(subject, html, "saturday")
    else:
        send_email(RECIPIENT_EMAIL, subject, html, SENDER_EMAIL)


def run_monthly(preview=False):
    """1st of month: top 5 articles + MOC tracker attachment."""
    logger.info("=" * 50)
    logger.info("MONTHLY — digest and MOC update")
    logger.info("=" * 50)

    all_articles = []
    for j in JOURNALS:
        all_articles.extend(fetch_articles(j, since_days=30))

    logger.info(f"Month's articles: {len(all_articles)}")

    # Prioritize: open access first, then by impact factor
    oa = sorted([a for a in all_articles if a["is_open_access"]],
                key=lambda a: a["impact_factor"], reverse=True)
    rest = sorted([a for a in all_articles if not a["is_open_access"]],
                  key=lambda a: a["impact_factor"], reverse=True)
    ranked = oa + rest
    top5 = ranked[:5]

    # MOC: live Google Sheet (Monthly Top 5 + summary) or local xlsx fallback.
    used_google = _track_monthly(ranked[:20])

    subject, html = build_monthly_email(all_articles, top5)

    # Attach the local xlsx only in fallback mode (Google sheet is the live copy).
    attachments = [] if used_google else [MOC_FILE]
    if preview:
        _save(subject, html, "monthly")
    else:
        send_email(RECIPIENT_EMAIL, subject, html, SENDER_EMAIL,
                   attachments=attachments)


# ── MOC tracking (Google Sheets, with local xlsx fallback) ───────────────────

def _track_digest(selected: list):
    """Append featured articles to the live MOC sheet, or the xlsx fallback."""
    today = datetime.now().strftime("%Y-%m-%d")
    if gsheets.is_configured():
        try:
            url = gsheets.log_digest(selected, today)
            logger.info(f"MOC mode: Google Sheets (live) → {url}")
            return
        except Exception as e:
            logger.error(f"Google Sheets MOC failed ({e}); falling back to local xlsx")
    else:
        logger.info("MOC mode: local xlsx (Google not configured)")
    try:
        log_articles(selected)
    except Exception as e:
        logger.error(f"Local xlsx MOC fallback failed: {e}")


def _track_cme(cme: list):
    """Append a CME Log row to the live MOC sheet, or the xlsx fallback."""
    today = datetime.now().strftime("%Y-%m-%d")
    if gsheets.is_configured():
        try:
            url = gsheets.log_cme(today, len(cme))
            logger.info(f"MOC mode: Google Sheets (live) → {url}")
            return
        except Exception as e:
            logger.error(f"Google Sheets CME log failed ({e}); falling back to local xlsx")
    else:
        logger.info("MOC mode: local xlsx (Google not configured)")
    try:
        log_cme(cme)
    except Exception as e:
        logger.error(f"Local xlsx CME fallback failed: {e}")


def _track_monthly(fallback_articles: list) -> bool:
    """Refresh the live Summary & Report in Google Sheets. Returns True if the
    Google path was used; False means the xlsx fallback ran (attach it)."""
    if gsheets.is_configured():
        try:
            url = gsheets.refresh_summary()
            logger.info(f"MOC mode: Google Sheets (live) → {url}")
            return True
        except Exception as e:
            logger.error(f"Google Sheets monthly update failed ({e}); falling back to xlsx")
    else:
        logger.info("MOC mode: local xlsx (Google not configured)")
    try:
        log_articles(fallback_articles)
        update_summary()
    except Exception as e:
        logger.error(f"Local xlsx monthly fallback failed: {e}")
    return False


# ── Cache ────────────────────────────────────────────────────────────────────

def _cache_articles(articles: list):
    cache = _load_cache_raw()
    seen = {a["url"] for a in cache}
    for art in articles:
        if art["url"] not in seen:
            copy = dict(art)
            if isinstance(copy.get("date"), datetime):
                copy["date"] = copy["date"].isoformat()
            cache.append(copy)
    Path(CACHE_FILE).write_text(json.dumps(cache, default=str), encoding="utf-8")


def _load_cache_raw() -> list:
    p = Path(CACHE_FILE)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def _load_cached(days=7) -> list:
    cutoff = datetime.now() - timedelta(days=days)
    out = []
    for art in _load_cache_raw():
        try:
            d = datetime.fromisoformat(art["date"]) if art.get("date") else None
            if d and d >= cutoff:
                out.append(art)
        except (ValueError, TypeError):
            out.append(art)
    return out


def _write_monday_featured(selected: list):
    """Overwrite monday_featured.json with the EXACT list emailed this month."""
    out = []
    for art in selected:
        copy = dict(art)
        if isinstance(copy.get("date"), datetime):
            copy["date"] = copy["date"].isoformat()
        out.append(copy)
    Path(MONDAY_FEATURED_FILE).write_text(json.dumps(out, default=str),
                                          encoding="utf-8")
    logger.info(f"Saved {len(out)} Monday featured articles → {MONDAY_FEATURED_FILE}")


def _load_monday_featured() -> list:
    """Load the exact monthly digest article list (or [] if none yet)."""
    p = Path(MONDAY_FEATURED_FILE)
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []


def _write_weekly_summaries(summaries: list | None, deepdive_url: str | None):
    """Persist the digest's Deep Dive summaries + page URL for the CME step."""
    payload = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "deepdive_url": deepdive_url,
        "summaries": summaries or [],
    }
    Path(WEEKLY_SUMMARIES_FILE).write_text(json.dumps(payload, default=str),
                                           encoding="utf-8")
    logger.info(f"Saved {len(summaries or [])} Deep Dive summaries → "
                f"{WEEKLY_SUMMARIES_FILE}")


def _load_weekly_summaries() -> dict:
    """Load the digest's Deep Dive summaries payload (or {} if none yet)."""
    p = Path(WEEKLY_SUMMARIES_FILE)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(subject, html, label):
    f = f"preview_{label}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    Path(f).write_text(html, encoding="utf-8")
    logger.info(f"Preview: {f} (Subject: {subject})")


# ── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1].lower()
    cmds = {
        "digest": lambda: run_digest(preview=False),
        "saturday": lambda: run_saturday(preview=False),
        "monthly": lambda: run_monthly(preview=False),
        "preview": lambda: run_digest(preview=True),
        "preview-sat": lambda: run_saturday(preview=True),
        "preview-month": lambda: run_monthly(preview=True),
    }

    if cmd in cmds:
        cmds[cmd]()
    else:
        print(f"Unknown: {cmd}\n{__doc__}")
        sys.exit(1)
