#!/usr/bin/env bash
# OCR spike: запуск llama-server с весами Surya 2.5 (Task 2 Step 3).
# Флаг --special ОБЯЗАТЕЛЕН: без него модель не отдаёт спецтокены разметки
# (Task 2 Step 4 фиксирует отказ без него). Порт 8181, только loopback.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
PARALLEL="${1:-1}"; shift 2>/dev/null || true
exec "$ROOT/bin/llama-b12034/llama-server" \
  --model "$ROOT/models/surya-2.5-Q8_0.gguf" \
  --alias datalab-to/surya-ocr-2.5 \
  --mmproj "$ROOT/models/surya-2.5-mmproj.gguf" \
  --port 8181 \
  --host 127.0.0.1 \
  --ctx-size 24576 \
  --special \
  --parallel "$PARALLEL" \
  "$@"
