import json
import logging

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

        clip_candidates.sort(key=lambda c: c.score, reverse=True)
        logger.info(
            "Transcript analysis finished",
            extra={
                "raw_candidate_count": len(clip_candidates),
                "returned_candidates": min(len(clip_candidates), settings.max_suggested_clips),
            },
        )
        return clip_candidates[: settings.max_suggested_clips]

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
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [item for item in parsed if isinstance(item, dict)]
    except json.JSONDecodeError:
        logger.warning("Failed to decode Ollama response as JSON list")
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
