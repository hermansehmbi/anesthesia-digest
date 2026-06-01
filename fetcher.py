"""
Anesthesia Journal Digest — RSS & Podcast Fetcher
"""

import re
import feedparser
import logging
from datetime import datetime, timedelta
from typing import Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

USER_AGENT = "AnesthesiaDigest/1.0 (Academic RSS aggregator)"


def fetch_articles(journal: dict, since_days: int = 4) -> list[dict]:
    """Fetch recent articles from a journal's RSS feed."""
    articles = []
    for url_key in ["rss_url", "rss_url_inpress"]:
        rss_url = journal.get(url_key)
        if not rss_url:
            continue

        logger.info(f"Fetching: {journal['abbreviation']} ({url_key})")
        try:
            feed = feedparser.parse(rss_url, agent=USER_AGENT)
        except Exception as e:
            logger.error(f"  Failed: {e}")
            continue

        if feed.bozo and not feed.entries:
            logger.warning(f"  Feed error: {feed.bozo_exception}")
            continue

        cutoff = datetime.now() - timedelta(days=since_days)
        seen_urls = {a["url"] for a in articles}

        for entry in feed.entries:
            pub_date = _parse_date(entry)
            if pub_date and pub_date < cutoff:
                continue
            url = entry.get("link", "")
            if url in seen_urls:
                continue

            articles.append({
                "title": _clean(entry.get("title", "Untitled")),
                "authors": _authors(entry),
                "url": url,
                "doi": _doi(entry),
                "date": pub_date,
                "date_str": pub_date.strftime("%Y-%m-%d") if pub_date else "Recent",
                "abstract": _clean(entry.get("summary", "")),
                "is_open_access": _is_oa(entry, journal["publisher"]),
                "journal": journal["name"],
                "journal_abbr": journal["abbreviation"],
                "impact_factor": journal["impact_factor"],
            })
            seen_urls.add(url)

    logger.info(f"  → {len(articles)} articles from {journal['abbreviation']}")
    return articles


def fetch_podcast_episodes(journal: dict, max_episodes: int = 1) -> list[dict]:
    """Fetch latest podcast episodes for a journal."""
    podcast = journal.get("podcast")
    if not podcast or not podcast.get("rss_url"):
        return []

    logger.info(f"Podcast: {podcast['name']}")
    try:
        feed = feedparser.parse(podcast["rss_url"], agent=USER_AGENT)
    except Exception as e:
        logger.error(f"  Failed: {e}")
        return []

    episodes = []
    for entry in feed.entries[:max_episodes]:
        audio_url = ""
        for link in entry.get("enclosures", []) + entry.get("links", []):
            if "audio" in link.get("type", ""):
                audio_url = link.get("href", "")
                break

        pub = _parse_date(entry)
        episodes.append({
            "title": _clean(entry.get("title", "Untitled")),
            "url": entry.get("link", audio_url),
            "audio_url": audio_url,
            "date_str": pub.strftime("%Y-%m-%d") if pub else "Recent",
            "duration": entry.get("itunes_duration", ""),
            "description": _clean(entry.get("summary", ""))[:250],
            "podcast_name": podcast["name"],
            "journal_abbr": journal["abbreviation"],
            "website": podcast.get("website", ""),
        })
    return episodes


def fetch_bonus_podcasts(bonus_list: list, max_episodes: int = 1) -> list[dict]:
    """Fetch episodes from non-journal podcasts like ASA Central Line."""
    episodes = []
    for pod in bonus_list:
        if not pod.get("rss_url"):
            continue
        try:
            feed = feedparser.parse(pod["rss_url"], agent=USER_AGENT)
            for entry in feed.entries[:max_episodes]:
                audio_url = ""
                for link in entry.get("enclosures", []) + entry.get("links", []):
                    if "audio" in link.get("type", ""):
                        audio_url = link.get("href", "")
                        break
                pub = _parse_date(entry)
                episodes.append({
                    "title": _clean(entry.get("title", "Untitled")),
                    "url": entry.get("link", audio_url),
                    "audio_url": audio_url,
                    "date_str": pub.strftime("%Y-%m-%d") if pub else "Recent",
                    "duration": entry.get("itunes_duration", ""),
                    "description": _clean(entry.get("summary", ""))[:250],
                    "podcast_name": pod["name"],
                    "journal_abbr": "",
                    "website": pod.get("website", ""),
                })
        except Exception as e:
            logger.error(f"Bonus podcast {pod['name']} failed: {e}")
    return episodes


# ── Helpers ──────────────────────────────────────────────────────────────────

def _parse_date(entry) -> Optional[datetime]:
    for field in ["published_parsed", "updated_parsed", "created_parsed"]:
        parsed = entry.get(field)
        if parsed:
            try:
                return datetime(*parsed[:6])
            except (TypeError, ValueError):
                continue
    for field in ["published", "updated", "dc_date"]:
        s = entry.get(field, "")
        if s:
            for fmt in ["%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z",
                        "%Y-%m-%d", "%a, %d %b %Y %H:%M:%S %z",
                        "%a, %d %b %Y %H:%M:%S GMT"]:
                try:
                    return datetime.strptime(s.strip(), fmt)
                except ValueError:
                    continue
    return None


def _clean(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    for old, new in [("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"),
                     ("&quot;", '"'), ("&#39;", "'")]:
        text = text.replace(old, new)
    return text


def _authors(entry) -> str:
    authors = entry.get("authors", [])
    if authors:
        names = [a.get("name", "") for a in authors if a.get("name")]
        if names:
            return "; ".join(names[:4]) + (" et al." if len(names) > 4 else "")
    return entry.get("author", "") or entry.get("dc_creator", "")


def _doi(entry) -> str:
    for field in ["prism_doi", "dc_identifier"]:
        val = entry.get(field, "")
        if val and "10." in val:
            return val
    for field in ["link", "id"]:
        m = re.search(r"(10\.\d{4,}/[^\s]+)", entry.get(field, ""))
        if m:
            return m.group(1)
    return ""


def _is_oa(entry, publisher: str) -> bool:
    for field in ["rights", "dc_rights", "prism_copyright", "license"]:
        val = str(entry.get(field, "")).lower()
        if any(k in val for k in ["creative commons", "cc-by", "cc by", "open access"]):
            return True
    for tag in entry.get("tags", []):
        if "open access" in str(tag.get("term", "")).lower():
            return True
    if entry.get("openaccess") == "1":
        return True
    return False
