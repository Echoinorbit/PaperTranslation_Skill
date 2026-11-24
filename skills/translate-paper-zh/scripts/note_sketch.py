"""Small searchable hand-drawn comparisons and method diagrams for a PDF note."""

from dataclasses import dataclass

import pymupdf as pdf


SIZE = 10.3
INK = (.16, .15, .13)
BRUSH = (.97, .86, .54)


@dataclass
class Sketch:
    kind: str
    rows: list[list[str]]
    widths: list[float]
    height: float
    focus: tuple[int, int] | None


def parse_sketch(spec, pen, width):
    if spec is None:
        return None
    if not isinstance(spec, dict):
        raise ValueError("sketch must be a flow or table object")
    kind = spec.get("kind")
    if kind == "flow":
        rows = [spec.get("steps")]
        min_cols, max_rows, spacing = 2, 1, 13
    elif kind == "table":
        rows = spec.get("rows")
        min_cols, max_rows, spacing = 2, 5, 3
    else:
        raise ValueError("choose flow or table for sketch.kind")
    if not isinstance(rows, list) or not 1 <= len(rows) <= max_rows:
        raise ValueError("provide a short sketch with one to five rows")
    if not isinstance(rows[0], list) or not min_cols <= len(rows[0]) <= 3:
        raise ValueError("use two or three sketch columns or steps")
    count = len(rows[0])
    if any(not isinstance(row, list) or len(row) != count for row in rows):
        raise ValueError("sketch rows must have equal length")
    for row in rows:
        if any(not isinstance(label, str) or not label.strip() or len(label.splitlines()) != 1 for label in row):
            raise ValueError("a sketch label must fit on a single line")
    if kind == "table" and len(rows) < 2:
        raise ValueError("a sketch table needs a heading and a data row")
    widths = [max(pen.text_length(row[i], fontsize=SIZE) for row in rows) + 7 for i in range(count)]
    space = width - sum(widths) - (count - 1) * spacing
    if space < 0:
        raise ValueError("sketch labels exceed the available width; shorten them")
    widths = [w + min(space / count, 10) for w in widths]
    focus = spec.get("focus")
    if focus is not None:
        if (kind != "table" or not isinstance(focus, list) or len(focus) != 2
                or any(type(i) is not int for i in focus)
                or not 0 <= focus[0] < len(rows) or not 0 <= focus[1] < count):
            raise ValueError("sketch.focus must locate a table cell by zero-based row and column")
        focus = tuple(focus)
    height = 27 if kind == "flow" else 16 * len(rows) + 8
    return Sketch(kind, rows, widths, height, focus)


def label(page, x, y, text, pen, box_width):
    x += (box_width - pen.text_length(text, fontsize=SIZE)) / 2
    writer = pdf.TextWriter(page.rect)
    for face, run, scale in pen.runs(text):
        writer.append((x, y), run, font=face, fontsize=SIZE * scale)
        x += face.text_length(run, fontsize=SIZE * scale)
    writer.write_text(page, color=INK)


def stroke(page, points, color, width=.8):
    page.draw_polyline(points, color=color, width=width, lineCap=1, lineJoin=1)


def draw_sketch(page, sketch, x, top, pen, color):
    if sketch.kind == "flow":
        for i, (name, width) in enumerate(zip(sketch.rows[0], sketch.widths)):
            end = x + width
            stroke(page, [(x+1,top+4),(end-.8,top+3.6),(end,top+20),
                          (x+.2,top+20.4),(x+1,top+4)], color)
            label(page, x, top+15.3, name, pen, width)
            if i + 1 < len(sketch.widths):
                stroke(page, [(end+1.5,top+12.3),(end+10.8,top+11.9)], color)
                stroke(page, [(end+7.8,top+9.6),(end+10.8,top+11.9),(end+7.6,top+14.2)], color)
            x = end + 13
        return
    right = x + sum(sketch.widths) + 3 * (len(sketch.widths) - 1)
    for index, row in enumerate(sketch.rows):
        left = x
        baseline = top + 12 + index * 16
        for column, (name, width) in enumerate(zip(row, sketch.widths)):
            if sketch.focus == (index, column):
                page.draw_polyline([(left+.5, baseline-8.3), (left+width-1, baseline-9.1),
                                    (left+width-.4, baseline+1.2), (left+.3, baseline+2.1)],
                                   color=None, fill=BRUSH, closePath=True)
            label(page, left, baseline, name, pen, width)
            left += width + 3
        if index == 0 or index == len(sketch.rows) - 1:
            stroke(page, [(x+.7,baseline+3.1), ((x+right)/2,baseline+3.5),
                          (right-.5, baseline+2.8)], color, .65)
