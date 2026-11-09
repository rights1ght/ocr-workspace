import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import type { JobState } from "../lib/types";

/** Рабочая область этапа 1: карточка, статус обработки (SSE), HTML-предпросмотр. */
export default function Workspace({ id }: { id: string }) {
  const qc = useQueryClient();
  const card = useQuery({ queryKey: ["doc", id], queryFn: () => api.documentCard(id), refetchInterval: 1500 });
  const job = card.data?.job_id ?? null;
  const [live, setLive] = useState<JobState | null>(null);

  const sseKey = ["job", job];
  useQuery({
    queryKey: sseKey,
    enabled: !!job && ["queued", "processing"].includes(card.data?.status ?? ""),
    queryFn: () =>
      new Promise<JobState>((resolve) => {
        const es = new EventSource(`/api/jobs/${job}/events`);
        es.onmessage = (e) => {
          const st = JSON.parse(e.data) as JobState;
          setLive(st);
          if (["done", "error", "canceled"].includes(st.status)) {
            es.close();
            qc.invalidateQueries({ queryKey: ["doc", id] });
            qc.invalidateQueries({ queryKey: ["documents"] });
            resolve(st);
          }
        };
        es.onerror = () => es.close();
      }),
  });

  // Оригинал страницы (просмотр) — если страницы отрендерены
  const pages = useQuery({ queryKey: ["pages", id], queryFn: () => api.documentPages(id) });
  const [pageNo, setPageNo] = useState(1);
  const page = (pages.data ?? []).find((p) => p.page_no === pageNo);

  return (
    <main className="mx-auto max-w-6xl px-4 py-8">
      <div className="mb-4 flex items-center gap-4">
        <Link to="/" className="text-blue-600 hover:underline">← Библиотека</Link>
        <h1 className="text-xl font-semibold">{card.data?.title ?? "…"}</h1>
        <span className="text-sm text-gray-500">{card.data?.status}</span>
        {live && card.data?.status === "processing" && (
          <span className="text-sm">
            {live.pages_done}/{live.pages_total} · {live.progress}%
          </span>
        )}
      </div>

      {card.data?.status === "error" && (
        <div className="rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-red-700 mb-4">
          {card.data.error_message}
        </div>
      )}

      <div className="grid grid-cols-2 gap-6" style={{ height: "70vh" }}>
        <section className="overflow-auto rounded-xl bg-white shadow-sm p-6">
          {card.data?.content_html ? (
            <article dangerouslySetInnerHTML={{ __html: card.data.content_html }} />
          ) : (
            <p className="text-gray-500">Текст появится после обработки.</p>
          )}
        </section>

        <section className="rounded-xl bg-gray-100 shadow-sm p-4 overflow-auto">
          <div className="mb-3 flex items-center gap-2 text-sm">
            <button className="rounded border px-2 py-0.5" onClick={() => setPageNo(Math.max(1, pageNo - 1))}>←</button>
            <span>стр. {pageNo}{pages.data ? ` / ${pages.data.length}` : ""}</span>
            <button className="rounded border px-2 py-0.5"
              onClick={() => setPageNo(Math.min((pages.data?.length ?? 1), pageNo + 1))}>→</button>
          </div>
          {card.data?.status === "processing" && (
            <div className="mb-3">
              <div className="h-2 rounded bg-gray-200 overflow-hidden">
                <div className="h-full bg-blue-500 transition-all" style={{ width: `${live?.progress ?? 0}%` }} />
              </div>
            </div>
          )}
          {page?.image_path ? (
            <img src={`/api/documents/${id}/pages/${pageNo}.png`} alt={`страница ${pageNo}`}
              className="mx-auto rounded shadow bg-white" />
          ) : (
            <p className="text-center text-gray-500 pt-10">Изображения страниц готовятся…</p>
          )}
        </section>
      </div>
    </main>
  );
}
