"""Add searchable handwritten notes to a completed, upright translation.

Usage: python annotate.py clean.pdf notes.json manuscript.pdf [--notebook-paper]
The manifest contains base_sha256 and notes. Each note supplies a one-based
translated page, ink (blue/red/yellow), anchor (unique text or one PDF-point
bbox), mark, lines, and an optional source locator. Optional inline labels
and sketches can be written inside an inspected empty region of the source
page. Reference numbers can link to verified HTTPS URLs via reference_links.
Legacy kind (evidence/calculation/idea) selects the ink only if ink is absent.
"""

import argparse
from collections import defaultdict
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import re
import struct
import tempfile
import unicodedata
from urllib.parse import urlsplit

import pymupdf as pdf
from note_sketch import Sketch, draw_sketch, parse_sketch


MARGIN = 180
PAD = 12
BODY_SIZE = 12.2
LEADING = 16.5
FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
CAVEAT_SCALE = 1.15
INLINE_SIZE = 10.5
INLINE_LEADING = 13.0
PAPER_RGB = (250, 243, 227)


def rgb(red, green, blue):
    return (red / 255, green / 255, blue / 255)


INK = {
    "blue": rgb(31, 78, 121),
    "red": rgb(166, 52, 41),
    "yellow": rgb(138, 90, 0),
}
YELLOW_MARKER = rgb(244, 223, 125)
HIGHLIGHT_OPACITY = 0.65
LEGACY_INK = {"evidence": "blue", "calculation": "yellow", "idea": "red"}
LEGACY_COLORS = {"green": "yellow", "ochre": "red"}
# Keep compact equations (even with spaces) and model names together when they fit.
BODY_TOKENS = re.compile(
    r"(?:[A-Za-zΑ-ω][A-Za-zΑ-ω_\d]*|\d+(?:\.\d+)?)(?:[ \t]*[=+×÷−≈<>≤≥*/^][ \t]*(?:[A-Za-zΑ-ω][A-Za-zΑ-ω_\d]*|\d+(?:\.\d+)?))+"
    r"|[\d.()=+/%×÷−≈<>≤≥*^–-]+(?:[ \t]+[\d.()=+/%×÷−≈<>≤≥*^–-]+)*"
    r"|[A-Za-zΑ-ω][A-Za-zΑ-ω\d¹²³\u2070-\u209f]*(?:[./_+–-][A-Za-zΑ-ω\d]+)*|[ \t]+|."
)
CLOSING_PUNCT = frozenset("，。、！？；：）】》」』”’")
TEMPLATE_LABEL = re.compile(
    r"^\s*(?:(?:[【〔\[]\s*)?AI\s*(?:手算|证据|设想|追问|阅读手稿|读书笔记)"
    r"|[【〔\[]\s*(?:研究设想|研究假设|研究问题|手算|证据|设想|追问)\s*[】〕\]]"
    r"|(?:研究设想|研究假设|研究问题|手算|证据|设想|追问)\s*[:：])",
    re.IGNORECASE,
)
PAPER_PAGE = re.compile(r"(?:原文?\s*)?第\s*([0-9]+)\s*页|\bp\.?\s*([0-9]+)\b", re.IGNORECASE)
LOCATOR = re.compile(r"§\s*[\dA-Z]+(?:\.[\dA-Z]+)*|(?:图|表|式)\s*(?:[（(]\s*[A-Za-z0-9.]+\s*[）)]|[A-Za-z0-9]+(?:[.-][A-Za-z0-9]+)*)")


