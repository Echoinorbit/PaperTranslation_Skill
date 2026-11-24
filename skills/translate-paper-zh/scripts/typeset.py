"""Position reviewed Chinese text and preserve original PDF figure/formula objects."""

import math
import re
import statistics
from collections import Counter
from functools import lru_cache
from pathlib import Path

import pymupdf as pdf

from layout import layout_hint


FONT = pdf.Font("cjk")
NOTEBOOK_PAPER = (250/255, 243/255, 227/255)
GRAPHICS = {"figure", "table", "formula"}
TOKENS = re.compile(r"[A-Za-z0-9]+(?:[./_′’'−+–-][A-Za-z0-9]+)*|[ \t]+|[^\n]")
CLOSING = "，。！？、；：）】》”’％,.!?;:)]"


@lru_cache(maxsize=1)
def notebook_font():
    path = Path(__file__).resolve().parent.parent / "assets" / "fonts" / "LXGWWenKai-Regular.ttf"
    return pdf.Font(fontfile=str(path))


@lru_cache(maxsize=32768)
def unit_width(text, font=FONT):
    return font.text_length(text, fontsize=1)


def wrap(text, width, size, font=FONT):
    lines = []
    for part in text.splitlines():
        line = ""
        used = 0.0
        for token in TOKENS.findall(part):
            tokens = list(token) if unit_width(token, font) * size > width else [token]
            for word in tokens:
                if word.isspace() and not line:
                    continue
                advance = unit_width(word, font) * size
                if line and used + advance > width:
                    carry = ""
                    if word in CLOSING and len(line.rstrip()) > 1:
                        trimmed = line.rstrip()
                        last = re.search(r"[A-Za-z0-9]+(?:[._/–-][A-Za-z0-9]+)*$", trimmed)
                        tail = last.group() if last else trimmed[-1]
                        if len(tail) < len(trimmed) and unit_width(tail + word, font) * size <= width:
                            carry, line = tail, trimmed[:-len(tail)]
                    lines.append(line.rstrip())
                    line = carry
                    used = unit_width(carry, font) * size
                    if word.isspace():
                        continue
                line += word
                used += advance
        if line.strip():
            lines.append(line.strip())
    return lines


def ink(page, x, baseline, lines, size, leading, *, strong=False, font=FONT):
    pen = pdf.TextWriter(page.rect)
    for i, line in enumerate(lines):
        y = baseline + i * leading
        if font is FONT:
            pen.append((x, y), line, font=font, fontsize=size)
        else:
            # WenKai shares glyphs for hyphen / nonbreaking hyphen and for middle dot /
            # bullet operator. Emit these two using distinct Unicode mappings so model
            # names, identifiers and URLs can be searched and copied as authored.
            xpos = x
            for run in re.findall(r"[-·]|[^-·]+", line):
                face = FONT if run in ("-", "·") else font
                pen.append((xpos, y), run, font=face, fontsize=size)
                xpos += font.text_length(run, fontsize=size)
    # Fill and stroke the same glyphs to keep CJK line widths and search intact.
    pen.write_text(page, render_mode=2 if strong else 0)


def is_emphasized(item):
    return item["kind"] == "heading" or item.get("emphasis") == "strong"


def body_metrics(source):
    lines = [line for block in source.get_text("dict", flags=pdf.TEXTFLAGS_DICT & ~pdf.TEXT_PRESERVE_IMAGES)["blocks"]
             for line in block.get("lines", [])]
    sizes = [s["size"] for line in lines for s in line["spans"]
             if len(s["text"].strip()) >= 20 and 7 <= s["size"] <= 16]
    return statistics.median(sizes) if sizes else 10


def columns_for(source):
    return layout_hint(source)["flow_columns"]


def interior_glyphs(spans, crop):
    counts = Counter()
    for span in spans:
        for char, glyph, _, (left, top, right, bottom) in span["chars"]:
            # Use coordinates: an empty Rect can be considered contained even
            # when its zero-advance combining glyph is far outside this crop.
            if crop.x0 <= left <= right <= crop.x1 and crop.y0 <= top <= bottom <= crop.y1:
                counts[(span["font"], char, glyph)] += 1
    return counts


