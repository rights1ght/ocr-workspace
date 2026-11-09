/** Клиент API: fetch к /api с JSON-помощниками. */
const BASE = "";

async function jfetch<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(BASE + path, init);
  if (!r.ok) {
    let detail = `${r.status}`;
    try { detail = (await r.json())?.detail ?? detail; } catch { /* не JSON */ }
    throw new Error(detail);
  }
  if (r.status === 204) return undefined as T;
  return (await r.json()) as T;
}

export const api = {
  documents: () => jfetch<import("./types").DocumentBrief[]>("/api/documents"),
  documentCard: (id: string) => jfetch<import("./types").DocumentBrief>(`/api/documents/${id}`),
  documentPages: (id: string) => jfetch<import("./types").Page[]>(`/api/documents/${id}/pages`),
  upload: (file: File) =>
    jfetch<import("./types").Upload>("/api/documents", {
      method: "POST",
      body: (() => { const fd = new FormData(); fd.append("file", file); return fd; })(),
    }),
  remove: (id: string) => jfetch<void>(`/api/documents/${id}`, { method: "DELETE" }),
  process: (id: string) => jfetch<{ job_id: string }>(`/api/documents/${id}/process`, { method: "POST" }),
};