class ManuscriptPen:
    """Pair WenKai and Caveat, retaining upright digits and technical strings."""

    def __init__(self, handwriting, latin, fallback, upright=None):
        self.handwriting = handwriting
        self.latin = latin
        self.fallback = fallback
        self.upright = upright or handwriting

    def runs(self, text):
        last = None
        chars = []
        for token in BODY_TOKENS.findall(text):
            script = token.isalpha() and all(unicodedata.name(c, "").startswith("LATIN") for c in token)
            # In abbreviations such as mIoU the case and the straight stems matter.
            ambiguous = any(c in "IlO" for c in token) and (sum(c.isupper() for c in token) >= 2 or len(token) == 1)
            if script and not ambiguous:
                preferred = self.latin
            elif all(ord(c) < 128 or unicodedata.category(c)[0] in "NS" or
                     unicodedata.name(c, "").startswith("GREEK") for c in token):
                preferred = self.upright
            else:
                preferred = self.handwriting
            for ch in token:
                face = preferred
                if not face.has_glyph(ord(ch)):
                    face = self.upright if self.upright.has_glyph(ord(ch)) else self.fallback
                    if not face.has_glyph(ord(ch)):
                        raise ValueError(f"no embedded handwriting font covers {ch!r} (U+{ord(ch):04X})")
                if face is not last and chars:
                    yield last, "".join(chars), CAVEAT_SCALE if last is self.latin else 1
                    chars = []
                last = face
                chars.append(ch)
        if chars:
            yield last, "".join(chars), CAVEAT_SCALE if last is self.latin else 1

    def text_length(self, text, fontsize):
        return sum(face.text_length(run, fontsize=fontsize * scale) for face, run, scale in self.runs(text))


@dataclass
class Inline:
    rect: pdf.Rect
    lines: list[str]
    sketch: Sketch | None


@dataclass
class Note:
    rect: pdf.Rect
    ink: str
    mark: str
    body: list[str]
    source: list[str]
    inline: Inline | None
    also: list[tuple[pdf.Rect, str]]
    sketch: Sketch | None
    top: float = 0

    @property
    def height(self):
        diagram = self.sketch.height if self.sketch else 0
        return LEADING * len(self.body) + diagram + 11.5 * len(self.source) + 11


def load_pen(path):
    font = pdf.Font(fontfile=str(path))
    # OS/2 fsType embedding restrictions also apply to a user-supplied face.
    data = font.buffer
    offset = int.from_bytes(data[12:16], "big") if data[:4] == b"ttcf" else 0
    count = int.from_bytes(data[offset+4:offset+6], "big")
    flags = 0
    for i in range(count):
        tag, _, position, length = struct.unpack_from(">4sIII", data, offset+12+16*i)
        if tag == b"OS/2" and length >= 10:
            flags = struct.unpack_from(">H", data, position+8)[0]
            break
    if flags & 0x0202:
        raise ValueError(f"This font restricts outline embedding: {path}")
    return font, not bool(flags & 0x0100)


def wrap_line(text, font, size, limit, *, body=False):
    result, line, width = [], "", 0.0
    tokens = BODY_TOKENS.findall(text) if body else list(text)
    for token in tokens:
        advance = font.text_length(token, fontsize=size)
        # Closing punctuation has blank space on its right. It may hang partway
        # into the reserved outer padding, never beyond the physical margin.
        if body and line and token in CLOSING_PUNCT and width + advance <= limit + min(size / 2, PAD - 2):
            line += token
            width += advance
            continue
        if line and width + advance > limit:
            if body and token in CLOSING_PUNCT and len(line) > 1 and unicodedata.east_asian_width(line[-1]) in ("W", "F"):
                result.append(line[:-1].rstrip())
                line = line[-1]
                width = font.text_length(line, fontsize=size)
            else:
                result.append(line.rstrip())
                line, width = "", 0.0
        if token.isspace() and not line:
            continue
        if advance > limit and len(token)>1:
            # An identifier longer than the entire margin must still fit.
            chunks = wrap_line(token,font,size,limit)
            result.extend(chunks[:-1])
            line = chunks[-1]
            width = font.text_length(line,fontsize=size)
            continue
        line += token
        width += advance
    if line:
        result.append(line.rstrip())
    return result


