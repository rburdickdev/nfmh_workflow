import json
import logging
import re

import httpx

from app.core.config import get_settings
from app.providers.base import AIAnalysisProvider, ClipSuggestion
from app.services.chunking import chunk_transcript

logger = logging.getLogger(__name__)


class OllamaAnalysisProvider(AIAnalysisProvider):
    """
    Local/external Ollama provider for transcript analysis.

    Integration point:
    - Reads OLLAMA_BASE_URL and OLLAMA_MODEL from environment variables.
    - For cloud migration, implement another AIAnalysisProvider and switch
      AI_ANALYSIS_PROVIDER in `.env`.
    """

    def analyze_transcript(
        self, transcript_text: str, segments: list[dict]
    ) -> list[ClipSuggestion]:
        settings = get_settings()
        chunks = chunk_transcript(transcript_text)
        if not chunks:
            return []

        logger.info(
            "Starting transcript chunk analysis",
            extra={"chunk_count": len(chunks), "model": settings.ollama_model},
        )
        clip_candidates: list[ClipSuggestion] = []
        for index, chunk in enumerate(chunks, start=1):
            logger.info(
                "Analyzing transcript chunk",
                extra={"chunk_index": index, "chunk_count": len(chunks), "chunk_chars": len(chunk)},
            )
            prompt = _build_analysis_prompt(chunk)
            response = self._query_ollama(prompt, settings.ollama_base_url, settings.ollama_model)
            parsed = _safe_parse_json_list(response)
            logger.info(
                "Chunk analysis complete",
                extra={"chunk_index": index, "parsed_candidates": len(parsed)},
            )
            clip_candidates.extend(_convert_candidates(parsed, segments))

        deduped_candidates = _dedupe_candidates(clip_candidates)
        deduped_candidates.sort(key=lambda c: c.score, reverse=True)
        clip_candidates.sort(key=lambda c: c.score, reverse=True)
        logger.info(
            "Transcript analysis finished",
            extra={
                "raw_candidate_count": len(clip_candidates),
                "deduped_candidate_count": len(deduped_candidates),
                "returned_candidates": min(len(deduped_candidates), settings.max_suggested_clips),
            },
        )
        return deduped_candidates[: settings.max_suggested_clips]

    def _query_ollama(self, prompt: str, base_url: str, model: str) -> str:
        endpoint = f"{base_url.rstrip('/')}/api/generate"
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
        }
        logger.info("Querying Ollama model", extra={"endpoint": endpoint, "model": model})
        with httpx.Client(timeout=get_settings().analysis_timeout_seconds) as client:
            response = client.post(endpoint, json=payload)
            response.raise_for_status()
            data = response.json()
        return str(data.get("response", "[]"))


def _build_analysis_prompt(chunk_text: str) -> str:
    return f"""
You are an expert podcast clip editor.
Analyze transcript text and return JSON array with 1-3 social clip suggestions.

Required fields per suggestion:
- title
- hook_text
- reason
- score (0-100)
- quote_snippet

Focus on:
- heated arguments
- emotional moments
- funny moments
- controversy
- memorable quotes
- high engagement potential
- strong opinions

Transcript chunk:
{chunk_text}

Return only valid JSON array.
""".strip()


def _safe_parse_json_list(raw: str) -> list[dict]:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    parsed = _parse_json_payload(cleaned)
    if parsed:
        return parsed

    # Fallback: model sometimes returns explanatory text around JSON.
    first_bracket = cleaned.find("[")
    last_bracket = cleaned.rfind("]")
    if first_bracket != -1 and last_bracket > first_bracket:
        candidate = cleaned[first_bracket : last_bracket + 1]
        parsed = _parse_json_payload(candidate)
        if parsed:
            return parsed

    logger.warning("Failed to decode Ollama response into a clip list")
    return []


def _parse_json_payload(raw: str) -> list[dict]:
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, str):
            return _parse_json_payload(parsed)
        if isinstance(parsed, list):
            return [item for item in parsed if isinstance(item, dict)]
        if isinstance(parsed, dict):
            # Common provider wrappers: {"clips":[...]}, {"suggestions":[...]}, etc.
            preferred_keys = [
                "clips",
                "suggestions",
                "clip_suggestions",
                "results",
                "items",
                "output",
            ]
            for key in preferred_keys:
                value = parsed.get(key)
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]

            # Last resort: pick the first list-like value from the object.
            for value in parsed.values():
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]
    except json.JSONDecodeError:
        return []
    return []


def _convert_candidates(items: list[dict], segments: list[dict]) -> list[ClipSuggestion]:
    """
    Convert model output into timeline-aware clip suggestions.

    This MVP uses quote_snippet fuzzy matching across transcript segments.
    """
    suggestions: list[ClipSuggestion] = []
    for item in items:
        quote = str(item.get("quote_snippet", "")).strip()
        start_seconds, end_seconds = _estimate_timestamps(quote, segments)
        suggestions.append(
            ClipSuggestion(
                title=str(item.get("title", "Untitled clip"))[:140],
                hook_text=str(item.get("hook_text", ""))[:240],
                reason=str(item.get("reason", "High engagement potential"))[:500],
                score=float(item.get("score", 50)),
                start_seconds=start_seconds,
                end_seconds=end_seconds,
            )
        )
    return suggestions


def _dedupe_candidates(candidates: list[ClipSuggestion]) -> list[ClipSuggestion]:
    deduped: list[ClipSuggestion] = []
    for candidate in sorted(candidates, key=lambda c: c.score, reverse=True):
        duplicate_idx = _find_duplicate_candidate_index(candidate, deduped)
        if duplicate_idx is None:
            deduped.append(candidate)
            continue

        existing = deduped[duplicate_idx]
        if _candidate_quality(candidate) > _candidate_quality(existing):
            deduped[duplicate_idx] = candidate
    return deduped


def _find_duplicate_candidate_index(
    candidate: ClipSuggestion, existing_candidates: list[ClipSuggestion]
) -> int | None:
    candidate_key = _normalized_text_key(candidate)
    for idx, existing in enumerate(existing_candidates):
        if _is_same_time_window(candidate, existing):
            return idx
        if candidate_key and candidate_key == _normalized_text_key(existing):
            return idx
    return None


def _is_same_time_window(a: ClipSuggestion, b: ClipSuggestion) -> bool:
    start_close = abs(a.start_seconds - b.start_seconds) <= 3.0
    end_close = abs(a.end_seconds - b.end_seconds) <= 3.0
    return start_close and end_close


def _normalized_text_key(candidate: ClipSuggestion) -> str:
    text = f"{candidate.title} {candidate.hook_text}".lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    words = [word for word in text.split() if len(word) > 2]
    return " ".join(words[:12])


def _candidate_quality(candidate: ClipSuggestion) -> tuple[float, int, int]:
    return (candidate.score, len(candidate.hook_text), len(candidate.title))


def _estimate_timestamps(quote_snippet: str, segments: list[dict]) -> tuple[float, float]:
    default_start, default_end = 0.0, 30.0
    if not segments:
        return default_start, default_end

    lowered_quote = quote_snippet.lower()
    for idx, segment in enumerate(segments):
        segment_text = str(segment.get("text", "")).lower()
        if lowered_quote and lowered_quote in segment_text:
            start = float(segment.get("start", 0.0))
            end_idx = min(idx + 5, len(segments) - 1)
            end = float(segments[end_idx].get("end", start + 30.0))
            return start, max(end, start + 10.0)

    start = float(segments[0].get("start", 0.0))
    end = float(segments[min(4, len(segments) - 1)].get("end", start + 30.0))
    return start, max(end, start + 10.0)
