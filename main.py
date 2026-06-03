"""
Anesthesia Journal Digest — Main
==================================
Usage:
    python main.py digest          # Monday weekly article digest
    python main.py saturday        # Saturday CME + week highlights
    python main.py monthly         # Monthly top-5 + MOC tracker
    python main.py preview         # Preview digest locally (no email)
    python main.py preview-sat     # Preview Saturday email locally
    python main.py preview-month   # Preview monthly email locally
"""

import sys
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

from config import (
    JOURNALS, BONUS_PODCASTS, RECIPIENT_EMAIL, SENDER_EMAIL,
    MODE, INITIAL_LOOKBACK_DAYS,
)
from fetcher import fetch_articles, fetch_podcast_episodes, fetch_bonus_podcasts
from article_selector import select_digest_articles
from email_builder import build_digest_email, build_saturday_email, build_monthly_email
from email_sender import send_email
from moc_tracker import log_articles, log_cme, update_summary, MOC_FILE

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

CACHE_FILE = "articles_cache.json"
FEATURED_FILE = "featured_cache.json"  # only the articles actually shown in a digest


def run_digest(preview=False):
    """Monday (weekly): articles + podcasts + audio (if API mode)."""
    logger.info("=" * 50)
    logger.info("DIGEST — fetching articles and podcasts")
    logger.info("=" * 50)

    since = INITIAL_LOOKBACK_DAYS
    # The digest runs once a week (Monday), so once past the initial backfill
    # period look back a full week to cover everything since the last digest.
    if since <= 7:
        since = 7

    all_articles = []
    for j in JOURNALS:
        all_articles.extend(fetch_articles(j, since_days=since))

    all_pods = []
    for j in JOURNALS:
        all_pods.extend(fetch_podcast_episodes(j, max_episodes=1))
    bonus = fetch_bonus_podcasts(BONUS_PODCASTS, max_episodes=1)

    logger.info(f"Total: {len(all_articles)} articles, {len(all_pods)} podcast eps")

    # Cache the full set first so Saturday's weekly review sees everything.
    _cache_articles(all_articles)

    # Digest email shows a tight selection: the single most clinically relevant
    # article per journal (chosen by Claude), capped at 10 total.
    selected = select_digest_articles(all_articles, per_journal=1, max_total=10)
    logger.info(f"Selected {len(selected)} articles for the digest email")

    # Record exactly what was featured this week so Saturday's CME quiz can be
    # built from the articles the reader actually saw (not the full fetch).
    if not preview:
        _cache_featured(selected)

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

    # Build and send. The podcast is played inline via GitHub Pages, so the MP3
    # is no longer attached to the email.
    subject, html = build_digest_email(selected, all_pods, bonus,
                                       has_audio=has_audio,
                                       podcast_url=podcast_url)

    if preview:
        _save(subject, html, "digest")
    else:
        send_email(RECIPIENT_EMAIL, subject, html, SENDER_EMAIL)


def run_saturday(preview=False):
    """Saturday: week's highlights + CME questions (if API mode)."""
    logger.info("=" * 50)
    logger.info("SATURDAY — CME and weekly review")
    logger.info("=" * 50)

    # CME quiz is built from the articles actually FEATURED in this week's
    # Monday digests, so the quiz tests what was emailed. Fall back to
    # the full weekly cache (or a fresh fetch) only if no featured set exists.
    week = _load_featured(days=7)
    source = "featured digest articles"
    if not week:
        week = _load_cached(days=7)
        source = "weekly article cache (no featured set found)"
    if not week:
        logger.info("Cache empty — fetching last 7 days")
        for j in JOURNALS:
            week.extend(fetch_articles(j, since_days=7))
        source = "fresh 7-day fetch"

    logger.info(f"Week's articles: {len(week)} (from {source})")

    # API mode: generate 10 CME questions and publish an interactive quiz page.
    cme = None
    quiz_url = None
    if MODE == "api" and week:
        try:
            from cme_generator import generate_cme_questions
            cme = generate_cme_questions(week, num_questions=10)
            if cme:
                # Log CME to MOC tracker
                log_cme(cme)
                # Publish the interactive quiz to GitHub Pages.
                try:
                    from publisher import publish_cme_quiz
                    quiz_url = publish_cme_quiz(cme, datetime.now(),
                                                push=not preview)
                except Exception as e:
                    logger.error(f"CME quiz publishing failed: {e}")
        except Exception as e:
            logger.error(f"CME generation failed: {e}")

    subject, html = build_saturday_email(week, cme_questions=cme, quiz_url=quiz_url)

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

    # Update MOC tracker
    log_articles(ranked[:20])
    update_summary()

    subject, html = build_monthly_email(all_articles, top5)

    if preview:
        _save(subject, html, "monthly")
    else:
        send_email(RECIPIENT_EMAIL, subject, html, SENDER_EMAIL,
                   attachments=[MOC_FILE])


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


def _cache_featured(selected: list):
    """Append the articles featured in a digest, stamped with featured_at, so
    Saturday can rebuild the week's set. De-duplicated by URL."""
    p = Path(FEATURED_FILE)
    existing = []
    if p.exists():
        try:
            existing = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            existing = []
    seen = {a.get("url") for a in existing}
    stamp = datetime.now().isoformat()
    for art in selected:
        if art.get("url") in seen:
            continue
        copy = dict(art)
        if isinstance(copy.get("date"), datetime):
            copy["date"] = copy["date"].isoformat()
        copy["featured_at"] = stamp
        existing.append(copy)
        seen.add(art.get("url"))
    p.write_text(json.dumps(existing, default=str), encoding="utf-8")
    logger.info(f"Recorded {len(selected)} featured articles → {FEATURED_FILE}")


def _load_featured(days=7) -> list:
    """Load featured articles whose featured_at is within the window."""
    p = Path(FEATURED_FILE)
    if not p.exists():
        return []
    try:
        items = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []
    cutoff = datetime.now() - timedelta(days=days)
    out = []
    for art in items:
        fa = art.get("featured_at")
        try:
            if fa and datetime.fromisoformat(fa) >= cutoff:
                out.append(art)
        except (ValueError, TypeError):
            continue
    return out


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
