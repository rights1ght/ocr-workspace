# Этап 1: каркас и импорт — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Загруженные PDF/скан/фото/DOCX/TXT превращаются в документ (pages PNG + канонический HTML в SQLite); библиотека с загрузкой работает в Electron.

**Architecture:** FastAPI (1 воркер, 127.0.0.1:8765) + SQLite WAL (SQLAlchemy Core, SQL-миграции по `user_version`); pipelines импорта пишут `page`/`document`; очередь asyncio-воркеров; SSE-прогресс. React 19 + Vite + Tailwind 4 отдаётся той же FastAPI (`frontend/dist`). OCR — этап 2, но статус машины/движка показывается сразу.

**Tech Stack:** Python 3.12 (venv spike), FastAPI, SQLAlchemy 2 Core, pdfplumber/pypdfium2, python-docx, React 19, Vite, Tailwind 4, TanStack Query.

**Spec:** OCR/TZ.md §§7, 8, 10, 12 (этап 1), приложения A/B.

## Global Constraints

- Python 3.12; зависимости точными версиями (`uv pip install`, freeze в `requirements.txt`).
- Сервер только `127.0.0.1` (SEC-1), порт `APP_PORT=8765`.
- Каталог данных `./data` рядом с проектом (`APP_DATA_DIR`, §7.1).
- Загрузка: MIME+magic bytes (SEC-3), ≤ `MAX_UPLOAD_MB=200`, ≤ `MAX_PAGES=200`; пути только через UUID (SEC-2); HTML санитайзится (§7.5, SEC-4).
- SQLite WAL, `foreign_keys=ON`, `busy_timeout=5000` (§7.1).
- Логи: `data/logs/app.log`, формат §10.7, без текстов документов (SEC-6).
- Блоки/страницы/документ — схема §7.2; сборка — §7.4; экспорт HTML→MD — приложение B.
- NFR-8: UI ≤ 5 с; OCR-страница ≤ 40 с @150 (показ ETA).

## Review Focus

1. Повреждённый/зашифрованный PDF → «Файл повреждён или защищён паролем», не краш (US-11) → тест: `test_upload_corrupt_pdf`.
2. Файл с неверным расширением (exe как .pdf) → 415 по magic bytes → тест `test_upload_forged_extension`.
3. DOCX без текста (пустой) → документ создаётся со статусом error=«пустой документ», а не 500 → тест `test_upload_empty_docx`.
4. `../`-путь в имени оригинала → хранится только basename, файлы пишутся в `<uuid>/original.<ext>` → тест `test_upload_traversal_name`.
5. Удаление документа удаляет и dir документов на диске → тест `test_delete_removes_files`.

---

### Task 1: Скелет backend (config, paths, logging, health)

**Files:** `backend/app/main.py`, `backend/app/core/config.py`, `backend/app/core/logging.py`, `backend/app/core/paths.py`, `backend/tests/conftest.py`, `backend/tests/test_health.py`

**Interfaces:**
- Produces: `app = create_app()` (создаёт dirs, применяется логирование); `settings` (dataclass: data_dir, port 8765, max_upload_mb 200, max_pages 200, ocr_dpi 150, from env); `get_data_dir() -> Path`; логгер `app.*`.

- [ ] Step 1: тест — `TestClient(create_app()).get("/health")` → `{"status":"ok"}`; каталоги `data/documents`, `data/logs`, `data/tmp` созданы; при `APP_DATA_DIR` в tmp — переопределяется.
- [ ] Step 2: FAIL → Step 3: реализация (uvicorn не нужен в тестах) → PASS.
- [ ] Step 4: `pip install fastapi httpx` Верси freeze; commit.

### Task 2: БД (schema + миграции)

**Files:** `backend/app/db/models.py`, `backend/app/db/session.py`, `backend/app/db/migrations.py`, `backend/tests/test_migrations.py`

**Interfaces:**
- Produces: `engine`, `SessionLocal`, `run_migrations(engine)`, таблицы `document`, `page`, `job`, `export`, `setting`, `app_event` (поля как ТЗ §7.2; `page.blocks_json TEXT`).

- [ ] Step 1: тест — миграции поднимают `user_version=1`; повторный вызов идемпотентен; FK page→document реально работает (`PRAGMA foreign_key_check` пуст, вставка page с чужим document_id падает).
- [ ] Step 2..4: FAIL → реализация SQL `migrations/0001-*.sql` (внутри db-пакета) → PASS → commit.

### Task 3: Загрузка документа (upload API + сигнатуры + типы источника)

**Files:** `backend/app/api/documents.py`, `backend/app/pipeline/detect.py`, `backend/tests/test_upload.py`, `backend/tests/test_detect.py`

**Interfaces:**
- Consumes: Task 2 cессия.
- Produces: `POST /api/documents` multipart `file` → 201 `{document}`; `detect_source(path) -> source_type in {pdf_text,pdf_scan,pdf_mixed,image,docx,txt}`; таблица статусов (§7.3) реализована в `detect.py` через `Text/SectionHeader/…` типа из списка §7.2 при сборке. `DocumentOut` pydantic-модель.

- [ ] Step 1: тесты — корректные фикстуры (pdf/image/docx/txt/заглушка png) → 201 и поляchema §7.2; фордж: `MZ`-файл с `.pdf` → 415 с текстом «Неподдерживаемый файл»; двойной upload одного файла → `duplicate=true` в ответе; имя `../../evil.pdf` → basename; PDF > MAX_PAGES → 409 «Слишком много страниц».
- [ ] Steps: FAIL → реализация (pdfplumber для текстового слоя: страница text_chars>50 → pdf_text, 0 у большинства → pdf_scan, часть → pdf_mixed) → PASS → commit.

