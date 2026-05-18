from app.core.config import get_settings


def chunk_transcript(text: str) -> list[str]:
    """
    Simple character-based chunking for MVP.

    This is intentionally easy to understand and tune through environment vars.
    A later version can replace this with true semantic token chunking.
    """
    settings = get_settings()
    chunk_size = settings.transcript_chunk_size
    overlap = settings.transcript_chunk_overlap

    if not text:
        return []

    chunks: list[str] = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = min(start + chunk_size, text_len)
        chunks.append(text[start:end])
        if end == text_len:
            break
        start = max(end - overlap, 0)

    return chunks
