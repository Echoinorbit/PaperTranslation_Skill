import io
from pathlib import Path
import sys
import unittest

import pymupdf as pdf

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "translate-paper-zh" / "scripts"))
from typeset import typeset


class NotebookPaperTests(unittest.TestCase):
    def test_searchable_handwriting_and_untinted_transparent_graphic(self):
        source_box = pdf.Rect(45, 95, 135, 145)
        target = pdf.Rect(40, 95, 160, 145)  # The source image is centered with sides exposed.
        pages = [{"page": 1, "items": [
            {"kind": "text", "zh": "Open-Canopy · 标高 ˒", "target": [35, 35, 200, 64], "size": 10},
            {"kind": "figure", "zh": "颜色刻度", "bbox": list(source_box), "target": list(target),
             "caption_box": [40, 146, 200, 168], "size": 9},
        ]}]
        with pdf.open() as src:
            original = src.new_page(width=240, height=280)
            original.draw_rect(pdf.Rect(50, 100, 120, 135), fill=(.1, .4, .65),
                               color=(.4, .7, .3), fill_opacity=.64)
            white, khaki = io.BytesIO(), io.BytesIO()
            typeset(src, pages, white)
            qa = typeset(src, pages, khaki, notebook_paper=True)

        with pdf.open(stream=white) as plain, pdf.open(stream=khaki) as notebook:
            page = notebook[0]
            self.assertIn("Open-Canopy · 标高 ˒", page.get_text())
            self.assertTrue(page.search_for("Open-Canopy"))
            self.assertTrue(any("WenKai" in f[3] for f in page.get_fonts()))
            pix = page.get_pixmap()
            self.assertEqual(pix.pixel(42, 103), (250, 243, 227))
            self.assertEqual(pix.pixel(56, 96), (255, 255, 255))
            region = pdf.Rect(55, 95, 145, 145)
            self.assertEqual(qa["pages"][0]["graphic_boxes"], [{"out": 1, "box": list(region)}])
            self.assertEqual(page.get_pixmap(clip=region).samples, plain[0].get_pixmap(clip=region).samples)


if __name__ == "__main__":
    unittest.main()