### Task 4: Pages render ( pipelines: pdf/image/docx/txt)

**Files:** `backend/app/pipeline/pages.py`, `backend/tests/test_pages.py`

**Interfaces:**
- Consumes: `document`, `data_dir`.
- Produces: `render_pages(doc_path, doc_dir, dpi) -> list[PageRecord]` (PNG в `pages/NNNN.png`, width/height, page_count, `has_text_layer`); дляен: `extract_text_pdf(...)`, `extract_text_docx(path) -> str`, `extract_text_txt(path) -> str`.

- [ ] Step 1: тесты — 3-страничный PDF (сгенерирован на лету Pillow), image, docx (python-docx создан на лету), txt; папки pages заполнены 0001.png…; повреждённый PDF (`b "%PDF-"`-заголовок + мусор) → PdfError, документа не рендерится, статус error с сообщением «Файл повреждён или защищён паролем».
- [ ] Steps: FAIL → реализация (pypdfium2 render scale=dpi/72; Image: сохраняем оригинал в pages с пересохранением PNG + EXIF-транпонз) → PASS → commit.

### Task 5: Сборка HTML + санитайзер

**Files:** `backend/app/pipeline/assemble.py`, `backend/app/pipeline/sanitize.py`, `backend/tests/test_assemble.py`, `backend/tests/test_sanitize.py`

**Interfaces:**
- Produces: `sanitize_html(html: str) -> str` (белый список §7.5, `rel="noopener noreferrer"` на внешних ссылках); `assemble_document(source_type, pages, extracted_texts, blocks_by_page=None) -> content_html` по правилам §7.4 (txt/документ-предпросмотр этапа 1: абзацы с `data-src-page`, `<hr data-page-break>`; первый заголовок → h1).

- [ ] Step 1: тесты — sanitize: script/iframe/onclick/`javascript:` вырезаются, `<p>`, `td colspan` живут; assemble: `data-src-page`, page-break, экранирование `<` & `>` в тексте абзацев.
- [ ] Steps: FAIL → реализация (bs4, без bleach) → PASS → commit.

### Task 6: Jobs (очередь, воркер, SSE) + обработка импорта

**Files:** `backend/app/jobs/queue.py`, `backend/app/jobs/worker.py`, `backend/app/api/jobs.py`, `backend/tests/test_jobs.py`

**Interfaces:**
- Consumes: Tasks 3–5 пайплайн как `run_import(document_id)`; cессии Task 2.
- Produces: `enqueue(document_id) -> job_id`; worker (1 поток, `asyncio.to_thread`) — переводит `pausedProcessing->interrupted` при старте (§10.4); `GET /api/jobs/{id}/events` SSE-поток (`job` события); `POST /api/jobs/{id}/cancel`; таблица job §7.2.

- [ ] Step 1: тесты — job lifecycle queued→running→done собновления progress; cancel→canceled; старт с «зависшей running» → interrupted.
- [ ] Steps: FAIL → реализация (sync queue в sqlite; SSE через `sse-starlette` или ручной streaming) → PASS → commit.

### Task 7: CRUD документов + фронтенд скелет (библиотека)

**Files:** `backend/app/api/documents.py` (дополнение), `frontend/` (Vite scaffold), `frontend/src/pages/Library.tsx`, `frontend/src/pages/WorkspaceStub.tsx`, `frontend/src/lib/api.ts`, `backend/app/main.py` (static)

**Interfaces:**
- Consumes: API Tasks 3/6.
- Produces: `GET /api/documents` (list, параметры q, status), `GET /api/documents/{id}`, `DELETE /api/documents/{id}` (удаляет dir), статику `/` из `frontend/dist`; фронт: драг-энд-дроп зоны на «Библиотека», список карточек, экран прогресса по SSE.

- [ ] Step 1: pytest — list/ metallic/delete с файлами на диске; delete 404 повторно.
- [ ] Step 2: `npm create vite` (react-ts), Tailwind 4, TanStack Query, react-router; Library со здачей через `POST /api/documents` (traceback рендер в ESLint off — не нужен тест, ручная приемка).
- [ ] Step 3: e2e-приемка вручную через браузер: gadget upload корректного/кривого файла виден.
- [ ] Step 4: commit.

### Task 8: Electron → настоящий UI + run.sh

**Files:** `OCR/desktop/main.js` (изменение: prod-load `http://127.0.0.1:8765` когда backend доступен), `OCR/run.sh` (uvicorn + статическая сборка), `OCR README-u-related` — нет, README в Task 9 этапа 4.

**Interfaces:**
- Produces: единый вход: `run.sh` поднимает backend (тот же venv), Electron открывает `http://127.0.0.1:8765`; закрытие окна — прежнее правило (SIGTERM backend + модель выгружается).

- [ ] Step 1: ручная приёмка: окно открывает библиотеку, drag&drop работает, закрытие окна останавливает и backend, и llama-server.
- [ ] Step 2: commit.

### Task 9: Freeze зависимостей + requirements.txt backend

**Files:** `backend/requirements.txt`

- [ ] Step 1: `uv pip freeze | grep -E 'fastapi|uvicorn|sqlalchemy|httpx|pydantic|python-docx|pdfplumber|pypdfium2|sse'` → requirements.txt; commit.
