export type UploadStatus = "uploaded" | "processing" | "completed" | "failed";

export type UploadItem = {
  id: string;
  original_filename: string;
  mime_type: string;
  status: UploadStatus;
  created_at: string;
};

export type UploadDetail = UploadItem & {
  storage_path: string;
  updated_at: string;
  transcript_text?: string | null;
};

export type ClipStatus = "suggested" | "approved" | "rejected";

export type ClipItem = {
  id: string;
  upload_id: string;
  title: string;
  hook_text: string;
  reason: string;
  score: number;
  start_seconds: number;
  end_seconds: number;
  clip_path: string;
  captions_path: string;
  status: ClipStatus;
  created_at: string;
};

export type ProviderConfig = {
  ai_analysis_provider: string;
  transcription_provider: string;
  clip_extraction_provider: string;
  ollama_base_url: string;
  ollama_model: string;
  whisper_model: string;
  supported_ollama_models: string[];
  cloud_provider_keys_configured: {
    openai: boolean;
    claude: boolean;
    deepgram: boolean;
    youtube: boolean;
  };
};

export type ProcessingJobStatus = "pending" | "running" | "completed" | "failed";

export type ProcessingJob = {
  id: string;
  job_type: string;
  status: ProcessingJobStatus;
  error_message: string | null;
  created_at: string;
  updated_at: string;
};

export type YouTubeUploadRequest = {
  title?: string;
  description?: string;
  privacy_status?: "private" | "unlisted" | "public";
};

export type YouTubeUploadResult = {
  clip_id: string;
  youtube_video_id: string;
  youtube_url: string;
  rendered_video_path: string;
  thumbnail_path: string;
};
