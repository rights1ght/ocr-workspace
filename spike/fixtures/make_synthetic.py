#!/usr/bin/env python3
"""OCR spike Task 3: синтетические эталонные фикстуры (throwaway).

Создаёт (рядом с этим файлом):
  synth/page12pt.png + synth/page12pt_truth.txt   — 12pt: заголовок, 4 абзаца, список
  synth/page9pt.png  + synth/page9pt_truth.txt    — 9pt мелкий текст
  synth/photo12pt.jpg                              — page12pt, повёрнутая на 90°, EXIF Orientation 6
  synth/tables/t1.png + synth/tables/t1_structure.txt  — 5x4 простая
  synth/tables/t3.png + synth/tables/t3_structure.txt  — 4x3 с rowspan и colspan

Запуск:  .venv/bin/python fixtures/make_synthetic.py
Проверка Task 3: каждый truth-файл не пуст и совпадает по символам с нарисованным.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
DPI = 300
W, H = 2480, 3508  # A4 @ 300 dpi
MARGIN = 160
FONT_R = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_B = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

TITLE = "Проверка распознавания: эталонная страница 12pt"
PHONE = "+79261234567"

PARAS_12 = [
    "Проверка качества распознавания русского текста начинается с простого случая: печатные абзацы размером 12 пунктов на белом фоне при 300 dpi. Такой текст называется эталонным, потому что его точное содержание известно заранее и хранится в отдельном файле.",
    "Норма символьной ошибки вычисляется как отношение расстояния Левенштейна между распознанным текстом и эталоном к длине эталона. Для печатного русского текста при 150 dpi цель составляет не более 3 процентов, а порог пересмотра движка — 8 процентов.",
    f"Второй абзац сознательно содержит латинские вставки, например GDP, ISO 9001 и HTTP/2, чтобы проверить смешанный текст. Числа тоже нужны: 1987, 12,5, 40 проц, № 221, телефон {PHONE} и индекс 119021.",
    "Завершает страницу абзац с пунктуацией разных видов: кавычки-ёлочки «так», тире — и дефис-короткое словцо. Если модель теряет кавычки или путает тире с дефисом, это попадает в отчёт как структурная потеря.",
]
LIST_12 = [
    "первый пункт списка с номером один",
    "второй пункт со словом таблица",
    "третий пункт, он же последний",
]
PARAS_9 = [
    "Мелкий шрифт 9 пунктов сильнее всего распадается при понижении разрешения до 96 dpi. В этой строке намеренно использованы частые буквы кириллицы: местные торговые ведомости приветствуют инспекцию.",
    "Вторая строка мелкого текста проверяет сноски и единицы измерения, которые встречаются в справочных изданиях: 0,5 г/м3, 20 град и давление 101325 Па.",
]

T1 = [
    ["Товар", "Кол-во", "Цена, руб", "Сумма, руб"],
    ["Тетрадь 48 листов", "12", "45,50", "546,00"],
    ["Ручка синяя", "25", "18,20", "455,00"],
    ["Линейка 30 см", "8", "32,00", "256,00"],
    ["Итого", "45", "", "1257,00"],
]
# сетка: None — продолжение ячейки слева/сверху (merged)
T3 = [
    ["Месяц", "План", "Факт"],
    ["Январь", "120", "118"],
    ["Февраль", None, "133"],  # rowspan: слева Февраль, справа 130 на 2 строки
    ["Март", "Итого: 260", None],  # colspan на последней строке
]
T3_MERGED = {"rowspan": [("130", 1, 1, 2, 1)], "colspan": [("Итого: 260", 3, 1, 1, 2)]}


def _font(size_pt: float, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT_B if bold else FONT_R, int(round(size_pt * DPI / 72)))


def _wrap(d, text: str, font: ImageFont.FreeTypeFont, width: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w_ in words:
        cand = f"{cur} {w_}" if cur else w_
        if d.textlength(cand, font=font) > width:
            if cur:
                lines.append(cur)
            cur = w_
        else:
            cur = cand
    if cur:
        lines.append(cur)
    return lines


def _write_page(path: Path, font_pt: float, blocks: list[str], bold_first: bool = True) -> str:
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    y = MARGIN
    truth: list[str] = []
    for i, text in enumerate(blocks):
        is_title = bold_first and i == 0
        font = _font(font_pt + 4, bold=True) if is_title else _font(font_pt)
        for ln in _wrap(d, text, font, W - 2 * MARGIN):
            d.text((MARGIN, y), ln, font=font, fill="black")
            y += int(font.size * 1.45)
            truth.append(ln)
        y += int(font.size * 0.7)
    img.save(path)
    return " ".join(truth)


def _draw_table_t1(d, x0: int, y0: int, rows: list[list[str]], cw: int, ch: int) -> None:
    for r, row in enumerate(rows):
        for c, cell in enumerate(row):
            box = [x0 + c * cw, y0 + r * ch, x0 + (c + 1) * cw, y0 + (r + 1) * ch]
            d.rectangle(box, width=6)
            font = _font(11, bold=(r == 0))
            d.text((box[0] + 20, box[1] + 36), cell, font=font, fill="black")


def draw_table(path: Path, rows: list[list[str]], tag: str) -> str:
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    cw, ch = 560, 180  # 4 колонки * 560 + поля ≤ 2480
    x0, y0 = MARGIN, MARGIN + 320
    if tag == "t1":
        _draw_table_t1(d, x0, y0, rows, cw, ch)
        n_rows, n_cols = len(rows), 4
        merged = {}
    else:
        # t3: чистая сетка 4x3 c учётом merged (rowspan на (1,1), colspan на (3,1))
        n_rows, n_cols = 4, 3
        cx = [x0 + j * cw for j in range(n_cols + 1)]
        cy = [y0 + j * ch for j in range(n_rows + 1)]
        span = T3_MERGED
        # рисуем вручную: базовая сетка + удаление внутренних линий merged
        for i in range(n_rows + 1):
            d.line([cx[0], cy[i], cx[-1], cy[i]], fill="black", width=3)
        for j in range(n_cols + 1):
            d.line([cx[j], cy[0], cx[j], cy[-1]], fill="black", width=3)
        # rowspan "130": ячейка (1,1) тянется на строку 2 → убираем горизонталь между 2 и 3 в колонке 1
        d.rectangle([cx[1], cy[1], cx[2], cy[3]], width=3)
        d.line([cx[1], cy[2], cx[2], cy[2]], fill="white", width=3)
        # colspan "Итого: 260": ячейка (3,1) тянется на колонку 2 → убираем вертикаль
        d.rectangle([cx[1], cy[3], cx[3], cy[4]], width=3)
        d.line([cx[2], cy[3], cx[2], cy[4]], fill="white", width=3)
        for (txt, r, c, rs, cs) in [(v, a, b, rr, cc) for (v, a, b, rr, cc) in span["rowspan"] + span["colspan"]]:
            font = _font(11)
            d.text((cx[c] + 24, cy[r] + 60), txt, font=font, fill="black")
        # простые ячейки; (1,1)='130' рисуется в цикле merged-ячеек (rowspan)
        simple = {
            (0, 0): "Месяц", (0, 1): "План", (0, 2): "Факт",
            (1, 0): "Январь", (1, 2): "118",
            (2, 0): "Февраль", (2, 2): "133",
            (3, 0): "Март",
        }
        for (r, c), txt in simple.items():
            d.text((cx[c] + 24, cy[r] + 36), txt, font=_font(11), fill="black")
        merged = {"rowspan": 1, "colspan": 1}
    img.save(path)
    header = " | ".join(rows[0])

    structure = (
        f"tag={tag} rows={n_rows} cols={n_cols} merged={merged}\n"
        f"header: {header}\n"
        f"rowspan: '130' занимает строки 2-3 колонки 2\n"
        f"colspan: 'Итого: 260' занимает колонки 2-3 строки 4\n"
    )
    return structure


def main() -> None:  # pragma: no cover — throwaway spike
    synth = ROOT / "synth"
    tables = synth / "tables"
    tables.mkdir(parents=True, exist_ok=True)

    blocks12: list[str] = [TITLE, *PARAS_12, *(f"{i}. {item}" for i, item in enumerate(LIST_12, 1))]
    truth12 = _write_page(synth / "page12pt.png", 12, blocks12)
    (synth / "page12pt_truth.txt").write_text(truth12, encoding="utf-8")

    blk9 = ["Справочные данные 9pt", *PARAS_9]
    truth9 = _write_page(synth / "page9pt.png", 9, blk9)
    (synth / "page9pt_truth.txt").write_text(truth9, encoding="utf-8")

    (synth / "tables/t1_structure.txt").write_text(draw_table(tables / "t1.png", T1, "t1"), encoding="utf-8")
    (synth / "tables/t3_structure.txt").write_text(draw_table(tables / "t3.png", T3, "t3"), encoding="utf-8")

    # photo12pt: поворот +90° COL при сохранении и EXIF Orientation 6 => прямое положение при exif_transpose
    src = Image.open(synth / "page12pt.png")
    # храним повёрнутой ПРОТИВ часовой (90° CCW): тогда EXIF Orientation 6 («повернуть на 90° CW»)
    # восстанавливает прямое положение через ImageOps.exif_transpose (Review Focus #4)
    rotated = src.rotate(90, expand=True)
    ex = rotated.getexif()
    ex[0x112] = 6  # Orientation
    rotated.save(synth / "photo12pt.jpg", quality=92, exif=ex.tobytes())

    print("generated:", synth)


if __name__ == "__main__":
    main()
