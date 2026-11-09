#!/usr/bin/env bash
# OCR spike: скачать llama.cpp (CPU ubuntu) и GGUF-веса Surya 2.5 Q8_0.
# Оригинал плана Task 2 Steps 1-2. Веса не попадают в git (см. ../.gitignore).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
LLAMA_TAG="b12034"
mkdir -p "$ROOT/bin" "$ROOT/models"

if [[ ! -x "$ROOT/bin/llama-b12034/llama-server" ]]; then
  echo ">> скачиваю llama.cpp $LLAMA_TAG (ubuntu x64, CPU)"
  curl -L --fail -o /tmp/llama.tar.gz \
    "https://github.com/ggml-org/llama.cpp/releases/download/${LLAMA_TAG}/llama-${LLAMA_TAG}-bin-ubuntu-x64.tar.gz"
  tar xzf /tmp/llama.tar.gz -C "$ROOT/bin"
fi
"$ROOT/bin/llama-b12034/llama-server" --version

for f in surya-2.5-Q8_0.gguf surya-2.5-mmproj.gguf chat_template.jinja; do
  if [[ ! -s "$ROOT/models/$f" ]]; then
    echo ">> скачиваю $f"
    curl -L --fail -o "$ROOT/models/$f" \
      "https://huggingface.co/datalab-to/surya-ocr-2.5-gguf/resolve/main/$f"
  fi
done
ls -la "$ROOT/models"
echo OK
