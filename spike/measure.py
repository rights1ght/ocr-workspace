#!/usr/bin/env python3
"""OCR spike Task 4: throughput/RAM/уверенность Surya 2.5 по фикстурам.

Каждая страница — отдельная строка CSV (Review Focus #5: линейка время-vs-page_no).

Использование (сервер уже запущен run-server.sh):
  .venv/bin/python measure.py --dpi 150 --out measure-results/150/per-page.csv

throw away: ТЗ раздел 12, spike не в проде.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import resource
import time
from pathlib import Path

# Дефолты ДО импорта surya: работаем через уже запущенный llama-server
os.environ.setdefault("SURYA_INFERENCE_BACKEND", "llamacpp")
os.environ.setdefault("SURYA_INFERENCE_URL", "http://127.0.0.1:8181/v1")

from PIL import Image, ImageOps  # noqa: E402

ROOT = Path(__file__).resolve().parent
FIXTURES = ROOT / "fixtures" / "synth"
LOW_CONF = 0.80
TEXT_TRUTH_HINT = {"page12pt", "page9pt"}


def server_rss_kb() -> int:
    best = 0
    for pid in (Path("/proc")).glob("[0-9]*"):
        try:
            comm = (pid / "comm").read_text().strip()
            if comm == "llama-server":
                for line in (pid / "status").read_text().splitlines():
                    if line.startswith("VmRSS:"):
                        kb = int(line.split()[1])
                        best = max(best, kb)
        except (OSError, ValueError):
            continue
    return best


def load_image(path: Path, dpi: int, cache: dict[str, Image.Image]) -> Image.Image:
    key = f"{path.name}:{dpi}"
    if key in cache:
        return cache[key]
    img = Image.open(path)
    img = ImageOps.exif_transpose(img)
    img.load()
    base_dpi = 300 if dpi != 300 else 300  # fixtures генерируются в 300 dpi
    if dpi < 300:
        scale = dpi / base_dpi
        img = img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))), Image.LANCZOS)
    cache[key] = img
    return img


def pdf_pages(pdf_path: Path, dpi: int) -> list[Image.Image]:
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(pdf_path)
    pages = []
    for i in range(len(pdf)):
        page = pdf[i]
        bitmap = page.render(scale=dpi / 72)
        pages.append(bitmap.to_pil())
    return pages


def collect_images(dpi: int, pdf20: Path) -> list[tuple[str, Image.Image]]:
    cache: dict[str, Image.Image] = {}
    out: list[tuple[str, Image.Image]] = []
    for png in sorted(FIXTURES.glob("*.png")):
        out.append((png.stem, load_image(png, dpi, cache)))
    jpg = FIXTURES / "photo12pt.jpg"
    if jpg.exists():
        out.append((jpg.stem, load_image(jpg, dpi, cache)))
    for table in sorted((FIXTURES / "tables").glob("*.png")):
        out.append(("tables/" + table.stem, load_image(table, dpi, cache)))
    if pdf20 is not None and pdf20.exists():
        for i, page in enumerate(pdf_pages(pdf20, dpi), 1):
            out.append((f"20pages.pdf:p{i}", page))
    return out


def make_pdf20(target: Path) -> None:
    """20-страничный PDF из page12pt.png — тест на троттлинг (Review Focus #5)."""
    img = Image.open(FIXTURES / "page12pt.png").convert("RGB")
    img.save(target, "PDF", save_all=True, append_images=[img] * 19)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dpi", type=int, default=150)
    ap.add_argument("--out", default=str(ROOT / "measure-results" / "per-page.csv"))
    ap.add_argument("--with-throttle", action="store_true", help="включить 20-страничный PDF")
    ap.add_argument("--save-text", action="store_true", help="сохранить blocks JSON рядом с CSV (нужно для cer.py)")
    args = ap.parse_args()

    pdf20 = FIXTURES / "20pages.pdf"
    if args.with_throttle:
        if not pdf20.exists():
            print(">> готовлю 20pages.pdf")
            make_pdf20(pdf20)
    else:
        pdf20 = None

    from surya.inference import SuryaInferenceManager
    from surya.recognition import RecognitionPredictor

    manager = SuryaInferenceManager()
    rec = RecognitionPredictor(manager)

    images = collect_images(args.dpi, pdf20)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with out_path.open("w", newline="", encoding="utf-8") as fh:
        wr = csv.writer(fh)
        wr.writerow(["file", "page_no", "dpi", "seconds", "self_rss_kb", "server_rss_kb", "n_blocks", "n_low_conf", "low_conf_ratio"])
        for ix, (name, img) in enumerate(images, 1):
            before_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            server_before = server_rss_kb()
            t0 = time.perf_counter()
            try:
                preds = rec([img])
                elapsed = time.perf_counter() - t0
                page = preds[0]
                blocks = page.blocks if hasattr(page, "blocks") else page.get("blocks", [])
                n_blocks = len(blocks)
                n_low = sum(1 for b in blocks if (b.confidence if hasattr(b, "confidence") else b.get("confidence", 0)) < LOW_CONF)
                ratio = round(n_low / n_blocks, 3) if n_blocks else 0.0
                label = "ok"
                if args.save_text and isinstance(blocks, list) and blocks:
                    dump = [
                        (b.model_dump() if hasattr(b, "model_dump") else dict(b))
                        for b in blocks
                    ]
                    text_dir = out_path.parent / "blocks"
                    text_dir.mkdir(parents=True, exist_ok=True)
                    (text_dir / f"{name.replace('/', '__')}.json").write_text(
                        json.dumps({"file": name, "blocks": dump}, ensure_ascii=False), encoding="utf-8")
            except Exception as exc:
                elapsed = time.perf_counter() - t0
                n_blocks, n_low, ratio, label = 0, 0, "", f"ERROR:{type(exc).__name__}:{exc}"[:200]
            self_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss - before_rss
            wr.writerow([name, ix, args.dpi, round(elapsed, 2), self_rss, server_before, n_blocks, n_low, ratio])
            fh.flush()
            print(f"[{args.dpi}] {name}: {elapsed:.1f}s blocks={n_blocks} low={n_low} {label}")
    print("csv:", out_path)


if __name__ == "__main__":
    main()
