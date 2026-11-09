# Spike поручитель: не для продакшена (ТЗ раздел 12 этап 0)
PY := .venv/bin/python
PIP := .venv/bin/python -m pip
export PATH := $(HOME)/.local/bin:$(PATH)

.PHONY: venv clean models server

venv: .venv
.venv:
	uv venv --python 3.12
	uv pip install --python .venv torch --index-url https://download.pytorch.org/whl/cpu
	uv pip install --python .venv surya-ocr pypdfium2 pdfplumber markdownify
	uv pip freeze --python .venv | sort -u > requirements-spike.txt

clean:
	rm -rf .venv measure-results results __pycache__
	rm -f spike-notes.md
