"use client";

import { ChangeEvent, useEffect, useMemo, useRef, useState } from "react";
import {
  approveClip,
  getApiBaseUrl,
  getProviderConfig,
  getUpload,
  getUploadClips,
  getUploadJobs,
  getUploads,
  rejectClip,
  uploadAudio
} from "../components/api";
import {
  ClipItem,
  ProcessingJob,
  ProcessingJobStatus,
  ProviderConfig,
  UploadDetail,
  UploadItem
} from "../components/types";

export default function HomePage() {
  const apiBaseUrl = getApiBaseUrl();
  const [uploads, setUploads] = useState<UploadItem[]>([]);
  const [selectedUploadId, setSelectedUploadId] = useState<string | null>(null);
  const [selectedUpload, setSelectedUpload] = useState<UploadDetail | null>(null);
  const [clips, setClips] = useState<ClipItem[]>([]);
  const [jobs, setJobs] = useState<ProcessingJob[]>([]);
  const [providerConfig, setProviderConfig] = useState<ProviderConfig | null>(null);
  const [showUploadPlayer, setShowUploadPlayer] = useState(false);
  const [activeClipPlayerId, setActiveClipPlayerId] = useState<string | null>(null);
  const uploadAudioRef = useRef<HTMLAudioElement | null>(null);
  const [uploadDuration, setUploadDuration] = useState(0);
  const [uploadCurrentTime, setUploadCurrentTime] = useState(0);
  const [isUploadPlaying, setIsUploadPlaying] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function refreshUploads() {
    try {
      const data = await getUploads();
      setUploads(data);
      if (!selectedUploadId && data.length > 0) {
        setSelectedUploadId(data[0].id);
      }
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function refreshSelectedUpload(uploadId: string) {
    try {
      const [uploadDetail, clipsData, jobsData] = await Promise.all([
        getUpload(uploadId),
        getUploadClips(uploadId),
        getUploadJobs(uploadId)
      ]);
      setSelectedUpload(uploadDetail);
      setClips(clipsData);
      setJobs(jobsData);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function refreshProviderConfig() {
    try {
      const config = await getProviderConfig();
      setProviderConfig(config);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  useEffect(() => {
    refreshUploads();
    refreshProviderConfig();
    const interval = setInterval(refreshUploads, 8000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (selectedUploadId) {
      refreshSelectedUpload(selectedUploadId);
      const interval = setInterval(() => refreshSelectedUpload(selectedUploadId), 8000);
      return () => clearInterval(interval);
    }
  }, [selectedUploadId]);

  useEffect(() => {
    setShowUploadPlayer(false);
    setActiveClipPlayerId(null);
    setUploadDuration(0);
    setUploadCurrentTime(0);
    setIsUploadPlaying(false);
  }, [selectedUploadId]);

  useEffect(() => {
    if (!showUploadPlayer && uploadAudioRef.current) {
      uploadAudioRef.current.pause();
      setIsUploadPlaying(false);
    }
  }, [showUploadPlayer]);

  async function onUpload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;

    try {
      setIsUploading(true);
      setError(null);
      const uploaded = await uploadAudio(file);
      await refreshUploads();
      setSelectedUploadId(uploaded.id);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setIsUploading(false);
    }
  }

  async function onClipAction(clipId: string, action: "approve" | "reject") {
    try {
      if (action === "approve") await approveClip(clipId);
      if (action === "reject") await rejectClip(clipId);
      if (selectedUploadId) await refreshSelectedUpload(selectedUploadId);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  function getJobStatus(jobType: string): ProcessingJobStatus {
    return jobs.find((job) => job.job_type === jobType)?.status ?? "pending";
  }

  function getStatusClass(status: ProcessingJobStatus): string {
    if (status === "completed") return "bg-green-100 text-green-800";
    if (status === "running") return "bg-blue-100 text-blue-800";
    if (status === "failed") return "bg-red-100 text-red-800";
    return "bg-slate-100 text-slate-700";
  }

  function formatTimestamp(seconds: number): string {
    const wholeSeconds = Math.max(0, Math.floor(seconds));
    const minutes = Math.floor(wholeSeconds / 60);
    const remainder = wholeSeconds % 60;
    return `${minutes}:${remainder.toString().padStart(2, "0")}`;
  }

  const uploadTimelineClipRanges = useMemo(() => {
    if (uploadDuration <= 0) {
      return [];
    }
    return clips
      .map((clip) => {
        const start = Math.max(0, Math.min(clip.start_seconds, uploadDuration));
        const end = Math.max(start, Math.min(clip.end_seconds, uploadDuration));
        return {
          id: clip.id,
          title: clip.title,
          start,
          end,
          leftPercent: (start / uploadDuration) * 100,
          widthPercent: Math.max(((end - start) / uploadDuration) * 100, 0.6)
        };
      })
      .sort((a, b) => a.start - b.start);
  }, [clips, uploadDuration]);

  const orderedClips = useMemo(() => {
    return [...clips].sort((a, b) => {
      if (a.start_seconds !== b.start_seconds) {
        return a.start_seconds - b.start_seconds;
      }
      if (a.end_seconds !== b.end_seconds) {
        return a.end_seconds - b.end_seconds;
      }
      return b.score - a.score;
    });
  }, [clips]);

  async function toggleUploadPlayback() {
    if (!uploadAudioRef.current) {
      return;
    }
    if (uploadAudioRef.current.paused) {
      await uploadAudioRef.current.play();
      setIsUploadPlaying(true);
      return;
    }
    uploadAudioRef.current.pause();
    setIsUploadPlaying(false);
  }

  function onUploadSeek(event: ChangeEvent<HTMLInputElement>) {
    const targetSeconds = Number(event.target.value);
    setUploadCurrentTime(targetSeconds);
    if (uploadAudioRef.current) {
      uploadAudioRef.current.currentTime = targetSeconds;
    }
  }

  return (
    <main className="mx-auto max-w-7xl p-4 md:p-8">
      <header className="mb-6 rounded-lg bg-white p-4 shadow">
        <h1 className="text-2xl font-bold">Newsroom Clipper MVP</h1>
        <p className="text-sm text-slate-600">
          Upload long-form MP3/WAV. The system transcribes, scores, and suggests social clips.
        </p>
      </header>

      <section className="mb-6 rounded-lg bg-white p-4 shadow">
        <label className="mb-2 block text-sm font-semibold">Upload Show Audio (MP3/WAV)</label>
        <input
          type="file"
          accept=".mp3,.wav,audio/mpeg,audio/wav"
          onChange={onUpload}
          className="block w-full text-sm"
        />
        {isUploading && <p className="mt-2 text-sm text-blue-600">Uploading and queuing job...</p>}
        {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
      </section>

      <section className="mb-6 rounded-lg bg-white p-4 shadow">
        <div className="mb-2 flex items-center justify-between">
          <h2 className="text-lg font-semibold">Provider Settings (Read-Only)</h2>
          <button
            onClick={refreshProviderConfig}
            className="rounded bg-slate-200 px-2 py-1 text-xs font-semibold text-slate-700"
          >
            Refresh
          </button>
        </div>
        {!providerConfig && (
          <p className="text-sm text-slate-600">Loading provider configuration...</p>
        )}
        {providerConfig && (
          <div className="grid gap-3 md:grid-cols-2">
            <div className="rounded border border-slate-200 p-3 text-xs">
              <p><span className="font-semibold">AI Provider:</span> {providerConfig.ai_analysis_provider}</p>
              <p><span className="font-semibold">Transcription:</span> {providerConfig.transcription_provider}</p>
              <p><span className="font-semibold">Clip Extraction:</span> {providerConfig.clip_extraction_provider}</p>
              <p><span className="font-semibold">Ollama URL:</span> {providerConfig.ollama_base_url}</p>
              <p><span className="font-semibold">Ollama Model:</span> {providerConfig.ollama_model}</p>
              <p><span className="font-semibold">Whisper Model:</span> {providerConfig.whisper_model}</p>
            </div>
            <div className="rounded border border-slate-200 p-3 text-xs">
              <p className="mb-1 font-semibold">Supported Ollama Model Names</p>
              <p className="mb-2">{providerConfig.supported_ollama_models.join(", ")}</p>
              <p className="mb-1 font-semibold">Future Cloud Keys Configured</p>
              <p>OpenAI: {providerConfig.cloud_provider_keys_configured.openai ? "yes" : "no"}</p>
              <p>Claude: {providerConfig.cloud_provider_keys_configured.claude ? "yes" : "no"}</p>
              <p>Deepgram: {providerConfig.cloud_provider_keys_configured.deepgram ? "yes" : "no"}</p>
            </div>
          </div>
        )}
      </section>

      <div className="grid gap-6 md:grid-cols-3">
        <section className="rounded-lg bg-white p-4 shadow">
          <h2 className="mb-3 text-lg font-semibold">Uploaded Shows</h2>
          <ul className="space-y-2">
            {uploads.map((upload) => (
              <li
                key={upload.id}
                className={`cursor-pointer rounded border p-3 ${
                  selectedUploadId === upload.id ? "border-blue-500 bg-blue-50" : "border-slate-200"
                }`}
                onClick={() => setSelectedUploadId(upload.id)}
              >
                <p className="truncate text-sm font-medium">{upload.original_filename}</p>
                <p className="text-xs text-slate-600">Status: {upload.status}</p>
              </li>
            ))}
          </ul>
        </section>

        <section className="md:col-span-2 rounded-lg bg-white p-4 shadow">
          <h2 className="mb-3 text-lg font-semibold">Editorial Review</h2>
          {!selectedUpload && <p className="text-sm text-slate-600">Select an upload to review.</p>}

          {selectedUpload && (
            <div className="space-y-4">
              <div className="rounded border border-slate-200 p-3">
                <p className="text-sm font-semibold">{selectedUpload.original_filename}</p>
                <p className="text-xs text-slate-600">Processing status: {selectedUpload.status}</p>
                <div className="mt-3">
                  <button
                    onClick={() => setShowUploadPlayer((current) => !current)}
                    className="rounded bg-blue-600 px-3 py-1 text-xs font-semibold text-white"
                  >
                    {showUploadPlayer ? "Hide Upload Player" : "Play Uploaded MP3/WAV"}
                  </button>
                  {showUploadPlayer && (
                    <div className="mt-3 space-y-2 rounded border border-slate-200 bg-slate-50 p-3">
                      <audio
                        ref={uploadAudioRef}
                        preload="metadata"
                        className="hidden"
                        onLoadedMetadata={() => {
                          const duration = uploadAudioRef.current?.duration ?? 0;
                          setUploadDuration(Number.isFinite(duration) ? duration : 0);
                        }}
                        onTimeUpdate={() => {
                          setUploadCurrentTime(uploadAudioRef.current?.currentTime ?? 0);
                        }}
                        onPlay={() => setIsUploadPlaying(true)}
                        onPause={() => setIsUploadPlaying(false)}
                        onEnded={() => setIsUploadPlaying(false)}
                      >
                        <source
                          src={`${apiBaseUrl}/uploads/${selectedUpload.id}/audio`}
                          type={selectedUpload.mime_type}
                        />
                      </audio>
                      <div className="flex flex-wrap items-center gap-2 text-xs">
                        <button
                          onClick={toggleUploadPlayback}
                          className="rounded bg-blue-600 px-3 py-1 font-semibold text-white"
                        >
                          {isUploadPlaying ? "Pause" : "Play"}
                        </button>
                        <span className="font-medium text-slate-700">
                          {formatTimestamp(uploadCurrentTime)} / {formatTimestamp(uploadDuration)}
                        </span>
                        {uploadTimelineClipRanges.length > 0 && (
                          <span className="text-slate-600">
                            {uploadTimelineClipRanges.length} clip window
                            {uploadTimelineClipRanges.length === 1 ? "" : "s"} overlaid
                          </span>
                        )}
                      </div>
                      <div className="relative pt-3">
                        {uploadTimelineClipRanges.length > 0 && (
                          <div className="pointer-events-none absolute inset-x-0 top-0 h-2">
                            {uploadTimelineClipRanges.map((range) => (
                              <div
                                key={`range-${range.id}`}
                                title={`${range.title}: ${formatTimestamp(range.start)} - ${formatTimestamp(
                                  range.end
                                )}`}
                                className="absolute h-2 rounded bg-blue-400/70"
                                style={{
                                  left: `${range.leftPercent}%`,
                                  width: `${range.widthPercent}%`
                                }}
                              />
                            ))}
                          </div>
                        )}
                        <input
                          type="range"
                          min={0}
                          max={Math.max(uploadDuration, 0)}
                          step={0.1}
                          value={Math.min(uploadCurrentTime, uploadDuration || 0)}
                          onChange={onUploadSeek}
                          disabled={uploadDuration <= 0}
                          className="h-2 w-full cursor-pointer accent-blue-600"
                          aria-label="Full upload timeline scrubber"
                        />
                      </div>
                    </div>
                  )}
                </div>
                <div className="mt-3">
                  <p className="mb-1 text-xs font-semibold text-slate-600">Transcript</p>
                  <div className="max-h-64 overflow-y-auto rounded border border-slate-200 bg-slate-50 p-2 text-xs text-slate-700">
                    {selectedUpload.transcript_text || "Transcript not ready yet."}
                  </div>
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  <a
                    href={`${apiBaseUrl}/uploads/${selectedUpload.id}/transcript/download?format=txt`}
                    className="rounded bg-slate-700 px-3 py-1 text-xs font-semibold text-white"
                  >
                    Download Transcript (.txt)
                  </a>
                  <a
                    href={`${apiBaseUrl}/uploads/${selectedUpload.id}/transcript/download?format=json`}
                    className="rounded bg-slate-700 px-3 py-1 text-xs font-semibold text-white"
                  >
                    Download Transcript (.json)
                  </a>
                </div>
              </div>

              <div className="rounded border border-slate-200 p-3">
                <div className="mb-2 flex items-center justify-between">
                  <h3 className="text-sm font-semibold">Pipeline Progress</h3>
                  <span className="text-xs text-slate-500">Auto-refreshes every 8s</span>
                </div>
                <div className="grid gap-2 md:grid-cols-3">
                  {[
                    { label: "Transcript Generation", key: "transcription" },
                    { label: "Transcript Analysis", key: "analysis" },
                    { label: "Clip Extraction", key: "clip_extraction" }
                  ].map((stage) => {
                    const stageStatus = getJobStatus(stage.key);
                    return (
                      <div key={stage.key} className="rounded border border-slate-200 p-2">
                        <p className="text-xs font-medium">{stage.label}</p>
                        <span
                          className={`mt-1 inline-block rounded px-2 py-0.5 text-xs font-semibold ${getStatusClass(
                            stageStatus
                          )}`}
                        >
                          {stageStatus}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>

              <div className="rounded border border-slate-200 p-3">
                <h3 className="mb-2 text-sm font-semibold">Generated Clips</h3>
                {orderedClips.length === 0 && (
                  <p className="text-sm text-slate-600">
                    Suggested clips will appear after transcription and analysis complete.
                  </p>
                )}
                {orderedClips.length > 0 && (
                  <ul className="max-h-72 space-y-2 overflow-y-auto pr-1">
                    {orderedClips.map((clip) => (
                      <li key={`panel-${clip.id}`} className="rounded border border-slate-200 p-2">
                        <div className="mb-2 flex flex-wrap items-center gap-2 text-xs">
                          <p className="font-semibold text-slate-800">{clip.title}</p>
                          <p className="text-slate-600">
                            Start {formatTimestamp(clip.start_seconds)} ({clip.start_seconds.toFixed(1)}s)
                          </p>
                          <p className="text-slate-600">
                            End {formatTimestamp(clip.end_seconds)} ({clip.end_seconds.toFixed(1)}s)
                          </p>
                        </div>
                        <div className="flex flex-wrap items-center gap-2 text-xs">
                          <button
                            onClick={() =>
                              setActiveClipPlayerId((current) => (current === clip.id ? null : clip.id))
                            }
                            className="rounded bg-blue-600 px-2 py-1 font-semibold text-white"
                          >
                            {activeClipPlayerId === clip.id ? "Hide Player" : "Play"}
                          </button>
                          <a
                            href={`${apiBaseUrl}/files/clips/${clip.id}.mp3`}
                            target="_blank"
                            rel="noreferrer"
                            className="rounded bg-slate-200 px-2 py-1 font-semibold text-slate-800"
                          >
                            Open
                          </a>
                          <a
                            href={`${apiBaseUrl}/files/clips/${clip.id}.mp3`}
                            download={`${clip.title || clip.id}.mp3`}
                            className="rounded bg-slate-700 px-2 py-1 font-semibold text-white"
                          >
                            Download MP3
                          </a>
                          <a
                            href={`${apiBaseUrl}/files/captions/${clip.id}.srt`}
                            download={`${clip.title || clip.id}.srt`}
                            className="rounded bg-slate-700 px-2 py-1 font-semibold text-white"
                          >
                            Download Captions
                          </a>
                        </div>
                        {activeClipPlayerId === clip.id && (
                          <audio controls className="mt-2 w-full">
                            <source src={`${apiBaseUrl}/files/clips/${clip.id}.mp3`} type="audio/mpeg" />
                          </audio>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              <div className="space-y-3">
                {orderedClips.map((clip) => (
                  <div key={clip.id} className="rounded border border-slate-200 p-3">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold">{clip.title}</p>
                        <p className="text-xs text-slate-600">
                          Score {clip.score.toFixed(1)} | {clip.start_seconds.toFixed(1)}s -{" "}
                          {clip.end_seconds.toFixed(1)}s
                        </p>
                      </div>
                      <p className="text-xs uppercase text-slate-500">{clip.status}</p>
                    </div>
                    <p className="mt-2 text-sm">{clip.hook_text}</p>
                    <p className="mt-1 text-xs text-slate-600">Why selected: {clip.reason}</p>
                    <audio controls className="mt-3 w-full">
                      <source src={`${apiBaseUrl}/files/clips/${clip.id}.mp3`} type="audio/mpeg" />
                    </audio>
                    <div className="mt-3 flex gap-2">
                      <button
                        onClick={() => onClipAction(clip.id, "approve")}
                        className="rounded bg-green-600 px-3 py-1 text-xs font-semibold text-white"
                      >
                        Approve
                      </button>
                      <button
                        onClick={() => onClipAction(clip.id, "reject")}
                        className="rounded bg-red-600 px-3 py-1 text-xs font-semibold text-white"
                      >
                        Reject
                      </button>
                      <a
                        href={`${apiBaseUrl}/files/clips/${clip.id}.mp3`}
                        download={`${clip.title || clip.id}.mp3`}
                        className="rounded bg-slate-700 px-3 py-1 text-xs font-semibold text-white"
                      >
                        Download MP3
                      </a>
                      <a
                        href={`${apiBaseUrl}/files/captions/${clip.id}.srt`}
                        download={`${clip.title || clip.id}.srt`}
                        className="rounded bg-slate-700 px-3 py-1 text-xs font-semibold text-white"
                      >
                        Download Captions
                      </a>
                    </div>
                  </div>
                ))}
                {orderedClips.length === 0 && (
                  <p className="text-sm text-slate-600">No clips ready for detailed review yet.</p>
                )}
              </div>

              {orderedClips.length > 0 && (
                <div className="rounded border border-slate-200 p-3">
                  <h3 className="mb-2 text-sm font-semibold">Downloads Panel</h3>
                  <ul className="space-y-2 text-xs">
                    {orderedClips.map((clip) => (
                      <li key={`download-${clip.id}`} className="flex flex-wrap items-center gap-2">
                        <span className="font-medium">{clip.title}</span>
                        <a
                          href={`${apiBaseUrl}/files/clips/${clip.id}.mp3`}
                          download={`${clip.title || clip.id}.mp3`}
                          className="rounded bg-blue-600 px-2 py-1 font-semibold text-white"
                        >
                          MP3
                        </a>
                        <a
                          href={`${apiBaseUrl}/files/captions/${clip.id}.srt`}
                          download={`${clip.title || clip.id}.srt`}
                          className="rounded bg-blue-600 px-2 py-1 font-semibold text-white"
                        >
                          SRT
                        </a>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </section>
      </div>
    </main>
  );
}