def locate(page, anchor):
    if not isinstance(anchor, dict):
        raise ValueError("anchor must contain text or bbox")
    if set(anchor) == {"text"}:
        text = anchor["text"]
        if not isinstance(text, str) or not text.strip():
            raise ValueError("anchor.text must be a nonempty string")
        matches = page.search_for(text)
        exact_count = page.get_text().casefold().count(text.casefold())
        if len(matches) != 1 or exact_count > 1:
            count = max(len(matches), exact_count)
            raise ValueError(f"expected one single-line match for {text!r}, found {count}; narrow the text or use bbox")
        rect = matches[0]
    elif set(anchor) == {"bbox"}:
        coords = anchor["bbox"]
        if (not isinstance(coords, list) or len(coords) != 4 or
                not all(type(v) in (int, float) and math.isfinite(v) for v in coords)):
            raise ValueError("anchor.bbox must contain four finite point coordinates")
        rect = pdf.Rect(coords)
    else:
        raise ValueError("anchor must contain exactly one of text or bbox")
    if rect.is_empty or not page.rect.contains(rect):
        raise ValueError(f"anchor lies outside translated page: {rect}")
    return rect


def compact_source(source, page):
    """Use just a paper locator under the handwriting, not a prose caption."""
    if not isinstance(source, str):
        raise ValueError("source must be text")
    locators = []
    for match in PAPER_PAGE.finditer(source):
        n = int(match[1] or match[2])
        if n != page:
            locators.append(f"p. {n}")
    for match in LOCATOR.finditer(source):
        locator = "".join(match.group().split()).replace("（","(").replace("）",")")
        locators.append(locator)
    return " · ".join(dict.fromkeys(locators))


def inline_label(page, spec, font):
    if spec is None:
        return None
    if not isinstance(spec, dict) or not {"bbox", "lines"} <= set(spec) <= {"bbox", "lines", "sketch"}:
        raise ValueError("inline must contain bbox and lines and may also contain sketch")
    rect = locate(page, {"bbox": spec["bbox"]})
    lines = spec["lines"]
    if (not isinstance(lines, list) or not 1 <= len(lines) <= 2 or
            not all(isinstance(s, str) and s.strip() and len(s.splitlines()) == 1 for s in lines)):
        raise ValueError("inline.lines requires one or two short handwritten lines")
    if TEMPLATE_LABEL.match(lines[0]):
        raise ValueError("remove the template heading from inline.lines")
    sketch = parse_sketch(spec.get("sketch"), font, rect.width - 4)
    sketch_height = sketch.height if sketch else 0
    if (rect.height < 16 + (len(lines) - 1) * INLINE_LEADING + sketch_height or
            any(font.text_length(s, INLINE_SIZE) + 4 > rect.width for s in lines)):
        raise ValueError("inline handwriting does not fit its bbox; shorten it or enlarge the empty rectangle")
    return Inline(rect, lines, sketch)


def read_mark(page, spec, ink):
    if not isinstance(spec, dict):
        raise ValueError("a mark requires an anchor and a mark style")
    mark = spec["mark"]
    if mark not in ("circle", "underline", "highlight", "bracket"):
        raise ValueError("choose circle, underline, bracket or highlight for mark")
    if mark == "highlight" and ink != "yellow":
        raise ValueError("choose yellow ink for a highlight")
    return locate(page, spec["anchor"]), mark


