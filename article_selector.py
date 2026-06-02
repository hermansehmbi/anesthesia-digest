"""
Anesthesia Journal Digest — Smart Article Selection
====================================================
For each journal with multiple new articles, ask the Claude API to pick the
ONE most clinically relevant article for a practicing COMMUNITY anesthesiologist.

Selection priorities (high → low):
  HIGH  randomized controlled trials, systematic reviews, meta-analyses,
        clinical practice guidelines, consensus statements, and topics with
        direct bedside impact (analgesia, airway, obstetric anesthesia,
        perioperative management, regional techniques, patient safety)
  LOW   basic-science / animal studies (e.g. mouse models), bibliometric or
        methodology papers, editorials, and letters

Open access is used ONLY as a tiebreaker between two equally clinical articles.
Falls back to a sensible heuristic if the API is unavailable.
"""

import os
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def select_digest_articles(articles: list, per_journal: int = 1,
                           max_total: int = 10) -> list:
    """Pick the best article(s) per journal, capped at ``max_total`` total.

    Uses Claude to choose the single most clinically relevant article from each
    journal that has more than one candidate. Journals are then ordered by
    impact factor to fill the limited slots.
    """
    by_journal = {}
    for a in articles:
        by_journal.setdefault(a["journal_abbr"], []).append(a)

    api_key = _api_key()

    selected = []
    for abbr, arts in by_journal.items():
        if len(arts) <= per_journal:
            selected.extend(arts)
            continue

        chosen = None
        if api_key and per_journal == 1:
            chosen = _claude_pick(arts, api_key)
        if chosen is not None:
            selected.append(chosen)
        else:
            # Heuristic fallback: clinical keywords first, then open access,
            # then most recent.
            ranked = sorted(arts, key=_heuristic_key, reverse=True)
            selected.extend(ranked[:per_journal])

    # Highest-impact journals fill the limited slots first.
    selected.sort(key=lambda a: a["impact_factor"], reverse=True)
    return selected[:max_total]


# ── Claude-driven pick ───────────────────────────────────────────────────────

def _claude_pick(articles: list, api_key: str) -> dict | None:
    """Ask Claude to choose the single most clinically relevant article."""
    from config import CLAUDE_MODEL

    briefs = []
    for i, art in enumerate(articles, 1):
        brief = f"[{i}] {art['title']}"
        if art.get("abstract"):
            brief += f"\n    Abstract: {art['abstract'][:600]}"
        if art.get("is_open_access"):
            brief += "\n    (open access)"
        briefs.append(brief)
    candidates = "\n\n".join(briefs)

    prompt = f"""You are the editor of a digest for a practicing COMMUNITY \
anesthesiologist (general OR list, obstetrics, regional, acute pain — not a \
researcher). From the candidate articles below, all from the same journal, \
pick the ONE single most clinically relevant article for that reader.

PRIORITIZE (most valuable first):
- Randomized controlled trials
- Systematic reviews and meta-analyses
- Clinical practice guidelines and consensus statements
- Topics with direct bedside impact: analgesia, airway, obstetric anesthesia,
  perioperative management, regional techniques, patient safety

DEPRIORITIZE (rarely pick these):
- Basic science or animal studies (e.g. mouse models)
- Bibliometric, scientometric, or methodology papers
- Editorials, commentaries, and letters

Open access should ONLY break a tie between two articles that are otherwise
equally clinically relevant. Do not let open access outweigh clinical value.

CANDIDATE ARTICLES:
{candidates}

Respond with ONLY raw JSON, no markdown:
{{"choice": <number>, "reason": "<one short sentence>"}}"""

    try:
        import httpx
        response = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": CLAUDE_MODEL,
                "max_tokens": 256,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
        text = "".join(b.get("text", "") for b in data.get("content", [])
                       if b.get("type") == "text").strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        result = json.loads(text)
        idx = int(result.get("choice", 0)) - 1
        if 0 <= idx < len(articles):
            abbr = articles[idx]["journal_abbr"]
            logger.info(f"  {abbr}: picked #{idx+1} — {result.get('reason', '')}")
            return articles[idx]
    except Exception as e:
        logger.warning(f"  Claude article pick failed ({e}); using heuristic")
    return None


# ── Heuristic fallback ───────────────────────────────────────────────────────

_CLINICAL_KEYWORDS = (
    "randomi", "systematic review", "meta-analysis", "meta analysis",
    "guideline", "consensus", "trial", "analgesi", "airway", "obstetric",
    "perioperative", "regional", "block", "safety", "spinal", "epidural",
    "postoperative", "sedation",
)
_DEPRIORITIZE_KEYWORDS = (
    "mouse", "murine", "rat ", "rodent", "in vitro", "bibliometric",
    "scientometric", "editorial", "letter to", "erratum", "correction",
    "methodolog",
)


def _heuristic_key(art: dict):
    """Score an article without the API: clinical signal, then OA, then date."""
    text = f"{art.get('title', '')} {art.get('abstract', '')}".lower()
    score = sum(1 for k in _CLINICAL_KEYWORDS if k in text)
    score -= sum(2 for k in _DEPRIORITIZE_KEYWORDS if k in text)
    return (score, bool(art.get("is_open_access")), art.get("date") or datetime.min)


def _api_key() -> str:
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        try:
            from config import ANTHROPIC_API_KEY
            key = ANTHROPIC_API_KEY
        except Exception:
            key = ""
    return key