def redact_surrounding_text(page, crop):
    x0, y0, x1, y1 = page.rect
    for strip in (pdf.Rect(x0, y0, x1, crop.y0), pdf.Rect(x0, crop.y1, x1, y1),
                  pdf.Rect(x0, crop.y0, crop.x0, crop.y1), pdf.Rect(crop.x1, crop.y0, x1, crop.y1)):
        if not strip.is_empty:
            page.add_redact_annot(strip, fill=False, cross_out=False)
    page.apply_redactions(images=pdf.PDF_REDACT_IMAGE_NONE, graphics=pdf.PDF_REDACT_LINE_ART_NONE,
                          text=pdf.PDF_REDACT_TEXT_REMOVE)


class Flow:
    def __init__(self, result, srcdoc, entry, preview, notebook_paper=False):
        self.result, self.doc = result, srcdoc
        self.notebook_paper = notebook_paper
        self.font = notebook_font() if notebook_paper else FONT
        self.number = entry["page"]
        self.source = srcdoc[self.number - 1]
        self.width, self.height = self.source.rect.width, self.source.rect.height
        self.columns = entry["columns"] if "columns" in entry else columns_for(self.source)
        if type(self.columns) is not int or self.columns not in (1, 2):
            raise ValueError("columns must be 1 or 2")
        self.margin = min(46, self.width * 0.075)
        self.top, self.bottom = 37, self.height - 35
        self.gap = 18
        self.full_width = self.width - self.margin * 2
        self.col_width = (self.full_width - self.gap * (self.columns-1)) / self.columns
        self.base = max(8.5, min(12, body_metrics(self.source)))
        if self.col_width < self.base*4 or self.bottom-self.top < self.base*4:
            raise ValueError(f"Source page {self.number} is too small for the selected reading layout")
        self.preview = preview
        self.output_start = len(result)
        self.page = None
        self.placements = []
        self.graphic_boxes = []
        self.source_trace = None
        self.glyph_preserving_crops = []
        self.footers = []
        for index, item in enumerate(entry["items"]):
            if item.get("role") == "footer":
                self.footers.append((index, wrap(item["zh"], self.full_width, 7.5, self.font)))
        if self.footers:
            self.bottom = self.height - 26 - sum(len(lines)*10+3 for _, lines in self.footers)

    def finish(self):
        y = self.bottom + 4
        for index, lines in self.footers:
            ink(self.page, self.margin, y+7.5, lines, 7.5, 10, font=self.font)
            self.remember(index, (self.margin, y, self.width-self.margin, y+len(lines)*10))
            y += len(lines)*10+3
        if self.notebook_paper:
            # Leave the original paper exposed under photographs and plots. Even
            # repainting those areas white changes blending on transparent images.
            for number in range(self.output_start, len(self.result)):
                page = self.result[number]
                background = page.new_shape()
                background.draw_rect(page.rect)
                for graphic in self.graphic_boxes:
                    if graphic["out"] == number + 1:
                        background.draw_rect(pdf.Rect(graphic["box"]))
                background.finish(color=None, fill=NOTEBOOK_PAPER, even_odd=True)
                background.commit(overlay=False)

    def new_page(self):
        self.page = self.result.new_page(width=self.width, height=self.height)
        self.column = 0
        self.cursor = [self.top] * self.columns
        marker = f"原第 {self.number} 页"
        if self.page.number > self.output_start:
            marker = f"接{marker}"
        if self.preview:
            marker += "  ·  校对样张"
        ink(self.page, self.margin, self.height - 15, [marker], 8, 10, font=self.font)

    def next_column(self):
        if self.column + 1 < self.columns:
            self.column += 1
        else:
            self.new_page()

    def remember(self, item, rect):
        self.placements.append({"item": item, "out": self.page.number + 1,
                                "box": [round(n, 2) for n in rect]})

    def text(self, item, index):
        size = self.base * {"heading": 1.19, "caption": .94, "keep": .90}.get(item["kind"], 1)
        if item["kind"] != "keep":
            size = max(8, size)
        leading = size * 1.42
        lines = wrap(item["zh"], self.col_width, size, self.font)
        pos = 0
        while pos < len(lines):
            y = self.cursor[self.column]
            room = math.floor((self.bottom - y) / leading)
            if room < min(2, len(lines) - pos) or (item["kind"] == "heading" and room < len(lines) + 2):
                if y > self.top or self.column:
                    self.next_column()
                    continue
            count = min(max(1, room), len(lines) - pos)
            x = self.margin + self.column * (self.col_width + self.gap)
            ink(self.page, x, y + size * 1.05, lines[pos:pos+count], size, leading,
                strong=is_emphasized(item), font=self.font)
            self.remember(index, (x, y, x+self.col_width, y+count*leading))
            self.cursor[self.column] = y + count * leading + size * .48
            pos += count
            if pos < len(lines):
                self.next_column()

    def place_crop(self, target, crop):
        # A placement clip alone hides outside text but leaves it in the PDF's
        # searchable form. Trim an isolated page before importing that form.
        with pdf.open() as isolated:
            isolated.insert_pdf(self.doc, from_page=self.number - 1, to_page=self.number - 1,
                                links=False, annots=False, widgets=False)
            if self.source_trace is None:
                self.source_trace = self.source.get_texttrace()
            expected = interior_glyphs(self.source_trace, crop)
            isolated[0].clip_to_rect(crop)
            selected = 0
            if expected and expected - interior_glyphs(isolated[0].get_texttrace(), crop):
                # MuPDF's geometric clip can discard printable marks whose font
                # advance is zero (e.g. a slash drawn on top of an equals sign).
                # Strip outside text on a fresh copy; the final Form clip keeps
                # the original outlines, color and partial vector paths in view.
                isolated.insert_pdf(self.doc, from_page=self.number - 1, to_page=self.number - 1,
                                    links=False, annots=False, widgets=False)
                selected = 1
                redact_surrounding_text(isolated[selected], crop)
                if expected - interior_glyphs(isolated[selected].get_texttrace(), crop):
                    raise ValueError(f"Source page {self.number}: crop loses glyphs; check the bounds {crop}")
                self.glyph_preserving_crops.append(list(crop))
            if self.notebook_paper:
                # show_pdf_page fits the crop proportionally inside its target.
                scale = min(target.width / crop.width, target.height / crop.height)
                center = (target.tl + target.br) * 0.5
                half = pdf.Point(crop.width * scale / 2, crop.height * scale / 2)
                exposed = pdf.Rect(center - half, center + half)
                self.graphic_boxes.append({"out": self.page.number + 1, "box": list(exposed)})
            self.page.show_pdf_page(target, isolated, selected, clip=crop)

    def graphic(self, item, index):
        crop = pdf.Rect(item["bbox"])
        if crop.get_area() > .91 * self.source.rect.get_area():
            raise ValueError(f"Page {self.number}: select the actual object, not the entire source page")
        full = self.columns == 1 or crop.width > self.col_width * 1.12
        width = self.full_width if full else self.col_width
        size = max(8, self.base * .93)
        leading = size * 1.4
        lines = wrap(item["zh"], width, size, self.font)
        label_height = len(lines) * leading + 6
        height_limit = self.bottom - self.top - label_height
        if height_limit < min(42, crop.height * .6):
            raise ValueError(f"Page {self.number}, object {index}: split into labelled subpanels or table row groups")
        scale = min(width / crop.width, height_limit / crop.height, 1.12)
        if scale < .60:
            raise ValueError(f"Page {self.number}, object {index}: split a tall object for readable labels")
        w, h = crop.width * scale, crop.height * scale
        height = h + label_height
        y = max(self.cursor) if full else self.cursor[self.column]
        if y + height > self.bottom + .001:
            if full:
                self.new_page()
            else:
                self.next_column()
                if self.cursor[self.column] + height > self.bottom + .001:
                    self.new_page()
            y = max(self.cursor) if full else self.cursor[self.column]
        x = self.margin if full else self.margin + self.column * (self.col_width + self.gap)
        dest = pdf.Rect(x+(width-w)/2, y, x+(width+w)/2, y+h)
        self.place_crop(dest, crop)
        ink(self.page, x, y+h+size+4, lines, size, leading, font=self.font)
        self.remember(index, (x, y, x+width, y+height))
        if full:
            self.column, self.cursor = 0, [y+height+6] * self.columns
        else:
            self.cursor[self.column] = y+height+6

    def anchored(self, items):
        # Use only explicitly reviewed target rectangles. A text extraction box can
        # span both columns or include a figure caption; it is not a safe default.
        if not all(i.get("target") and (i["kind"] not in GRAPHICS or i.get("caption_box")) for i in items):
            return 0
        occupied = []
        plans = []
        for item in items:
            target = pdf.Rect(item["target"])
            is_graph = item["kind"] in GRAPHICS
            caption = pdf.Rect(item["caption_box"]) if is_graph else target
            rects = [target, caption] if is_graph else [target]
            for box in rects:
                if box.is_empty or not self.source.rect.contains(box) or (self.footers and box.y1 > self.bottom):
                    return 0
                if any((box & other).get_area() > 1 for other in occupied):
                    return 0
                occupied.append(box)
            nominal = float(item.get("size", self.base))
            if not 5 <= nominal <= 50:
                raise ValueError("Invalid source font size")
            for ratio in (1, .95, .9, .85):
                size = nominal * ratio
                if self.notebook_paper and item["kind"] != "keep" and nominal >= 8:
                    # A reviewed caption near the size floor may need exactly 8 pt:
                    # proportional steps can otherwise jump past that usable size.
                    size = max(8, size)
                if item["kind"] != "keep" and size < 8:
                    continue
                lines = wrap(item["zh"], caption.width, size, self.font)
                if len(lines) * size * 1.30 <= caption.height:
                    plans.append((target, caption, size, lines))
                    break
            else:
                break
        for index, (target, caption, size, lines) in enumerate(plans):
            item = items[index]
            if item["kind"] in GRAPHICS:
                self.place_crop(target, pdf.Rect(item["bbox"]))
            ink(self.page, caption.x0, caption.y0+size*1.05, lines, size, size*1.30,
                strong=is_emphasized(item), font=self.font)
            self.remember(index, target | caption)
        return len(plans)

    def resume_after_anchors(self):
        for placement in self.placements:
            area = pdf.Rect(placement["box"])
            for col in range(self.columns):
                left = self.margin + col * (self.col_width+self.gap)
                if area.x0 < left+self.col_width and area.x1 > left:
                    self.cursor[col] = max(self.cursor[col], area.y1+6)
        last = pdf.Rect(self.placements[-1]["box"])
        if self.columns == 2 and last.x0 >= self.width/2:
            self.column = 1


