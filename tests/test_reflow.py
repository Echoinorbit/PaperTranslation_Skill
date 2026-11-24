import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pymupdf

SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "translate-paper-zh" / "scripts"
sys.path.insert(0, str(SCRIPTS))
from typeset import typeset, unit_width, wrap


class ContinuousTranslationTests(unittest.TestCase):
    def test_graphic_crop_only_embeds_text_inside_the_figure(self):
        crop = [60, 94, 195, 162]
        with pymupdf.open() as source:
            page = source.new_page(width=300, height=290)
            page.insert_text((45, 45), "OutsideFigure")
            page.insert_text((80, 130), "FigureLabel")
            page.insert_image(pymupdf.Rect(145, 104, 169, 120),
                              stream=b"P6\n2 2\n255\n" + b"\xff\x00\x00" * 4)
            page.draw_line((75, 150), (165, 150), color=(0, 0, 1), width=2)
            for mode, layout in (("L0", {"target": crop, "caption_box": [60, 165, 195, 186]}),
                                 ("L2", {})):
                with self.subTest(mode=mode):
                    item = {"kind": "figure", "zh": "图中标注", "bbox": crop, **layout}
                    buffer = io.BytesIO()
                    qa = typeset(source, [{"page": 1, "columns": 1, "items": [item]}], buffer)
                    self.assertEqual(qa["pages"][0]["mode"], mode)
                    with pymupdf.open(stream=buffer.getvalue(), filetype="pdf") as result:
                        output = result[0]
                        self.assertIn("FigureLabel", output.get_text())
                        # Raw glyphs reveal hidden text that a crop-aware search can omit.
                        glyphs = "".join(chr(char[0]) for span in output.get_texttrace()
                                         for char in span["chars"])
                        self.assertNotIn("OutsideFigure", glyphs)
                        pixels = output.get_pixmap().samples
                        self.assertIn(b"\xff\x00\x00" * 3, pixels)
                        self.assertIn(b"\x00\x00\xff" * 3, pixels)

    def test_punctuation_preserves_words_and_numbers(self):
        for token in ("GFM", "10"):
            text = "模型 " + token
            lines = wrap(text + "，继续", unit_width(text) * 10 + .1, 10)
            self.assertTrue(any(token in line for line in lines))
            self.assertEqual("".join(lines).replace(" ", ""), (text+"，继续").replace(" ", ""))

    def test_full_document_rejects_missing_block_and_continues_inline(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            source, work, output = base/"source.pdf", base/"work", base/"zh.pdf"
            with pymupdf.open() as src:
                p = src.new_page(width=310, height=260)
                p.insert_text((35, 45), "A method for optical images.")
                p.insert_text((35, 110), "A longer explanation follows.")
                src.save(source)

            def run(*args):
                return subprocess.run([sys.executable, SCRIPTS/"paper.py", *args],
                                      capture_output=True, text=True)

            self.assertEqual(run("prepare", source, work).returncode, 0)
            inp = work/"translation.json"
            manifest = json.loads(inp.read_text("utf-8"))
            page = manifest["pages"][0]
            page.update(visual_reviewed=True, columns=1)
            page["items"] = [
                {"kind":"heading", "zh":"光学影像方法", "covers":["p1b1"],
                 "target":[30, 20, 240, 55], "size":11},
                {"kind":"text", "zh":"该方法在低照度条件下仍有效。"*115+"全文已结束。",
                 "covers":[], "target":[30, 80, 240, 105], "size":10},
            ]
            inp.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
            self.assertNotEqual(run("render", source, work, output).returncode, 0)
            self.assertFalse(output.exists())
            page["items"][1]["covers"] = ["p1b2"]
            inp.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
            rendered = run("render", source, work, output)
            self.assertEqual(rendered.returncode, 0, rendered.stderr)
            qa = json.loads(output.with_suffix(".qa.json").read_text("utf-8"))
            self.assertEqual((qa["scope"], qa["pages"][0]["mode"]), ("full","L1"))
            with pymupdf.open(output) as doc:
                self.assertGreater(len(doc), 1)
                body = "".join("".join(p.get_text().split()) for p in doc)
                self.assertIn("光学影像方法", body)
                self.assertIn("全文已结束", body)
                self.assertIn("接原第1页", body)


if __name__ == "__main__":
    unittest.main()