def prepare_notes(doc, raw, font, plain):
    if not isinstance(raw, list):
        raise ValueError("notes must be an array")
    grouped = defaultdict(list)
    for index, spec in enumerate(raw, 1):
        try:
            if not isinstance(spec, dict):
                raise ValueError("note must be an object")
            n = spec["page"]
            if type(n) is not int or not 1 <= n <= len(doc):
                raise ValueError("page must be a valid one-based translated page")
            page = doc[n-1]
            if page.rotation:
                raise ValueError("annotate the upright PDF produced by the translator")
            ink = spec["ink"] if "ink" in spec else LEGACY_INK.get(spec.get("kind"))
            ink = LEGACY_COLORS.get(ink, ink)
            if ink not in INK:
                raise ValueError("choose ink blue, red or yellow, or provide a valid legacy kind")
            rect, mark = read_mark(page, spec, ink)
            also = spec.get("also", [])
            if not isinstance(also, list):
                raise ValueError("also must be an array of secondary marks")
            marks = [read_mark(page, extra, ink) for extra in also]
            label = inline_label(page, spec.get("inline"), font)
            sketch = parse_sketch(spec.get("sketch"), font, MARGIN - 2 * PAD)
            lines = spec["lines"]
            if not isinstance(lines, list) or not lines or not all(isinstance(s, str) and s.strip() for s in lines):
                raise ValueError("provide one or more nonempty handwritten lines")
            prefix = TEMPLATE_LABEL.match(lines[0])
            if prefix:
                raise ValueError(f"remove the template heading {prefix.group()!r}; begin with the observation or question")
            source = compact_source(spec.get("source", ""), n)
            source_lines = wrap_line(source, plain, 8.5, MARGIN-2*PAD)
            body = [line for paragraph in lines for segment in paragraph.splitlines()
                    for line in wrap_line(segment.strip(), font, BODY_SIZE, MARGIN-2*PAD, body=True)]
            if not body:
                raise ValueError("provide a handwritten observation or question")
            grouped[n].append(Note(rect, ink, mark, body, source_lines, label, marks, sketch))
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(f"note {index}: {error}") from error
    return grouped


def arrange(notes, height):
    notes.sort(key=lambda note: (note.rect.y0, note.rect.x0))
    if sum(note.height for note in notes) > height - 2*PAD:
        raise ValueError("notes will not fit in the margin; shorten them or select fewer anchors")
    bottom = PAD
    for note in notes:
        note.top = max(bottom, min(note.rect.y0-9, height-PAD-note.height))
        bottom = note.top + note.height
    bottom = height-PAD
    for note in reversed(notes):
        note.top = min(note.top, bottom-note.height)
        bottom = note.top


def pen_stroke(page, paths, note, color, width):
    annot = page.add_ink_annot(paths)
    annot.set_colors(stroke=color)
    annot.set_border(width=width)
    annot.set_info(title="阅读手记", subject="".join(note.source),
                   content="\n".join(note.body))
    annot.update()


def draw_mark(page, note, r, mark, color):
    if mark == "highlight":
        annot = page.add_highlight_annot(r)
        annot.set_colors(stroke=YELLOW_MARKER)
        annot.set_opacity(HIGHLIGHT_OPACITY)
        annot.set_blendmode("Multiply")
        annot.set_info(title="阅读手记", subject="".join(note.source), content="\n".join(note.body))
        annot.update()
        return
    if mark == "bracket":
        x = r.x1 + 2
        points = [(x-2, r.y0), (x+1, r.y0-.3), (x+.7, r.y1+.3), (x-2.1, r.y1)]
    elif mark == "circle":
        cx, cy = (r.x0+r.x1)/2, (r.y0+r.y1)/2
        rx, ry = r.width/2+1.6, r.height/2+.6
        points = []
        for i in range(65):
            a = .30 + 2.03*math.pi*i/64
            points.append((cx+rx*math.cos(a)+.35*math.sin(2*a),
                           cy+ry*math.sin(a)+.24*math.cos(3*a)))
    else:
        points = [(r.x0+r.width*i/22, r.y1-.6+.4*math.sin(i*math.pi/11)) for i in range(23)]
    pen_stroke(page, [points], note, color, .85)


