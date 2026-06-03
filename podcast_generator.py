"""
Anesthesia Journal Digest — AI Two-Host Podcast Generator
==========================================================
1. Claude API writes a natural two-host conversation (Host A + Host B),
   NotebookLM-style, covering ALL of today's selected articles.
2. Edge TTS renders Host A with one voice and Host B with another.
3. pydub stitches the segments in order and mixes in intro / outro music.

Cost: ~$0.01-0.04 per episode (Claude API only; Edge TTS is free).
Requires the ffmpeg/ffprobe binaries on PATH for the two-host stitch+music mix
(the CI workflow installs them via apt; `brew install ffmpeg` on a Mac). If they
are missing it degrades to a single-voice file instead of producing nothing.
"""

import os
import re
import shutil
import asyncio
import logging
import tempfile
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


def generate_podcast(articles: list, output_path: str = "podcast.mp3") -> str | None:
    """Generate a ~15-minute two-host audio podcast from today's articles.

    Args:
        articles: List of article dicts from the fetcher/selector.
        output_path: Where to save the final MP3.

    Returns:
        Path to the MP3 file, or None if generation failed.
    """
    if not articles:
        logger.warning("No articles to generate podcast from")
        return None

    # Step 1: two-host script as an ordered list of (speaker, text) turns.
    turns = _generate_script(articles)
    if not turns:
        return None

    # Save a readable transcript for reference.
    script_path = output_path.replace(".mp3", "_script.txt")
    transcript = "\n\n".join(f"{'Host A' if s == 'A' else 'Host B'}: {t}"
                             for s, t in turns)
    Path(script_path).write_text(transcript, encoding="utf-8")
    word_count = len(transcript.split())
    logger.info(f"Script saved: {script_path} ({word_count} words, {len(turns)} turns)")

    # Step 2 + 3: synthesize each turn and stitch with music.
    return _render_audio(turns, output_path)


# ── Script generation ────────────────────────────────────────────────────────

def _generate_script(articles: list) -> list[tuple[str, str]] | None:
    """Call Claude to write a two-host conversational script.

    Returns an ordered list of (speaker, text) tuples where speaker is "A"/"B".
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        from config import ANTHROPIC_API_KEY
        api_key = ANTHROPIC_API_KEY
    if not api_key:
        logger.error("No ANTHROPIC_API_KEY found. Set it as an environment variable.")
        return None

    from config import CLAUDE_MODEL, PODCAST_WORD_TARGET

    # Use up to 10 articles — the script must cover ALL of them.
    articles = articles[:10]
    briefs = []
    for i, art in enumerate(articles, 1):
        brief = f"{i}. [{art['journal_abbr']}] {art['title']}"
        if art.get("authors"):
            brief += f"\n   Authors: {art['authors']}"
        if art.get("abstract"):
            brief += f"\n   Abstract: {art['abstract'][:500]}"
        if art.get("is_open_access"):
            brief += "\n   [OPEN ACCESS — free full text]"
        briefs.append(brief)
    articles_text = "\n\n".join(briefs)
    n = len(articles)

    prompt = f"""You are writing the script for "Anesthesia Digest," a two-host \
audio podcast for practicing anesthesiologists, in the natural, conversational \
style of NotebookLM's Audio Overviews. Today is \
{datetime.now().strftime('%A, %B %d, %Y')}.

There are TWO hosts:
- Host A (warm, leads the discussion, sets up each topic)
- Host B (curious, asks sharp follow-up questions, adds clinical color)

TARGET LENGTH: about {PODCAST_WORD_TARGET} words total. This is important — it \
needs to fill roughly 15 minutes of listening. Do not stop short.

ARTICLES TO COVER (there are {n} — you MUST cover ALL {n}):
{articles_text}

HOW TO WRITE IT:
- Open with a short, friendly two-host intro: greet the listener, say the date,
  and tease what's in today's episode.
- Then walk through EVERY one of the {n} articles in turn. Spend a real
  back-and-forth of roughly 60-90 seconds on each — NOT a passing mention.
  For each: name the journal, explain what was studied, what they found, why it
  matters at the bedside, and any caveats. Note when an article is open access.
