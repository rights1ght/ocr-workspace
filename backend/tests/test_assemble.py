"""Тесты сборки HTML и санитайзера (Task 5, OCR/TZ §7.4 §7.5 SEC-4)."""
import pytest


def test_sanitize_strips_script_and_handlers():
    from app.pipeline.sanitize import sanitize_html

    dirty = ('<p>ок<script>alert(1)</script></p>'
             '<p onclick="evil()" style="color:red" onclick2="x">т</p>'
             '<a href="javascript:bad()">x</a>'
             '<iframe src="http://evil"></iframe>')
    clean = sanitize_html(dirty)
    assert "script" not in clean and "alert" not in clean
    assert "onclick" not in clean
    assert "javascript:" not in clean
    assert "iframe" not in clean
    assert "<p>т</p>" in clean


def test_sanitize_keeps_allowed():
    from app.pipeline.sanitize import sanitize_html

    ok = '<table><tr><td colspan="2">x</td></tr></table><hr>'
    assert "<td colspan=\"2\">" in sanitize_html(ok)
    assert "<hr" in sanitize_html(ok)


def test_sanitize_external_link_rel():
    from app.pipeline.sanitize import sanitize_html

    out = sanitize_html('<a href="http://example.com/">сайт</a>')
    assert 'rel="noopener noreferrer"' in out
    assert "http://example.com/" in out


def test_sanitize_math_tags_live():
    from app.pipeline.sanitize import sanitize_html

    m = '<math><mrow><mi>n</mi><mo>+</mo><mn>1</mn></mrow></math>'
    assert "<mi>n</mi>" in sanitize_html(m)


def test_txt_assemble_paragraphs_with_defaults():
    from app.pipeline.assemble import assemble_from_text

    html = assemble_from_text("Заголовок документа\n\nПервый абзац.\n\nВторой абзац.")
    assert "<h1" in html and "Заголовок" in html
    assert "<p data-src-page=\"1\"" in html
    assert "Первый абзац." in html


def test_docx_assemble_escapes_lt_and_gt():
    from app.pipeline.assemble import assemble_from_text

    html = assemble_from_text("Формула a < b и 5 > 3.")
    assert "&lt;" in html and "&gt;" in html


def test_page_break_hr_uses_page_no():
    from app.pipeline.assemble import assemble_from_text

    html = assemble_from_text("Стр1 абзац.", page_breaks_after=1)
    assert '<hr data-page-break="1"' in html
