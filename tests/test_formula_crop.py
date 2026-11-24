import io
import sys
import unittest
from pathlib import Path

import pymupdf as pdf

SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "translate-paper-zh" / "scripts"
sys.path.insert(0, str(SCRIPTS))
from typeset import typeset


def put_combining_slashes(page):
    """A visible Type 3 slash with zero advance, as in a TeX negated relation."""
    doc = page.parent

    def object_with_stream(data, stream=None):
        number = doc.get_new_xref()
        doc.update_object(number, data)
        if stream is not None:
            doc.update_stream(number, stream)
        return number

    glyph = object_with_stream("<<>>", b"0 0 d0 70 w 40 0 m 450 650 l S")
    cmap = object_with_stream("<<>>", b"""
        /CIDInit /ProcSet findresource begin 12 dict begin begincmap
        /CIDSystemInfo << /Registry (Test) /Ordering (Test) /Supplement 0 >> def
        /CMapName /Zero def /CMapType 2 def
        1 begincodespacerange <00> <FF> endcodespacerange
        1 beginbfchar <41> <0338> endbfchar endcmap
        CMapName currentdict /CMap defineresource pop end end""")
    font = object_with_stream(f"""<< /Type /Font /Subtype /Type3 /Name /Zero
        /FontBBox [0 -100 600 750] /FontMatrix [.001 0 0 .001 0 0]
        /CharProcs << /overlay {glyph} 0 R >>
        /Encoding << /Type /Encoding /Differences [65 /overlay] >>
        /FirstChar 65 /LastChar 65 /Widths [0] /Resources <<>> /ToUnicode {cmap} 0 R >>""")
    resources = int(doc.xref_get_key(page.xref, "Resources")[1].split()[0])
    doc.xref_set_key(resources, "Font/Zero", f"{font} 0 R")
    # First slash overlays the equals sign; the second is outside the formula.
    stream = page.read_contents() + b"\nBT /Zero 18 Tf 1 0 0 1 84 120 Tm (A) Tj 1 0 0 1 52 210 Tm (A) Tj ET"
    page.set_contents(object_with_stream("<<>>", stream))


class FormulaCropTests(unittest.TestCase):
    def test_overlaid_negation_remains_visible_and_searchable(self):
        crop = pdf.Rect(60, 94, 195, 162)
        with pdf.open() as source:
            page = source.new_page(width=300, height=250)
            page.insert_text((40, 35), "OutsideSecret")
            page.insert_text((84, 130), "= value", fontsize=18)
            put_combining_slashes(page)
            matrix = pdf.Matrix(4, 4)
            expected = page.get_pixmap(matrix=matrix, clip=crop).samples
            self.assertIn("\u0338", page.get_text(clip=crop))
            item = {"kind": "formula", "zh": "式一", "bbox": list(crop), "target": list(crop),
                    "caption_box": [60, 165, 195, 189]}
            stream = io.BytesIO()
            typeset(source, [{"page": 1, "columns": 1, "items": [item]}], stream)
            with pdf.open(stream=stream.getvalue(), filetype="pdf") as rendered:
                output = rendered[0]
                self.assertEqual(output.get_pixmap(matrix=matrix, clip=crop).samples, expected)
                self.assertFalse(output.get_images())
                glyphs = "".join(chr(c[0]) for span in output.get_texttrace() for c in span["chars"])
                self.assertEqual(glyphs.count("\u0338"), 1)
                self.assertNotIn("OutsideSecret", glyphs)
                self.assertIn("\u0338", output.get_text(clip=crop))


if __name__ == "__main__":
    unittest.main()
