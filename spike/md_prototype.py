#!/usr/bin/env python3
"""OCR spike Task 6: сборка документа из блоков Surya → HTML → Markdown (throwaway).

Проверяемые выходы:
  measure-results/synthetic.html  (заголовок, абзацы, таблица/список, картинка из кропа)
  measure-results/synthetic.md    (то же в GFM; YAML-шапка как в ТЗ 7.4/US-8)
  measure-results/assets/img-*.png

Формулы (<math>) здесь только структурно: markdownify не решает KaTeX —
прод-конвертер (этап 3) получит ему замену. Точность формул из OCR — отдельный риск,
записывается в spike-report (Q-7).

Запуск: .venv/bin/python md_prototype.py --results results/page12pt/results.json
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from bs4 import BeautifulSoup
from markdownify import MarkdownConverter

SKIP_LABELS = {"PageHeader", "PageFooter"}


def strip_to_text(frag: str) -> str:
    return re.sub(r"<[^>]+>", "", frag).strip()


def pick(pages: list[dict]) -> dict:
    return pages[0]


def build_html(data: dict, page_img: Path, outdir: Path) -> tuple[str, int]:
    (outdir / "assets").mkdir(parents=True, exist_ok=True)
    page = pick(next(iter(data.values())))
    blocks = page.get("blocks", [])
    parts: list[str] = []
    first_heading = True
    for order, b in enumerate(sorted(blocks, key=lambda b: b.get("reading_order", 0))):
        label = b.get("label", "")
        if label in SKIP_LABELS:
            continue
        if label == "Picture":
            crop = Path("assets") / f"img-p1-{order:02d}.png"
            crop_picture(page_img, b.get("bbox", [0, 0, 0, 0]), outdir / crop)
            parts.append(f'<figure{attrs}><img src="{crop}" alt=""></figure>')
            continue
        frag = (b.get("html") or "").strip()
        if not frag:
            continue
        attrs = f' data-src-page="1" data-src-block="b-1-{order}"'
        if label in ("SectionHeader", "SubHeader"):
            tag = "h1" if first_heading else ("h2" if label == "SectionHeader" else "h3")
            first_heading = False
            parts.append(f"<{tag}{attrs}>{strip_to_text(frag)}</{tag}>")
        elif label == "ListGroup":
            parts.append(f'<div{attrs}>{frag}</div>')  # <ol>/<li> из Surya; markdownify даст нумерованный список
        elif label == "Table":
            parts.append(f'<div data-src-page="1">{frag}</div>')  # таблица уже <table>
        else:
            parts.append(f"<p{attrs}>{strip_to_text(frag)}</p>")
    return "\n".join(parts), first_heading


def crop_picture(page_img: Path, bbox: list[int], out_path: Path, pad: float = 0.02) -> None:
    from PIL import Image, ImageOps

    img = ImageOps.exif_transpose(Image.open(page_img))
    x0, y0, x1, y1 = bbox
    px, py = int((x1 - x0) * pad), int((y1 - y0) * pad)
    box = (max(0, x0 - px), max(0, y0 - py), min(img.width, x1 + px), min(img.height, y1 + py))
    img.crop(box).save(out_path)


def html_to_md(html_body: str) -> str:
    soup = BeautifulSoup(html_body, "html.parser")
    md = MarkdownConverter().convert_soup(soup) if hasattr(MarkdownConverter(), "convert_soup") \
        else MarkdownConverter().convert(soup.decode())
    md = re.sub(r"\n{3,}", "\n\n", md).strip()
    return md


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default=str(Path(__file__).parent / "results" / "page12pt" / "results.json"))
    ap.add_argument("--page-img", default=str(Path(__file__).parent / "fixtures" / "synth" / "page12pt.png"))
    ap.add_argument("--outdir", default=str(Path(__file__).parent / "measure-results"))
    args = ap.parse_args()
    outdir = Path(args.outdir)
    data = json.loads(Path(args.results).read_text(encoding="utf-8"))
    body, _ = build_html(data, Path(args.page_img), outdir)
    html = f"<!doctype html><html lang=ru><meta charset=utf-8><title>synthetic</title><article>\n{body}\n</article>"
    (outdir / "synthetic.html").write_text(html, encoding="utf-8")
    md = "---\ntitle: Проверка распознавания\nsource: synthetic\n---\n\n" + html_to_md(body)
    (outdir / "synthetic.md").write_text(md, encoding="utf-8")
    print("html:", outdir / "synthetic.html")
    print("md:", outdir / "synthetic.md")


if __name__ == "__main__":
    main()
