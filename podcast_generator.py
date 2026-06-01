"""
Anesthesia Journal Digest — AI Podcast Generator
==================================================
Uses Claude API to write a podcast script, then Edge TTS to generate audio.
Total cost: ~$0.01-0.03 per episode (Claude API only; Edge TTS is free).
"""

import os
import json
import asyncio
import logging
import tempfile
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


def generate_podcast(articles: list, output_path: str = "podcast.mp3") -> str | None:
    """
    Generate a 5-10 minute audio podcast from today's articles.

    Args:
        articles: List of article dicts from fetcher
        output_path: Where to save the MP3

    Returns:
        Path to MP3 file, or None if generation failed
    """
    if not articles:
        logger.warning("No articles to generate podcast from")
        return None

    # Step 1: Generate the script via Claude API
    script = _generate_script(articles)
    if not script:
        return None

    # Save script for reference
    script_path = output_path.replace(".mp3", "_script.txt")
    Path(script_path).write_text(script, encoding="utf-8")
    logger.info(f"Script saved: {script_path} ({len(script.split())} words)")

    # Step 2: Convert to audio via Edge TTS
    audio_path = _text_to_speech(script, output_path)
    return audio_path


def _generate_script(articles: list) -> str | None:
    """Call Claude API to generate a conversational podcast script."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        from config import ANTHROPIC_API_KEY
        api_key = ANTHROPIC_API_KEY

    if not api_key:
        logger.error("No ANTHROPIC_API_KEY found. Set it as an environment variable.")
        return None

    from config import CLAUDE_MODEL, PODCAST_MINUTES_TARGET

    # Prepare article summaries for the prompt
    article_briefs = []
    for i, art in enumerate(articles[:15], 1):  # Cap at 15 articles
        brief = f"{i}. [{art['journal_abbr']}] {art['title']}"
        if art.get("authors"):
            brief += f"\n   Authors: {art['authors']}"
        if art.get("abstract"):
            brief += f"\n   Abstract: {art['abstract'][:300]}"
        if art.get("is_open_access"):
            brief += "\n   [OPEN ACCESS]"
        article_briefs.append(brief)

    articles_text = "\n\n".join(article_briefs)
    word_target = PODCAST_MINUTES_TARGET * 140  # ~140 words per minute for narration

    prompt = f"""You are a host of "Anesthesia Digest," a short daily audio podcast for practicing anesthesiologists. 
Write a podcast script for today's episode ({datetime.now().strftime('%A, %B %d, %Y')}).

TARGET LENGTH: {word_target} words (approximately {PODCAST_MINUTES_TARGET} minutes when read aloud).

ARTICLES TO COVER:
{articles_text}

INSTRUCTIONS:
- Write in first person as a single narrator (no "Host A / Host B" format)
- Open with a brief, warm greeting: "Welcome to Anesthesia Digest for [date]..."
- Cover the 4-6 most interesting/impactful articles in depth
- For each article: explain what the researchers found, why it matters clinically, and any practice implications
- Mention the journal name so listeners can look it up
- Mention if an article is open access (listeners can read the full text for free)
- Use conversational, accessible language — like explaining to a colleague over coffee
- Briefly mention remaining articles at the end ("Also worth noting from this week...")
- Close with "That's your Anesthesia Digest for today. Until next time."
- Do NOT include stage directions, sound effects, or [brackets]
- Write the FULL script, ready to be read aloud as-is

Write only the script text, nothing else."""

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
                "max_tokens": 4096,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()

        script = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                script += block["text"]

        if not script:
            logger.error("Claude API returned empty response")
            return None

        logger.info(f"Script generated: {len(script.split())} words")
        return script.strip()

    except Exception as e:
        logger.error(f"Claude API call failed: {e}")
        return None


def _text_to_speech(text: str, output_path: str) -> str | None:
    """Convert text to speech using Edge TTS (free, no API key needed)."""
    try:
        import edge_tts
    except ImportError:
        logger.error("edge_tts not installed. Run: pip install edge-tts")
        return None

    from config import TTS_VOICE

    async def _generate():
        communicate = edge_tts.Communicate(text, TTS_VOICE, rate="-5%")
        await communicate.save(output_path)

    try:
        asyncio.run(_generate())
        size_mb = Path(output_path).stat().st_size / (1024 * 1024)
        logger.info(f"Audio generated: {output_path} ({size_mb:.1f} MB)")
        return output_path
    except Exception as e:
        logger.error(f"Edge TTS failed: {e}")
        return None
