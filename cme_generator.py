"""
Anesthesia Journal Digest — CME Question Generator
====================================================
Uses Claude API to generate RCPSC-style CME questions from the week's articles.
For Section 2 (self-learning) and Section 3 (self-assessment) credits.
"""

import os
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def generate_cme_questions(articles: list, num_questions: int = 10) -> list[dict] | None:
    """
    Generate CME-style MCQs from the week's articles.

    Returns list of question dicts:
        {
            "question": str,
            "options": {"A": str, "B": str, "C": str, "D": str},
            "correct": "B",
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

    from config import CLAUDE_MODEL

    # Pick articles with best abstracts (need substance for good questions)
    candidates = [a for a in articles if len(a.get("abstract", "")) > 100]
    if not candidates:
        candidates = articles
    candidates = sorted(candidates, key=lambda a: a["impact_factor"], reverse=True)[:15]

    # Build article summaries for prompt
    briefs = []
    for i, art in enumerate(candidates, 1):
        briefs.append(
            f"{i}. [{art['journal_abbr']}] {art['title']}\n"
            f"   URL: {art['url']}\n"
            f"   Abstract: {art['abstract'][:400]}"
        )
    articles_text = "\n\n".join(briefs)

    prompt = f"""You are creating CME (Continuing Medical Education) questions for a practicing
COMMUNITY anesthesiologist (general OR lists, obstetrics, regional, acute pain — not a
subspecialty researcher), suitable for RCPSC (Royal College of Physicians and Surgeons of
Canada) Maintenance of Certification.

These questions should be appropriate for:
- Section 2 credits (self-learning): questions that prompt reflection on practice
- Section 3 credits (self-assessment): knowledge-testing questions with feedback

ARTICLES FROM THIS WEEK:
{articles_text}

Generate EXACTLY {num_questions} single-best-answer multiple-choice questions. For each:
1. Base it on a specific article from the list above (use a DIFFERENT article when possible).
2. Write a single-best-answer question — ideally a brief clinical scenario — that matters at
   the bedside for a community anesthesiologist.
3. Provide exactly 4 options (A-D) with ONE clearly correct answer and three plausible
   distractors. Avoid "all/none of the above".
4. Write a thorough explanation of 5 to 10 lines (sentences): explain clearly WHY the correct
   answer is right, then briefly why each of the other three options is wrong, and tie it back
   to the clinical takeaway. This is the teaching point — make it substantive.
5. Reference the source article.

RESPOND IN THIS EXACT JSON FORMAT (no markdown, no backticks, just raw JSON):
[
  {{
    "question": "A 65-year-old patient undergoing...",
    "options": {{
      "A": "Option text",
      "B": "Option text",
      "C": "Option text",
      "D": "Option text"
    }},
    "correct": "B",
    "rationale": "The correct answer is B because... Option A is incorrect because... Option C is wrong because... Option D does not apply because... Clinically, this means...",
    "source_article": "Title of the source article",
    "source_journal": "BJA",
    "source_url": "https://..."
  }}
]

Generate exactly {num_questions} questions. Make them clinically relevant and exam-level
difficulty, with each explanation 5-10 lines long."""

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

        # Add RCPSC section tag
        for q in questions:
            q["rcpsc_section"] = "Section 2 & 3"

        logger.info(f"Generated {len(questions)} CME questions")
        return questions

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse CME JSON: {e}")
        logger.debug(f"Raw response: {text[:500]}")
        return None
    except Exception as e:
        logger.error(f"Claude API call failed for CME: {e}")
        return None
