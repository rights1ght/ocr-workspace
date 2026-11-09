#!/usr/bin/env python3
"""OCR spike Task 4 Step 3: агрегат CSV → summary.md с вердиктами по порогам ТЗ (приложение D).

Запуск: .venv/bin/python summarize.py
"""
from __future__ import annotations

import csv
import statistics as st
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RES = ROOT / "measure-results"
THRESH = {"96": 25, "150": 40, "192": 0, "300": 0}  # 192/300 не тестируем (из ТЗ: цели только 96/150; 192 — бенчмарк Datalab)
RAM_LIMIT_MB = 8192
LOW_LIMIT = 0.15


def collect() -> None:
    lines = ["# Surya 2.5 — сводка spike (ТЗ, приложение D)", "", "| DPI | метрика | значение | порог | вердикт |", "|---|---|---|---|---|"]
    for dpi_dir in sorted(RES.iterdir()):
        csvs = sorted(dpi_dir.glob("warm.csv"))  # только тёплые замеры (ruling #2)
        if not csvs:
            continue
        fps = [r for c in csvs for r in csv.DictReader(c.open(encoding="utf-8")) if r["file"].startswith("20pages.pdf:p")]
        script = [r for c in csvs for r in csv.DictReader(c.open(encoding="utf-8")) if not r["file"].startswith("20pages.pdf")]
        text_rows = [float(r["seconds"]) for r in script if not r["file"].startswith("tables/")]
        table_rows = [float(r["seconds"]) for r in script if "tables/" in r["file"]]
        low = [float(r["low_conf_ratio"]) for r in script] + [float(r["low_conf_ratio"]) for r in fps]
        server_kb = max((int(r["server_rss_kb"]) for r in script + fps), default=0)
        self_kb = max(int(r["self_rss_kb"]) for r in script + fps if r["self_rss_kb"])
        dpi = dpi_dir.name
        if text_rows:
            med = st.median(text_rows)
            thr = THRESH.get(dpi)
            verdict = "OK" if thr and med <= thr else ("OVER" if thr else "n/a")
            lines.append(f"| {dpi} | медиана сек/страницу (текст) | {med:.1f} | ≤{thr or '—'} | {verdict} |")
        if table_rows:
            lines.append(f"| {dpi} | медиана сек/таблицу | {st.median(table_rows):.1f} | — | — |")
        if low:
            max_ratio = max(low)
            lines.append(f"| {dpi} | max доля low_conf на странице | {max_ratio:.0%} | ≤15 % | {'OK' if max_ratio <= LOW_LIMIT else 'OVER'} |")
        ram_mb = round((server_kb + self_kb) / 1024, 1) if server_kb else round(self_kb / 1024, 1)
        lines.append(f"| {dpi} | пик RAM (приложение+сервер), МБ | {ram_mb} | ≤8192 | {'OK' if ram_mb <= RAM_LIMIT_MB else 'OVER'} |")
    (RES / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    collect()