class PaperSpace:
    """Test against the unannotated page before putting handwriting on it."""

    def __init__(self, page, notebook_paper):
        self.notebook = notebook_paper
        self.pix = page.get_pixmap(colorspace=pdf.csRGB if notebook_paper else pdf.csGRAY)
        self.pixels = self.pix.samples
        self.protected = [pdf.Rect(image["bbox"]) for image in page.get_image_info()]
        if notebook_paper:
            # The typesetter places source crops as top-level Form XObjects.
            # This also protects a chart or photo that contains khaki pixels.
            for _, name, parent, bbox in page.get_xobjects():
                if parent == 0 and name.startswith("fzFrm"):
                    rect = pdf.Rect(bbox) * page.transformation_matrix
                    if not rect.contains(page.rect):
                        self.protected.append(rect)
            # Also support simple white-backed panels in external PDFs.
            self.protected.extend(shape["rect"] for shape in page.get_drawings()
                                  if shape.get("fill") == (1, 1, 1) and
                                  any(item[0] == "re" for item in shape["items"]))

    def empty(self, rect):
        area = rect.irect
        pix = self.pix
        if (area.is_empty or area.x0 < 0 or area.y0 < 0 or area.x1 > pix.width or
                area.y1 > pix.height or any(rect.intersects(box) for box in self.protected)):
            return False
        for y in range(area.y0, area.y1):
            row = self.pixels[y*pix.stride + area.x0*pix.n:y*pix.stride + area.x1*pix.n]
            if self.notebook:
                for i, value in enumerate(PAPER_RGB):
                    channel = row[i::3]
                    if min(channel) < value-2 or max(channel) > value+2:
                        return False
            elif min(row) < 246:
                return False
        return True


def connect(page, note, old_width, paper, color, used):
    r = note.rect
    y = r.y1 if note.mark == "underline" else (r.y0+r.y1)/2
    x = r.x1 + 4
    # Draw a leader only through verified blank pixels. Never route across
    # another column, a chart or an intervening line of text.
    route = pdf.Rect(x-1, y-3, old_width, y+3)
    if (x+8 < old_width and paper.empty(route)
            and not any(route.intersects(other) for other in used)):
        tip_y = note.top+7
        points = [(x,y), (old_width,y), (old_width+4,(y+tip_y)/2), (old_width+8,tip_y)]
        pen_stroke(page, [points, [(x+3,y-1.6),(x,y),(x+3,y+1.6)]], note, color, .55)
        used.append(route)
    # Without a clear path, the matching ink, vertical order and mark popup retain
    # the association without placing a number or extra text in the article.


def inline_leader(page, note, color, paper, reserved):
    """Point back to the anchor only when the full ink path stays on bare paper."""
    a, b = note.rect, note.inline.rect
    ax, ay = (a.x0+a.x1)/2, (a.y0+a.y1)/2
    bx, by = (b.x0+b.x1)/2, (b.y0+b.y1)/2
    candidates = []
    if b.x0 > a.x1 + 9:
        candidates.append(((b.x0-2, by), (a.x1+4, ay)))
    elif b.x1 < a.x0 - 9:
        candidates.append(((b.x1+2, by), (a.x0-4, ay)))
    if b.y0 > a.y1 + 9:
        candidates.append(((bx, b.y0-2), (ax, a.y1+4)))
    elif b.y1 < a.y0 - 9:
        candidates.append(((bx, b.y1+2), (ax, a.y0-4)))
    for (x0,y0), (x1,y1) in sorted(candidates, key=lambda pair: math.dist(*pair)):
        length = math.hypot(x1-x0, y1-y0)
        if length > 120:
            continue
        steps = max(1, math.ceil(length/3))
        corridor = []
        for step in range(steps+1):
            x, y = x0+(x1-x0)*step/steps, y0+(y1-y0)*step/steps
            corridor.append(pdf.Rect(x-2.2,y-2.2,x+2.2,y+2.2))
        if not all(paper.empty(r) and not any(r.intersects(other) for other in reserved if other != b)
                   for r in corridor):
            continue
        dx, dy = (x0-x1)/length, (y0-y1)/length
        tip = [(x1+3*dx-1.3*dy,y1+3*dy+1.3*dx), (x1,y1),
               (x1+3*dx+1.3*dy,y1+3*dy-1.3*dx)]
        pen_stroke(page, [[(x0,y0),(x1,y1)], tip], note, color, .65)
        reserved.extend(corridor)
        return


