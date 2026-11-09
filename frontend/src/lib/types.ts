/** Типы API (зеркало backend-ответов). */
export type DocumentBrief = {
  id: string;
  title: string;
  status: "queued" | "processing" | "ready" | "error" | "canceled" | "interrupted";
  source_type: string;
  page_count: number;
  size_bytes: number;
  created_at: string;
  updated_at: string;
  original_filename?: string;
  mime?: string;
  sha256?: string;
  engine?: string;
  content_html?: string;
  content_version?: number;
  low_confidence?: number;
  error_message?: string | null;
  processing_ms?: number | null;
  duplicate?: boolean;
  directory?: string;
  job_id?: string;
};

export type Upload = DocumentBrief;

export type JobState = {
  id?: string;
  document_id: string;
  type?: string;
  status: "queued" | "running" | "done" | "error" | "canceled" | "interrupted";
  progress: number;
  pages_done: number;
  pages_total: number;
  eta_seconds?: number | null;
  error_message?: string | null;
};

export type Page = {
  page_no: number;
  image_path: string;
  width: number;
  height: number;
  dpi: number;
  has_text_layer: number;
  ocr_used: number;
  status: string;
  blocks_json: string;
};
