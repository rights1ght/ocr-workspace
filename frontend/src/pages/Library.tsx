import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import type { DocumentBrief } from "../lib/types";

const STATUS_LABEL: Record<string, string> = {
  queued: "в очереди",
  processing: "обработка",
  ready: "готов",
  error: "ошибка",
  canceled: "отменён",
  interrupted: "прерван",
};
const STATUS_COLOR: Record<string, string> = {
  queued: "#e2b23c",
  processing: "#e2b23c",
  ready: "#3ca85e",
  error: "#d24545",
  canceled: "#8a8a8a",
  interrupted: "#d24545",
};

export default function Library() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const docs = useQuery({ queryKey: ["documents"], queryFn: api.documents, refetchInterval: 2000 });
  const [drag, setDrag] = useState(false);
  const [uploading, setUploading] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const doUpload = useCallback(async (files: FileList) => {
    setError(null);
    for (const f of files) {
      setUploading((u) => [...u, f.name]);
      try {
        const doc = await api.upload(f);
        if (doc.duplicate) setError(`«${doc.title}» уже загружен раньше — добавлен с пометкой`);
        else navigate(`/doc/${doc.id}`);
      } catch (e: any) {
        setError(`${f.name}: ${e?.message ?? e}`);
      } finally {
        setUploading((u) => u.filter((n) => n !== f.name));
      }
      qc.invalidateQueries({ queryKey: ["documents"] });
    }
  }, [qc, navigate]);

  const del = useMutation({
    mutationFn: api.remove,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["documents"] }),
  });

  return (
    <main className="mx-auto max-w-4xl px-4 py-10">
      <h1 className="text-2xl font-semibold mb-6">Библиотека документов</h1>

      <div
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); void doUpload(e.dataTransfer.files); }}
        onClick={() => inputRef.current?.click()}
        className={`cursor-pointer rounded-2xl border-2 border-dashed p-12 text-center transition
          ${drag ? "border-blue-500 bg-blue-50" : "border-gray-300 bg-white hover:border-gray-400"}`}
      >
        <p className="text-lg">{drag ? "Отпустите файл" : "Перетащите PDF, скан, фото, DOCX или TXT"}</p>
        <p className="text-sm text-gray-500 mt-1">или нажмите, чтобы выбрать · до 200 МБ, до 200 страниц</p>
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,image/*,.docx,.txt"
          multiple
          className="hidden"
          onChange={(e) => { if (e.target.files) void doUpload(e.target.files); e.target.value = ""; }}
        />
      </div>

      {uploading.length > 0 && <p className="mt-3 text-sm text-blue-600">Загрузка: {uploading.join(", ")}</p>}
      {error && <p className="mt-3 text-sm text-red-600" role="alert">{error}</p>}

      <div className="mt-8 space-y-3">
        {(docs.data ?? []).map((d: DocumentBrief) => (
          <div key={d.id}
            className="flex items-center justify-between rounded-xl bg-white px-5 py-4 shadow-sm cursor-pointer hover:shadow"
            onClick={() => navigate(`/doc/${d.id}`)}
          >
            <div>
              <div className="font-medium">{d.title}</div>
              <div className="text-sm text-gray-500">
                {d.source_type} · {d.page_count} стр. · {(d.size_bytes / 1024).toFixed(0)} КБ
              </div>
            </div>
            <div className="flex items-center gap-4">
              <span className="flex items-center gap-2 text-sm">
                <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: STATUS_COLOR[d.status] }} />
                {STATUS_LABEL[d.status]}
                {d.error_message && <span className="text-red-600">— {d.error_message.slice(0, 60)}</span>}
              </span>
              <button
                className="rounded-lg border px-3 py-1 text-sm hover:bg-gray-50"
                onClick={(e) => { e.stopPropagation(); del.mutate(d.id); }}
              >
                удалить
              </button>
            </div>
          </div>
        ))}
        {(docs.data?.length ?? 0) === 0 && (
          <p className="text-center text-gray-500 py-8">Пока пусто — загрузите первый документ</p>
        )}
      </div>
    </main>
  );
}