- Make it a genuine conversation: banter, follow-up questions, reactions
  ("Oh, that's interesting — so does that change what you'd do?"), natural
  transitions between articles ("Speaking of airways, the next one...").
- Use accessible, collegial language — two anesthesiologists talking shop.
- Close with a brief two-host sign-off.

FORMAT — this is critical. Output ONLY dialogue lines, each on its own line,
each beginning with exactly "A:" or "B:" and nothing else. No narration, no
stage directions, no markdown, no section headers, no brackets. Example:

A: Welcome to Anesthesia Digest for today, I'm here with my co-host...
B: Great to be here. We've got a packed episode...

Write the full script now."""

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
        text = "".join(b.get("text", "") for b in data.get("content", [])
                       if b.get("type") == "text")
        if not text.strip():
            logger.error("Claude API returned empty response")
            return None
        turns = _parse_turns(text)
        if not turns:
            logger.error("Could not parse any A:/B: turns from the script")
            return None
        logger.info(f"Script generated: {len(turns)} turns, "
                    f"{len(text.split())} words")
        return turns
    except Exception as e:
        logger.error(f"Claude API call failed: {e}")
        return None


def _parse_turns(text: str) -> list[tuple[str, str]]:
    """Parse 'A:'/'B:' (or 'Host A:') prefixed lines into ordered turns.

    Consecutive lines without a new speaker tag are appended to the current
    turn so wrapped paragraphs stay intact.
    """
    turns: list[list] = []
    speaker_re = re.compile(r"^\s*(?:host\s*)?([AB])\s*[:\-]\s*(.*)$", re.IGNORECASE)
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        m = speaker_re.match(line)
        if m:
            speaker = m.group(1).upper()
            turns.append([speaker, m.group(2).strip()])
        elif turns:
            turns[-1][1] += " " + line
    # Drop empty turns and collapse whitespace.
    out = []
    for speaker, body in turns:
        body = re.sub(r"\s+", " ", body).strip()
        if body:
            out.append((speaker, body))
    return out


# ── Audio rendering ──────────────────────────────────────────────────────────

def _render_audio(turns: list[tuple[str, str]], output_path: str) -> str | None:
    """Synthesize each turn with its host voice and stitch with music."""
    try:
        import edge_tts  # noqa: F401
    except ImportError:
        logger.error("edge_tts not installed. Run: pip install edge-tts")
        return None

    try:
        from pydub import AudioSegment
    except ImportError:
        logger.warning("pydub not installed — falling back to single-voice file")
        return _render_single_voice(turns, output_path)

    # pydub needs the ffmpeg/ffprobe binaries to read & mix MP3s. If they aren't
    # on PATH, multi-voice stitching cannot work — degrade to a single-voice
    # file (edge-tts writes MP3 directly, no ffmpeg needed) rather than produce
    # nothing.
    if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
        logger.warning("ffmpeg/ffprobe not found on PATH — falling back to "
                       "single-voice file (install ffmpeg for the two-host mix)")
        return _render_single_voice(turns, output_path)

    from config import HOST_A_VOICE, HOST_B_VOICE, TTS_RATE

    tmpdir = Path(tempfile.mkdtemp(prefix="anes_pod_"))
    try:
        segment_files = asyncio.run(
            _synth_all(turns, tmpdir, HOST_A_VOICE, HOST_B_VOICE, TTS_RATE)
        )
        segment_files = [f for f in segment_files if f]
        if not segment_files:
            logger.error("No audio segments were produced")
            return None

        gap = AudioSegment.silent(duration=180)  # natural beat between turns
        narration = AudioSegment.empty()
        for i, f in enumerate(segment_files):
            seg = AudioSegment.from_file(f)
            narration += seg
            if i < len(segment_files) - 1:
                narration += gap

        final = _mix_music(narration, AudioSegment)
        final.export(output_path, format="mp3")
        size_mb = Path(output_path).stat().st_size / (1024 * 1024)
        dur_min = len(final) / 60000
        logger.info(f"Audio generated: {output_path} "
                    f"({size_mb:.1f} MB, ~{dur_min:.1f} min)")
        return output_path
    except Exception as e:
        logger.error(f"Audio rendering failed: {e}")
        return None
    finally:
        for p in tmpdir.glob("*"):
            try:
                p.unlink()
            except OSError:
                pass
        try:
            tmpdir.rmdir()
        except OSError:
            pass


async def _synth_all(turns, tmpdir, voice_a, voice_b, rate, concurrency=6):
    """Render every turn to its own MP3 file concurrently, preserving order.

    Sequentially this is the slow step (~90 turns × a few seconds each blew past
    the CI timeout). Bounded concurrency cuts it several-fold; results[i] keeps
    strict turn order regardless of completion order. One retry per turn rides
    out transient Edge-TTS hiccups.
    """
    import edge_tts
    sem = asyncio.Semaphore(concurrency)
    results: list = [None] * len(turns)

    async def _one(i, speaker, body):
        voice = voice_a if speaker == "A" else voice_b
        out = tmpdir / f"seg_{i:03d}.mp3"
        async with sem:
            for attempt in (1, 2):
                try:
                    await edge_tts.Communicate(body, voice, rate=rate).save(str(out))
                    results[i] = out
                    return
                except Exception as e:
                    if attempt == 2:
                        logger.warning(f"TTS failed for turn {i} ({speaker}): {e}")
                    else:
                        await asyncio.sleep(1.5)

    await asyncio.gather(*(_one(i, s, b) for i, (s, b) in enumerate(turns)))
    done = sum(1 for r in results if r)
    logger.info(f"TTS rendered {done}/{len(turns)} turns")
    return results


def _mix_music(narration, AudioSegment):
    """Play intro music solo for 5-7s, crossfade into the hosts, then after the
    hosts finish crossfade into the outro and let it play solo for 5-7s.

    Music sits -12 dB under the voices; all transitions are smooth fades.
    """
    from config import (INTRO_MUSIC, OUTRO_MUSIC, MUSIC_DUCK_DB,
                        INTRO_SOLO_MS, OUTRO_SOLO_MS, MUSIC_CROSSFADE_MS)

    final = narration

    intro_path = Path(INTRO_MUSIC)
    if intro_path.exists():
        try:
            xf = min(MUSIC_CROSSFADE_MS, len(final))
            intro = AudioSegment.from_file(intro_path) + MUSIC_DUCK_DB
            # Clip = solo portion + the overlap that crossfades into the voices,
            # so the listener hears INTRO_SOLO_MS of music before anyone speaks.
            intro_clip = intro[:INTRO_SOLO_MS + xf].fade_in(1200)
            final = intro_clip.append(final, crossfade=xf)
            logger.info(f"Mixed in intro music (~{INTRO_SOLO_MS/1000:.0f}s solo)")
        except Exception as e:
            logger.warning(f"Intro music skipped: {e}")
    else:
        logger.info(f"No intro music at {INTRO_MUSIC} (optional)")

    outro_path = Path(OUTRO_MUSIC)
    if outro_path.exists():
        try:
            xf = min(MUSIC_CROSSFADE_MS, len(final))
            outro = AudioSegment.from_file(outro_path) + MUSIC_DUCK_DB
            # Overlap crossfades from the last words into the music, then the
            # music plays solo for OUTRO_SOLO_MS before fading out.
            outro_clip = outro[:OUTRO_SOLO_MS + xf].fade_out(2000)
            final = final.append(outro_clip, crossfade=xf)
            logger.info(f"Mixed in outro music (~{OUTRO_SOLO_MS/1000:.0f}s solo)")
        except Exception as e:
            logger.warning(f"Outro music skipped: {e}")
    else:
        logger.info(f"No outro music at {OUTRO_MUSIC} (optional)")

    return final


def _render_single_voice(turns, output_path) -> str | None:
    """Fallback when pydub is unavailable: one voice, no music, single file."""
    import edge_tts
    from config import TTS_VOICE, TTS_RATE

    script = " ".join(body for _, body in turns)

    async def _go():
        await edge_tts.Communicate(script, TTS_VOICE, rate=TTS_RATE).save(output_path)

    try:
        asyncio.run(_go())
        logger.info(f"Audio generated (single-voice fallback): {output_path}")
        return output_path
    except Exception as e:
        logger.error(f"Edge TTS failed: {e}")
        return None
