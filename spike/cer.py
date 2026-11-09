#!/usr/bin/env python3
"""OCR spike Task 5: Character Error Rate (CER) по эталонам.

CER = левенштейн(распознанное, эталон) / len(эталон).

Вход:
  --result results/<page>.json   results.json от surya_ocr (или dict по файлу)
  --truth fixtures/synth/pageX_truth.txt

Использование:
  .venv/bin/python cer.py --results results/ --truth-dir fixtures/synth/ --dpi 150
throw away: ТЗ раздел 12, spike не в проде.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

WS = re.compile(r"\s+")


def normalize(text: str, case_sensitive: bool = True) -> str:
    """Нормализация: пробелы к одному, ё→е. Регистр СОХРАНЯЕМ (строгий режим) —
    понижение регистра занижает CER (находка ревьюера #8). Режим по умолчанию строгий.
    """
    if not case_sensitive:
        text = text.lower()
    text = text.replace("ё", "е")
    return WS.sub(" ", text).strip()


def texts_from_html(html: str) -> str:
    """Вырезаем текст из block HTML, сохраняем одиночные пробелы между тегами."""
    html = re.sub(r"<(script|style)[^>]*>.*?</\\1>", " ", html, flags=re.S | re.I)
    html = re.sub(r"<[^>]+>", " ", html)
    return WS.sub(" ", html).strip()


def lev(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def cer(guess: str, truth: str) -> float:
    guess, truth = normalize(guess), normalize(truth)
    return lev(guess, truth) / max(len(truth), 1)


def parse_results(path: Path, page_filter: str | None) -> dict[str, str]:
    """Возвращает {fixture_key: 'распознанный текст'} по results.json surya."""
    data = json.loads(path.read_text(encoding="utf-8"))
    # surya results.json: {input_filename_nor_ext: [page, ...]}
    out: dict[str, str] = {}
    for key, pages in data.items():
        if page_filter and page_filter not in key:
            continue
        texts = []
        for page in pages:
            for block in page.get("blocks", []):
                t = texts_from_html(block.get("html") or "")
                if t:
                    texts.append(t)
        out[key] = " ".join(texts)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True, help="results.json (или каталог с ними)")
    ap.add_argument("--truth-dir", default=str(Path(__file__).parent / "synth"))
    ap.add_argument("--dpi", default="")
    args = ap.parse_args()

    results = Path(args.results)
    files = sorted(results.glob("results.json")) if results.is_dir() else [results]

    rows = []
    for rf in files:
        for key, guess in parse_results(rf, None).items():
            for tp in sorted(Path(args.truth_dir).glob("*_truth.txt")):
                name = tp.stem.replace("_truth", "")
                if name in key:
                    truth = tp.read_text(encoding="utf-8")
                    rows.append((key, tp.stem, cer(guess, truth)))
    if not rows:
        print("parse: no fixture matched — проверь имена files в results.json", file=sys.stderr)
        sys.exit(1)
    print("file,fixture,cer")
    for key, fix, val in rows:
        print(f"{key},{fix},{val:.4f}")
    bad = [r for r in rows if r[2] > 0.03]
    if bad:
        print(f"WARN: {len(bad)} fixture выше порога 3%", file=sys.stderr)


if __name__ == "__main__":
    main()
