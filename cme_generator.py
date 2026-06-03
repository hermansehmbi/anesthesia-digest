"""
Anesthesia Journal Digest — CME Question Generator
====================================================
Uses Claude API to generate RCPSC-style CME questions from the week's articles.
For Section 2 (self-learning) and Section 3 (self-assessment) credits.
"""

import os
import re
import json
import random
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

_LETTERS = ["A", "B", "C", "D"]


def generate_cme_questions(articles: list, num_questions: int = 10) -> list[dict] | None:
    """
    Generate CME-style MCQs from the week's articles.

    Returns list of question dicts:
        {
            "question": str,
            "options": {"A": str, "B": str, "C": str, "D": str},
            "correct": "A|B|C|D",   # the letter of the correct option (randomized)
            "rationale": str,
            "source_article": str,
            "source_journal": str,
            "source_url": str,
            "rcpsc_section": "Section 2 & 3",
        }
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        from config import ANTHROPIC_API_KEY
        api_key = ANTHROPIC_API_KEY

    if not api_key:
        logger.error("No ANTHROPIC_API_KEY. Skipping CME generation.")
        return None

    if not articles:
        logger.warning("No articles for CME generation")
        return None

    from config import CLAUDE_MODEL, CME_SOURCE_CHARS

    # Pick the ~10 articles that will actually drive the quiz (need substance).
    candidates = [a for a in articles if len(a.get("abstract", "")) > 100]
    if not candidates:
        candidates = articles
    candidates = sorted(candidates, key=lambda a: a["impact_factor"],
                        reverse=True)[:num_questions]

    # Fetch (and cache) full text ONLY for these CME articles so explanations
    # can quote real statistics. Open access → parsed Results/Discussion/etc.;
    # paywalled → abstract only.
    try:
        from fulltext_fetcher import get_article_text
    except Exception:
        get_article_text = None

    briefs = []
    for i, art in enumerate(candidates, 1):
        info = {"source": "abstract", "text": art.get("abstract", "")}
        if get_article_text:
            try:
                info = get_article_text(art)
            except Exception as e:
                logger.warning(f"Full-text fetch failed for {art.get('url')}: {e}")

        body = (info.get("text") or art.get("abstract", "")).strip()
        if info.get("source") == "fulltext":
            access = "OPEN-ACCESS FULL TEXT (quote real numbers from the sections below)"
        elif body:
            access = ("ABSTRACT ONLY — paywalled. Describe direction/magnitude of "
                      "findings; do NOT invent any statistic not present below")
        else:
            access = "NO SOURCE TEXT AVAILABLE — keep the explanation qualitative"

        briefs.append(
            f"[{i}] Journal: {art['journal_abbr']} | Title: {art['title']}\n"
            f"URL: {art['url']}\n"
            f"Access: {access}\n"
            f"Source text:\n{body[:CME_SOURCE_CHARS]}"
        )
    articles_text = "\n\n".join(briefs)

    prompt = f"""You are writing CME (Continuing Medical Education) self-assessment questions
suitable for RCPSC (Royal College of Physicians and Surgeons of Canada) Maintenance of
Certification (Section 2 self-learning and Section 3 self-assessment).

TOPIC GUIDANCE (internal only — for choosing what to test): favor topics that matter at the
bedside for a generalist anesthesiologist (airway, analgesia, obstetric anesthesia, regional
techniques, perioperative management, patient safety).
HARD RULE: NEVER write the phrase "community anesthesiologist" (or "community anaesthetist",
or "community anesthetist") anywhere in a question, option, or explanation. That phrase is
internal guidance only and must not appear in the output.

ARTICLES FOR THIS WEEK (each has source text — full text if open access, otherwise abstract):
{articles_text}

Generate EXACTLY {num_questions} single-best-answer multiple-choice questions. For each:
1. Base it on a DIFFERENT article from the list above.
2. Write a REALISTIC CLINICAL VIGNETTE question with specific patient details (age, sex,
   comorbidities, procedure, doses, monitoring, or context) — e.g. "A 72-year-old undergoes
   elective hip arthroplasty under spinal anesthesia. Which intervention has the strongest
   evidence for reducing postoperative delirium?" Some may be focused knowledge questions,
   but most should be scenarios. Do NOT describe the target audience in the question.
3. Provide exactly 4 options (A-D): ONE clearly correct answer and three plausible
   distractors. Avoid "all/none of the above".