def write_line(page, pos, text, face, size, color):
    writer = pdf.TextWriter(page.rect)
    x,y = pos
    runs = face.runs(text) if isinstance(face, ManuscriptPen) else [(face, text, 1)]
    for run_face, run, scale in runs:
        run_size = size * scale
        writer.append((x,y), run, font=run_face, fontsize=run_size)
        x += run_face.text_length(run, fontsize=run_size)
    writer.write_text(page, color=color)


def paint_paper(page, rect):
    page.draw_rect(rect, color=None, fill=rgb(*PAPER_RGB))
    lines = page.new_shape()
    for y in range(30, int(rect.height)-12, 23):
        lines.draw_line((rect.x0+6,rect.y0+y), (rect.x1-8,rect.y0+y))
    lines.finish(color=rgb(226,216,191), width=.3)
    lines.commit()


def put_margin(margin_doc, height, notes, pen, plain, notebook_paper):
    page = margin_doc.new_page(width=MARGIN, height=height)
    if notebook_paper:
        paint_paper(page, page.rect)
    else:
        page.draw_rect(page.rect, color=None, fill=(1,1,1))
    for note in notes:
        color = INK[note.ink]
        y = note.top + BODY_SIZE
        for line in note.body:
            write_line(page, (PAD,y), line, pen, BODY_SIZE, color)
            y += LEADING
        if note.sketch:
            draw_sketch(page, note.sketch, PAD, y-BODY_SIZE, pen, color)
            y += note.sketch.height
        for line in note.source:
            write_line(page, (PAD,y), line, plain, 8.5, (.31,.32,.31))
            y += 11.5


def put_inline(overlays, page, notes, pen):
    layer = overlays.new_page(width=page.rect.width, height=page.rect.height)
    for note in notes:
        label = note.inline
        if not label:
            continue
        x, y = label.rect.x0+2, label.rect.y0+12
        for line in label.lines:
            write_line(layer, (x,y), line, pen, INLINE_SIZE, INK[note.ink])
            y += INLINE_LEADING
        if label.sketch:
            top = label.rect.y0 + 16 + (len(label.lines)-1)*INLINE_LEADING
            draw_sketch(layer, label.sketch, x, top, pen, INK[note.ink])
    return layer.number


def add_margin(page):
    before = page.rect
    media, crop = page.mediabox, page.cropbox
    # Keep the original PDF coordinate origin and top edge, including cropped pages.
    # set_mediabox resets the CropBox, so explicitly restore it with the added width.
    page.set_mediabox(pdf.Rect(media.x0, media.y0, max(media.x1,crop.x1+MARGIN), media.y1))
    page.set_cropbox(pdf.Rect(crop.x0,crop.y0,crop.x1+MARGIN,crop.y1))
    return pdf.Rect(before.width, 0, before.width+MARGIN, before.height)


def read_reference_links(spec):
    if not isinstance(spec, dict):
        raise ValueError("reference_links must map a citation such as [72] to an HTTPS URL")
    for citation, url in spec.items():
        if not re.fullmatch(r"\[[0-9]+\]", citation) or not isinstance(url, str):
            raise ValueError("reference_links must map bracketed reference numbers to HTTPS URLs")
        parts = urlsplit(url)
        if parts.scheme != "https" or not parts.hostname or parts.username is not None or any(c.isspace() for c in url):
            raise ValueError(f"{citation}: provide an absolute HTTPS reference URL without credentials or spaces")
    return spec


def link_note_references(page, references, areas):
    for citation, url in references.items():
        for area in areas:
            for hit in page.search_for(citation, clip=area):
                page.insert_link({"kind": pdf.LINK_URI, "uri": url, "from": hit})


