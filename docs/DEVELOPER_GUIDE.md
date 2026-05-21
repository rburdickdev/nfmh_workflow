# Developer Guide

This guide explains architecture, local run steps, and Postgres access for the MVP.

---

## Architecture Overview

The system is split into containers orchestrated by Docker Compose.

Services:

- `frontend` - Next.js newsroom UI
- `backend` - FastAPI REST API
- `worker` - Celery async job processor
- `postgres` - metadata persistence
- `redis` - Celery broker/result backend

External dependency:

- **Ollama** runs on host (outside Docker), accessed via `OLLAMA_BASE_URL`.

Core flow:

1. `POST /upload` stores file in `/storage/uploads` (Docker-managed volume).
2. Backend enqueues Celery task.
3. Worker normalizes source audio to 44.1kHz stereo WAV, then transcribes that WAV (local Whisper).
4. Worker analyzes transcript (Ollama model from env).
5. Worker extracts clips/captions (FFmpeg).
6. Frontend renders status and suggested clips.

Artifact outputs:

- Uploaded files: `/storage/uploads`
- Normalized transcription audio: `/storage/normalized_audio`
- Transcript artifacts: `/storage/transcripts`
- Extracted clip audio: `/storage/clips`
- Caption files: `/storage/captions`

Served download URLs:

- Uploaded source audio stream: `/uploads/{upload_id}/audio`
- Clips: `/files/clips/{clip_id}.mp3`
- Captions: `/files/captions/{clip_id}.srt`
- Transcripts: `/uploads/{upload_id}/transcript/download?format=txt|json`

---

## Code Structure

- `backend/app/main.py` - FastAPI app + startup + static file mounts
- `backend/app/api/routes.py` - REST endpoints
- `backend/app/providers/base.py` - provider interfaces
- `backend/app/providers/factory.py` - provider selection from env
- `backend/app/providers/whisper_provider.py` - local transcription
- `backend/app/providers/ollama_provider.py` - clip analysis via Ollama
- `backend/app/providers/ffmpeg_provider.py` - clip extraction + SRT
- `backend/app/services/pipeline.py` - orchestration logic
- `backend/app/workers/tasks.py` - Celery task entrypoint
- `frontend/src/app/page.tsx` - newsroom UI
- `docker-compose.yml` - service orchestration

---

## API Endpoints

- `POST /upload`
- `GET /uploads`
- `GET /uploads/{id}`
- `GET /uploads/{id}/audio`
- `GET /uploads/{id}/transcript/download?format=txt|json`
- `GET /uploads/{id}/clips`
- `POST /clips/{id}/approve`
- `POST /clips/{id}/reject`
- `POST /clips/{id}/youtube/upload`
- `GET /config/providers`

---

## Configuration Model

All runtime configuration is environment-variable driven.

Primary env vars:

- `OLLAMA_BASE_URL`
- `OLLAMA_MODEL`
- `WHISPER_MODEL`
- `POSTGRES_URL`
- `REDIS_URL`
- `CELERY_BROKER_URL`
- `CELERY_RESULT_BACKEND`
- `STORAGE_PATH`

Provider selection:

- `AI_ANALYSIS_PROVIDER` (default: `ollama`)
- `TRANSCRIPTION_PROVIDER` (default: `whisper_local`)
- `CLIP_EXTRACTION_PROVIDER` (default: `ffmpeg`)

Optional future keys:

- `OPENAI_API_KEY`
- `CLAUDE_API_KEY`
- `DEEPGRAM_API_KEY`

---

## Build and Run

## Prerequisites

- Docker Desktop running
- Ollama installed and running on host

## 1) Start Ollama and pull model

```bash
ollama serve
ollama pull llama3
```

## 2) Create env file

```bash
cp .env.example .env
```

Recommended values:

- `OLLAMA_BASE_URL=http://host.docker.internal:11434`
- `OLLAMA_MODEL=llama3`

## 3) Build + launch stack

```bash
docker compose up --build
```

Alternative:

```bash
./scripts/start_all.sh
```

## 4) Verify

- Frontend: `http://localhost:3000`
- API docs: `http://localhost:8000/docs`
- Health: `http://localhost:8000/health`

Useful logs:

```bash
docker compose logs -f backend
docker compose logs -f worker
```

Progress log tip:

- Use `docker compose logs -f worker` to track transcription/analysis/clip extraction progress.

Stop stack:

```bash
docker compose down
```

---

## Postgres Database Access

Default container/service:

- Service: `postgres`
- Container: `clipper_postgres`
- DB: `clipper_db`
- User: `clipper`
- Password: `clipper`
- Port: `5432`

These come from `.env` and can be changed there.

## Option A: Connect from host with `psql`

If `psql` is installed locally:

```bash
psql "postgresql://clipper:clipper@localhost:5432/clipper_db"
```

## Option B: Connect inside container

```bash
docker compose exec postgres psql -U clipper -d clipper_db
```

## Basic SQL checks

```sql
\dt
SELECT id, original_filename, status, created_at FROM uploads ORDER BY created_at DESC LIMIT 20;
SELECT id, upload_id, title, score, status FROM clips ORDER BY created_at DESC LIMIT 20;
SELECT id, upload_id, job_type, status, error_message FROM processing_jobs ORDER BY created_at DESC LIMIT 20;
```

## From backend container

Useful for debugging connection strings inside app runtime:

```bash
docker compose exec backend bash
python -c "from app.core.config import get_settings; print(get_settings().postgres_url)"
```

---

## Provider Abstraction and Future Providers

Key interfaces live in `backend/app/providers/base.py`.

To add a new cloud provider:

1. Implement the relevant interface class.
2. Add selection branch in `backend/app/providers/factory.py`.
3. Add env vars/credentials to `.env` and `.env.example`.
4. Keep API/service contracts unchanged.

This design avoids major refactors when moving from local to cloud AI.

---

## Frontend Download UX

The newsroom UI includes:

- A source audio playback toggle for uploaded MP3/WAV/M4A in Editorial Review
- A scrollable full transcript panel for long transcript text
- A **Generated Clips** panel with per-clip title links, inline play button, and source start/end timestamps
- Per-clip download buttons (MP3 + SRT) in each editorial clip card
- A **Downloads Panel** listing all generated clips with quick links
- Transcript download buttons (`.txt` and `.json`) for selected upload

Primary implementation file:

- `frontend/src/app/page.tsx`

---

## Queue and Failure Handling

- Celery task: `process_upload_task`
- Retries enabled (`max_retries=3`, exponential backoff)
- Failures captured in `processing_jobs.error_message`
- Upload status updated to `failed` on terminal errors

---

## Recommended Model Choices

For clip reasoning quality:

- Start with `llama3`
- Try `qwen` or `mistral` if needed
- Use the exact pulled model tag in `OLLAMA_MODEL`

Any Ollama model can be referenced, but instruction-following quality and JSON stability directly impact clip quality.

---

## Troubleshooting

### Ollama not reachable from containers

- Verify host Ollama running: `curl http://localhost:11434/api/tags`
- Verify `.env` has correct `OLLAMA_BASE_URL`
- Restart stack after env changes

### No clips generated

- Inspect worker logs for JSON parse failures or provider errors
- Try a stronger model in `OLLAMA_MODEL`

### Slow transcription

- Use smaller `WHISPER_MODEL` (`base` or `small`) for faster iterations