4. Write a full-paragraph explanation of ABOUT 10 LINES (8-12 sentences). It MUST:
   - quote ACTUAL effect sizes and statistics taken from that article's Source text above —
     the types of figures to look for are mean/median differences, relative risk, odds or
     hazard ratios, NNT, confidence intervals, p-values, and percentages, reported with the
     exact values found in that article's Source text;
   - explain WHY the correct choice is right, then why EACH of the other choices is wrong,
     REFERRING TO THE CHOICES BY THEIR CONTENT/WORDING, never by their letter (do not write
     "Option A/B/C/D"), because the option order will be randomized after generation;
   - end with the practical bedside takeaway.
   CRITICAL: Use ONLY numbers that actually appear in that article's Source text. Do NOT copy
   any numbers from these instructions. If the source is abstract-only or a specific number is
   not present, describe the direction and magnitude qualitatively instead. NEVER fabricate or
   guess statistics, confidence intervals, or p-values that are not in the provided text.
5. Reference the source article (use its exact title, journal, and URL from the list).
6. VARY which option is correct across the set — do not make the same letter correct every
   time. (The positions will also be shuffled afterwards as a safeguard.)

RESPOND IN THIS EXACT JSON FORMAT (no markdown, no backticks, just raw JSON):
[
  {{
    "question": "A 65-year-old ... <clinical vignette> ... Which ... ?",
    "options": {{
      "A": "<distinct option text>",
      "B": "<distinct option text>",
      "C": "<distinct option text>",
      "D": "<distinct option text>"
    }},
    "correct": "<the letter of the correct option>",
    "rationale": "<about 10 lines. State the article's real figures from its Source text. Explain why the correct choice is right and why each other choice is wrong, naming choices by their wording (not by letter). End with the bedside takeaway.>",
    "source_article": "Exact title of the source article",
    "source_journal": "<journal abbreviation>",
    "source_url": "https://..."
  }}
]

Generate exactly {num_questions} questions, each from a different article, at exam-level
difficulty, with statistics grounded ONLY in the provided source text."""

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
                "max_tokens": 8192,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=120,
        )
        response.raise_for_status()
        data = response.json()

        text = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                text += block["text"]

        # Parse JSON (strip any accidental markdown fences)
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
        text = text.strip()

        questions = json.loads(text)

        # Randomize the position of the correct option so there is no positional
        # bias (the model tends to favor one letter). This also remaps any stray
        # "Option X" references in the rationale to the new letters.
        _shuffle_options(questions)

        # Add RCPSC section tag
        for q in questions:
            q["rcpsc_section"] = "Section 2 & 3"

        dist = {L: sum(1 for q in questions if q.get("correct") == L) for L in _LETTERS}
        logger.info(f"Generated {len(questions)} CME questions; "
                    f"correct-answer distribution {dist}")
        return questions

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse CME JSON: {e}")
        logger.debug(f"Raw response: {text[:500]}")
        return None
    except Exception as e:
        logger.error(f"Claude API call failed for CME: {e}")
        return None


# ── Answer-position randomization ────────────────────────────────────────────

def _shuffle_options(questions: list, rng: random.Random | None = None) -> list:
    """Shuffle each question's A-D options in place and update the correct letter.

    Tracks the correct answer by its TEXT (not its letter), so after shuffling
    the ``correct`` field points at whichever letter now holds the right answer.
    Any explicit "Option X" letter references in the rationale are remapped to
    the new letters as a safety net (the prompt asks the model to avoid them).
    """
    rng = rng or random
    for q in questions:
        opts = q.get("options") or {}
        correct = q.get("correct")
        items = [(L, opts.get(L)) for L in _LETTERS if opts.get(L)]
        if len(items) < 2 or correct not in dict(items):
            continue

        correct_text = dict(items)[correct]
        texts = [t for _, t in items]
        rng.shuffle(texts)

        new_opts = {}
        new_correct = correct
        for i, t in enumerate(texts):
            L = _LETTERS[i]
            new_opts[L] = t
            if t == correct_text:
                new_correct = L

        # old letter -> new letter, matched by identical option text
        text_to_new = {t: _LETTERS[i] for i, t in enumerate(texts)}
        old_to_new = {oldL: text_to_new.get(t, oldL) for oldL, t in items}

        q["options"] = new_opts
        q["correct"] = new_correct
        q["rationale"] = _remap_letters(q.get("rationale", ""), old_to_new)
    return questions


# Match clear option-letter references like "Option B", "choice C", "answer is A".
_LETTER_REF_RE = re.compile(
    r"(?P<pre>\b[Oo]ptions?\s+|\b[Cc]hoices?\s+|\banswer(?:\s+is|:)?\s+)(?P<L>[A-D])\b")


def _remap_letters(text: str, mapping: dict) -> str:
    """Remap option-letter references in a rationale using old->new mapping.

    Uses a single pass so swaps never chain (e.g. A->C and C->A stay distinct).
    """
    if not text:
        return text

    def repl(m):
        return m.group("pre") + mapping.get(m.group("L"), m.group("L"))

    return _LETTER_REF_RE.sub(repl, text)