def typeset(source, pages, output, preview=False, *, notebook_paper=False):
    summaries = []
    with pdf.open() as result:
        for entry in pages:
            flow = Flow(result, source, entry, preview, notebook_paper)
            flow.new_page()
            all_items = entry["items"]
            regular = [i for i, item in enumerate(all_items) if item.get("role") != "footer"]
            items = [all_items[i] for i in regular]
            count = flow.anchored(items)
            for placement in flow.placements:
                placement["item"] = regular[placement["item"]]
            mode = "L2"
            if count:
                mode = "L0" if count == len(items) else "L1"
                if count < len(items):
                    flow.resume_after_anchors()
            for index in range(count, len(items)):
                item = items[index]
                if item["kind"] in GRAPHICS:
                    flow.graphic(item, regular[index])
                else:
                    flow.text(item, regular[index])
            flow.finish()
            summaries.append({"source_page": entry["page"], "mode": mode, "positioned": count, "columns": flow.columns,
                              "items": len(all_items), "out_first":flow.output_start+1,
                              "out_last":len(result), "placements":flow.placements})
            if notebook_paper:
                summaries[-1]["graphic_boxes"] = flow.graphic_boxes
            if flow.glyph_preserving_crops:
                summaries[-1]["glyph_preserving_crops"] = flow.glyph_preserving_crops
        result.set_toc([[1, f"原第 {s['source_page']} 页", s["out_first"]] for s in summaries])
        result.subset_fonts()
        result.save(output, garbage=4, deflate=True)
        return {"output_pages":len(result), "pages":summaries}
