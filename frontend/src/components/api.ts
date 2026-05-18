import {
  ClipItem,
  ProcessingJob,
  ProviderConfig,
  UploadDetail,
  UploadItem
} from "./types";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export function getApiBaseUrl(): string {
  return API_BASE;
}

export async function uploadAudio(file: File): Promise<UploadItem> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_BASE}/upload`, {
    method: "POST",
    body: formData
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json();
}

export async function getUploads(): Promise<UploadItem[]> {
  const response = await fetch(`${API_BASE}/uploads`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error("Failed to fetch uploads");
  }
  return response.json();
}

export async function getUpload(id: string): Promise<UploadDetail> {
  const response = await fetch(`${API_BASE}/uploads/${id}`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error("Failed to fetch upload detail");
  }
  return response.json();
}

export async function getUploadClips(id: string): Promise<ClipItem[]> {
  const response = await fetch(`${API_BASE}/uploads/${id}/clips`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error("Failed to fetch clips");
  }
  return response.json();
}

export async function getUploadJobs(id: string): Promise<ProcessingJob[]> {
  const response = await fetch(`${API_BASE}/uploads/${id}/jobs`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error("Failed to fetch processing jobs");
  }
  return response.json();
}

export async function approveClip(id: string): Promise<void> {
  const response = await fetch(`${API_BASE}/clips/${id}/approve`, { method: "POST" });
  if (!response.ok) {
    throw new Error("Failed to approve clip");
  }
}

export async function rejectClip(id: string): Promise<void> {
  const response = await fetch(`${API_BASE}/clips/${id}/reject`, { method: "POST" });
  if (!response.ok) {
    throw new Error("Failed to reject clip");
  }
}

export async function getProviderConfig(): Promise<ProviderConfig> {
  const response = await fetch(`${API_BASE}/config/providers`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error("Failed to fetch provider configuration");
  }
  return response.json();
}
