# Newsroom Clipper MVP

Dockerized MVP platform for AI-powered radio/podcast clipping and social media extraction.

Additional documentation:

- User guide: `docs/USER_GUIDE.md`
- Developer guide: `docs/DEVELOPER_GUIDE.md`

This project is designed for non-technical newsroom operators:

1. Upload long-form MP3/WAV/M4A.
2. System auto-processes in background.
3. Editorial team reviews suggested clips.
4. Team approves/rejects clips for social publishing.

---

## What This MVP Includes

- `frontend`: Next.js + Tailwind newsroom UI
- `backend`: FastAPI REST API
- `worker`: Celery background processing worker
- `postgres`: metadata storage
- `redis`: queue + task results
- External Ollama (already installed on your host, not dockerized here)
- Local Whisper transcription (`faster-whisper`) running inside Docker
- Local FFmpeg clip extraction inside Docker

---

## Architecture Overview

### Processing flow

1. `POST /upload` stores MP3/WAV/M4A in `/storage/uploads` (inside a Docker-managed volume)
2. API queues Celery task
3. Worker normalizes upload to 44.1kHz stereo WAV and transcribes that WAV with local Whisper
4. Worker chunks transcript and calls Ollama for hook detection
5. Worker extracts clips with FFmpeg and writes SRT captions
6. Suggested clips are stored in Postgres and shown in frontend

### Storage structure (inside Docker volume mounted at `/storage`)

- `/storage/uploads` - original uploads
- `/storage/normalized_audio` - normalized WAV files used for transcription
- `/storage/transcripts` - transcript TXT + JSON
- `/storage/clips` - extracted MP3 clips
- `/storage/captions` - generated SRT captions

---

## Ollama Setup (External)

Ollama runs on your machine outside Docker.

1. Verify Ollama is installed:
   - macOS: [https://ollama.com/download](https://ollama.com/download)
2. Start Ollama:
   - `ollama serve`
3. Pull at least one model:
   - `ollama pull llama3`
   - optional: `ollama pull mistral`
   - optional: `ollama pull deepseek-r1`
   - optional: `ollama pull qwen`
4. In `.env`, set:
   - `OLLAMA_BASE_URL=http://host.docker.internal:11434`
   - `OLLAMA_MODEL=llama3` (or another installed model)

---

## Quick Start

### 1) Configure environment

```bash
cp .env.example .env
```

Edit `.env` as needed.

### 2) Start everything with one command

```bash
./scripts/start_all.sh
```

or directly:

```bash
docker compose up --build
```

### 3) Open apps

- Frontend UI: `http://localhost:3000`
- Backend API docs: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/health`

### Export storage artifacts to local folder

To copy uploads, clips, transcripts, and captions from the Docker volume to your machine:

```bash
./scripts/export_storage.sh
```

Optional custom destination:

```bash
./scripts/export_storage.sh ./my_exports
```

---

## Environment Variables

All configuration is environment-driven. No hardcoded credentials.

### Core required variables

- `OLLAMA_BASE_URL`
- `OLLAMA_MODEL`
- `WHISPER_MODEL`
- `POSTGRES_URL`
- `REDIS_URL`
- `STORAGE_PATH`

### Optional future cloud credentials

These are intentionally included now so migration is easy later:

- `OPENAI_API_KEY`
- `CLAUDE_API_KEY`
- `DEEPGRAM_API_KEY`

Keep them blank unless you add cloud providers.

---

## Where Credentials and Provider Settings Live

### API keys / secrets

Put all credentials only in `.env` (never commit `.env`).

### Model switching

Change local model without code changes:

- `OLLAMA_MODEL=llama3`
- `OLLAMA_MODEL=mistral`
- `OLLAMA_MODEL=deepseek-r1`
- `OLLAMA_MODEL=qwen`

### Provider switching (future-proof design)

Provider selection lives in `.env`:

- `AI_ANALYSIS_PROVIDER=ollama`
- `TRANSCRIPTION_PROVIDER=whisper_local`
- `CLIP_EXTRACTION_PROVIDER=ffmpeg`

Provider interfaces are in:

- `backend/app/providers/base.py`

Provider factory wiring is in:

- `backend/app/providers/factory.py`

To add OpenAI/Claude/etc later:

1. Implement a new provider class.
2. Keep the same provider interface.
3. Add provider selection in `factory.py`.
4. Set provider variable in `.env`.

---

## REST API Endpoints

- `POST /upload`
- `GET /uploads`
- `GET /uploads/{id}`
- `GET /uploads/{id}/audio`
- `GET /uploads/{id}/transcript/download?format=txt|json`
- `GET /uploads/{id}/clips`
- `POST /clips/{id}/approve`
- `POST /clips/{id}/reject`
- `GET /config/providers` (safe, non-secret runtime config for UI settings panel)

---

## Queue + Retry Behavior

Celery handles heavy tasks outside request/response cycle:

- transcription jobs
- analysis jobs
- clip generation jobs

Retries:

- automatic retries on exceptions (up to 3)
- failed jobs stored in `processing_jobs` table
- upload status becomes `failed` when retries are exhausted

---

## Database Tables

- `uploads`
- `transcripts`
- `clips`
- `processing_jobs`

Tables are auto-created on startup for MVP simplicity.

---

## Notes for Newsroom Operators

- You only need the web UI and one upload action.
- Processing can take time for long episodes.
- Refreshes happen automatically every few seconds in the dashboard.
- Use Approve/Reject buttons to triage social clip candidates.

---

## Troubleshooting

### Ollama connection errors

- Ensure `ollama serve` is running on host
- Verify `OLLAMA_BASE_URL` in `.env`
- Test from host: `curl http://localhost:11434/api/tags`

### No clips generated

- Try a different model in `OLLAMA_MODEL`
- Increase model quality (for example, move from `mistral` to `llama3`)
- Check worker logs: `docker compose logs -f worker`

### Whisper too slow

- Use smaller model (`WHISPER_MODEL=base` or `small`)
- Reduce job size during testing

### FFmpeg failures

- Check backend/worker logs for command output
- Confirm source file is valid MP3/WAV/M4A

---

## Future Expansion Path

Designed to support later:

- OpenAI/Claude API backends
- livestream ingestion
- video clipping
- social publishing integrations
- multilingual transcription and captioning

The provider abstraction layer is already in place to minimize refactors.
