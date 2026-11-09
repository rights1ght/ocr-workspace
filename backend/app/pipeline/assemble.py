"""Сборка канонического HTML документа (OCR/TZ §7.4)."""
from __future__ import annotations

import html as htmod
import re

_BR = re.compile(r"\s*\n\s*")
_EMPTY_LINE = re.compile(r"\n{2,}")


def _paragraphize(raw: str) -> list[str]:
    """Плейн-текст → список абзацев (по двойным переводам строк)."""
    parts = _EMPTY_LINE.split(raw.strip())
    return [re.sub(r"[ \t]+", " ", p.replace("\n", " ")).strip() for p in parts if p.strip()]


def _is_heading_like(text: str) -> bool:
    leading = text.strip()
    return 6 < len(leading) < 200 and (leading.endswith(":") or re.fullmatch(r"[^а-яё.]{0,60}", leading)) and not leading.endswith(".")


def assemble_from_text(
    text: str,
    pages_paragraphs: list[list[str]] | None = None,
    page_breaks_after: list[int] | None = None,
    source_type: str = "txt",
) -> str:
    """Собирает HTML из плейн-текста (txt/docx/pdf_text).

    pages_paragraphs — опциональное разбиение по страницам (§7.4 п.12: <hr data-page-break>).
    """
    if pages_paragraphs is None:
        pages_paragraphs = [_paragraphize(text)]
    paragraphs = [p for grp in pages_paragraphs for p in grp]
    if isinstance(page_breaks_after, int):
        page_breaks_after = [page_breaks_after]
    break_set = set(page_breaks_after or [])

    title = paragraphs[0] if paragraphs else "Без названия"
    out: list[str] = [f'<h1 data-src-page="1" data-src-block="b-1-0">{htmod.escape(title)}</h1>']
    order = 1
    done = 0
    for page_idx, grp in enumerate(pages_paragraphs, start=1):
        for para in grp:
            if para == title and done == 0:
                done = 1
                continue
            order += 1
            out.append(
                f'<p data-src-page="{page_idx}" data-src-block="b-1-{order}">{htmod.escape(para)}</p>'
            )
        if page_idx in break_set:
            out.append(f'<hr data-page-break="{page_idx}">')
    return "\n".join(out)


def assemble_document(
    source_type: str,
    *,
    text: str,
    pages_paragraphs: list[list[str]] | None = None,
    blocks_by_page: list[list[dict]] | None = None,
) -> str:
    """Точка входа сборки: pdf_text/docx/txt — текстовые; скан (этап 2) добавит блоки."""
    if blocks_by_page:
        from app.pipeline.blocks import blocks_to_html

        return blocks_to_html(blocks_by_page)
    return assemble_from_text(text, pages_paragraphs, source_type=source_type)
