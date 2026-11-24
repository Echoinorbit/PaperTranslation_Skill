"""Conservative PDF layout hints for choosing a fallback after reviewed anchors."""

import re
import statistics

import pymupdf as pdf


SUSPECT_GLYPHS = re.compile("[\ufffd\ue000-\uf8ff\U000f0000-\U000ffffd\U00100000-\U0010fffd]")


def text_blocks(page):
    return page.get_text("dict", flags=pdf.TEXTFLAGS_DICT & ~pdf.TEXT_PRESERVE_IMAGES)["blocks"]


def text_layer_state(text):
    chars = "".join(text.split())
    if not chars:
        return "none"
    suspect = len(SUSPECT_GLYPHS.findall(chars))
    if suspect >= 3 and suspect / len(chars) >= .025:
        return "suspicious"
    return "sparse" if len(chars) < 100 else "present"


def visibly_blank(page):
    pixels = page.get_pixmap(matrix=pdf.Matrix(.5, .5), colorspace=pdf.csGRAY, alpha=False)
    return min(pixels.samples) >= 250


def image_footprint(page):
    # A small coverage grid counts each occupied cell once, even with overlaid masks.
    grid = 40
    rows = [0] * grid
    wide_image = False
    for image in page.get_image_info():
        box = pdf.Rect(image["bbox"]) & page.rect
        if box.is_empty:
            continue
        left, right = (round(grid * x / page.rect.width) for x in (box.x0, box.x1))
        top, bottom = (round(grid * y / page.rect.height) for y in (box.y0, box.y1))
        mask = ((1 << (right - left)) - 1) << left
        for row in range(top, bottom):
            rows[row] |= mask
        if box.width > .62 * page.rect.width and box.get_area() > .10 * page.rect.get_area():
            wide_image = True
    return sum(row.bit_count() for row in rows) / grid**2, wide_image


def parallel_columns(lines, count):
    # Long lines must recur at comparable heights in *each* proposed column.
    # This rejects a footer on the right below an all-left introductory passage.
    bands = [set() for _ in range(count)]
    for left, right, y in lines:
        column = max(0, min(count - 1, int((left + right) * .5 * count)))
        if left >= column/count - .025 and right <= (column+1)/count + .025:
            if right - left >= .46/count:
                bands[column].add(int(y*32))
    return len(set.intersection(*bands)) >= 3


def layout_hint(page, blocks=None):
    if blocks is None:
        blocks = text_blocks(page)
    width, height = page.rect.width, page.rect.height
    body = []
    all_text = []
    for block in blocks:
        for line in block.get("lines", []):
            box = pdf.Rect(line["bbox"]) & page.rect
            if box.is_empty:
                continue
            text = "".join(span["text"] for span in line["spans"])
            all_text.append(text)
            y = (box.y0 + box.y1) / (2 * height)
            # Suppress page furniture, vertical axis labels and short table entries.
            if .065 < y < .935 and line["dir"][0] > .97 and sum(ch.isalpha() for ch in text) >= 15:
                body.append((box.x0/width, box.x1/width, y))

    state = text_layer_state("".join(all_text))
    coverage, wide_image = image_footprint(page)
    columns = 1
    layout = "undetermined"
    if state == "none" and coverage == 0 and visibly_blank(page):
        layout = "blank"
    if state == "present":
        wide = [(left, right, y) for left, right, y in body
                if left < .40 and right > .60 and right-left >= .48]
        wide_ys = {y for _, _, y in wide}
        if parallel_columns(body, 3) or parallel_columns(body, 4):
            layout = "possible_multi_column"
        elif parallel_columns(body, 2):
            columns = 2
            # An ordinary title or running heading can span both columns.
            layout = "mixed" if len(wide_ys) >= 3 or wide_image else "two_column"
        elif len(wide_ys) >= 4 and len(body) >= 5:
            # A wide primary column can have a narrow metadata sidebar. Retain a
            # single reading column when original targets have not been reviewed.
            main_left = statistics.median(left for left, _, _ in wide)
            main_right = statistics.median(right for _, right, _ in wide)
            side_bands = {int(y*32) for left, right, y in body
                          if right < main_left-.025 or left > main_right+.025}
            wide_bands = {int(y*32) for y in wide_ys}
            layout = "mixed" if len(side_bands & wide_bands) >= 3 else "single_column"
    orientation = "square" if abs(width-height) < 1 else ("landscape" if width > height else "portrait")
    return {"orientation": orientation, "text_layer": state, "layout": layout,
            "image_coverage": round(coverage, 3), "flow_columns": columns,
            "needs_layout_review": layout not in {"single_column", "two_column"} or coverage >= .35}