def annotate(clean, manifest_path, output, font_path=None, *, uniform_margin=False, notebook_paper=False):
    if clean.resolve() == output.resolve() or output.exists():
        raise ValueError("choose a new output PDF path")
    source = clean.read_bytes()
    checksum = hashlib.sha256(source).hexdigest()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if not isinstance(manifest, dict) or manifest.get("base_sha256") != checksum:
        raise ValueError("base_sha256 does not match the supplied translation")
    references = read_reference_links(manifest.get("reference_links", {}))
    default_font = "Yozai-Medium.ttf" if notebook_paper else "LXGWWenKai-Regular.ttf"
    handwriting, allow_subset = load_pen(font_path or FONT_DIR / default_font)
    upright, upright_subset = (load_pen(FONT_DIR / "LXGWWenKai-Regular.ttf") if notebook_paper
                              else (handwriting, allow_subset))
    latin, latin_subset = load_pen(FONT_DIR / "Caveat-Medium.ttf")
    plain = pdf.Font("cjk")
    pen = ManuscriptPen(handwriting, latin, plain, upright)
    with pdf.open(stream=source,filetype="pdf") as doc, pdf.open() as margins:
        grouped = prepare_notes(doc, manifest.get("notes"), pen, plain)
        layers = {}
        for n, notes in grouped.items():
            arrange(notes, doc[n-1].rect.height)
            margin = len(margins)
            put_margin(margins, doc[n-1].rect.height, notes, pen, plain, notebook_paper)
            inline = put_inline(margins, doc[n-1], notes, pen) if any(note.inline for note in notes) else None
            layers[n] = (margin, inline)
        if grouped and allow_subset and latin_subset and upright_subset:
            margins.subset_fonts()
        for n, notes in grouped.items():
            page = doc[n-1]
            original = page.rect
            paper = PaperSpace(page, notebook_paper)
            used = [note.rect for note in notes]
            used.extend(rect for note in notes for rect, _ in note.also)
            for note in notes:
                if note.inline:
                    rect = note.inline.rect
                    if not paper.empty(rect) or any(rect.intersects(other) for other in used):
                        raise ValueError(f"page {n}: inline bbox {list(rect)} overlaps other ink or a figure; "
                                         "move it to empty paper")
                    used.append(rect)
            dest = add_margin(page)
            m, inline = layers[n]
            page.show_pdf_page(dest, margins, m)
            if inline is not None:
                page.show_pdf_page(original, margins, inline)
            for note in notes:
                color = INK[note.ink]
                draw_mark(page, note, note.rect, note.mark, color)
                for rect, mark in note.also:
                    draw_mark(page, note, rect, mark, color)
                if note.inline:
                    inline_leader(page, note, color, paper, used)
                connect(page, note, dest.x0, paper, color, used)
            link_note_references(page, references, [dest, *(note.inline.rect for note in notes if note.inline)])
        if uniform_margin and (grouped or notebook_paper):
            for page in doc:
                if page.number + 1 not in grouped:
                    if page.rotation:
                        raise ValueError("uniform margins require upright translated pages")
                    dest = add_margin(page)
                    if notebook_paper:
                        paint_paper(page, dest)
        output.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=output.parent) as tmp:
            stage = Path(tmp)/"ready.pdf"
            doc.save(stage, garbage=3, deflate=True)
            # Both operations publish a fully written file, failing on collision.
            if os.name == "nt":
                stage.rename(output)
            else:
                os.link(stage,output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("clean", type=Path)
    parser.add_argument("notes", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--font", type=Path, help="embeddable handwriting TTF/OTF")
    parser.add_argument("--notebook-paper", action="store_true",
                        help="match a khaki notebook base, using Yozai for handwritten observations")
    parser.add_argument("--uniform-margin", action="store_true",
                        help="also extend unmarked pages for a consistent fit-to-width zoom")
    args = parser.parse_args()
    try:
        annotate(args.clean,args.notes,args.output,args.font,uniform_margin=args.uniform_margin,
                 notebook_paper=args.notebook_paper)
    except (ValueError, OSError, RuntimeError) as error:
        parser.exit(1, f"{error}\n")
    print(args.output)


if __name__ == "__main__":
    main()
