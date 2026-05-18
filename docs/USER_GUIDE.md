# Newsroom User Guide

This guide is for editors and producers using the clipping platform day to day.

---

## What This Tool Does

The platform helps you turn long radio/podcast audio into social-ready short clips.

Workflow:

1. Upload MP3, WAV, or M4A show audio.
2. System transcribes audio automatically.
3. AI suggests strong social moments.
4. You review each suggested clip.
5. You approve or reject clips for publishing.

---

## Before You Start

Make sure the platform has been started by your technical team.

You should have:

- Frontend URL (usually `http://localhost:3000`)
- A valid MP3, WAV, or M4A file

---

## How to Use the Platform

## 1) Open the Dashboard

Open the frontend URL in your browser.

You will see:

- Upload section
- Provider Settings (read-only)
- Uploaded Shows list
- Editorial Review area

## 2) Upload Audio

In **Upload Show Audio (MP3/WAV/M4A)**:

1. Click the file picker.
2. Choose an MP3, WAV, or M4A file.
3. Wait for the file to upload and queue.

The file appears in **Uploaded Shows** with status updates.

## 3) Track Processing Status

Statuses:

- `uploaded` - file stored and queued
- `processing` - transcription + analysis in progress
- `completed` - clips are ready for review
- `failed` - an error occurred (ask developer/admin)

## 4) Review Suggested Clips

Select a show in **Uploaded Shows**.

In **Editorial Review**:

- Play the full uploaded source audio from the source audio player
- Read the full transcript in a scrollable transcript panel
- Read clip title and hook text
- See AI score and timestamps
- Listen to audio preview
- Review reason for selection

In **Generated Clips**:

- Open each clip link directly
- Use **Play** to open an inline clip player
- See start and end timestamps (`mm:ss`) from the original upload

You will also see download options for each generated clip:

- **Download MP3** for the extracted clip audio
- **Download Captions** for the clip SRT subtitle file

## 5) Approve or Reject

For each suggested clip:

- Click **Approve** to keep it for social
- Click **Reject** to discard it

## 6) Download Clips and Transcripts

For the currently selected upload:

- Use **Download Transcript (.txt)** for plain text transcript
- Use **Download Transcript (.json)** for timestamped transcript data

For each suggested clip:

- Use **Download MP3** to save clip audio
- Use **Download Captions** to save SRT captions

The **Downloads Panel** also lists all extracted clips with quick MP3/SRT links in one place.

---

## Understanding Provider Settings (Read-Only Panel)

The panel shows the current AI setup:

- Active analysis provider (example: `ollama`)
- Active transcription provider (example: `whisper_local`)
- Active model name (example: `llama3`)

It is informational only for operators.

If you need model/provider changes, contact your developer/admin.

---

## Tips for Better Results

- Upload clean audio with clear speech.
- Avoid heavily clipped/distorted source files.
- For very long episodes, allow extra processing time.
- If clip quality is weak, ask technical staff to try a different `OLLAMA_MODEL`.

---

## Common Issues

### Upload rejected

- Ensure file is MP3, WAV, or M4A.

### Processing takes long

- Long files and larger models need more time.

### No suggested clips

- Ask technical staff to check worker logs and model selection.

### Audio preview does not play

- Refresh the page.
- If still broken, ask technical staff to confirm backend is running.

### Uploaded source audio does not play

- Confirm backend is running at `http://localhost:8000`.
- Ask technical staff to verify the upload still exists in `storage/uploads`.

### Download links fail

- Confirm backend is running at `http://localhost:8000`.
- Ask technical staff to confirm processing completed (`completed` status).
- If transcript download fails, transcript may still be processing.

---

## When to Ask a Developer

Contact a developer/admin if:

- Status is `failed`
- No clips are generated repeatedly
- You need model/provider changes
- You need direct database exports or integration support
