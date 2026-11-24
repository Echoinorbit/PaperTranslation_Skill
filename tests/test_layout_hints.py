import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pymupdf as pdf

SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "translate-paper-zh" / "scripts"
sys.path.insert(0, str(SCRIPTS))
from layout import layout_hint, text_layer_state
from paper import prepare, validate
from typeset import typeset


def add_lines(page, left, top, width, count):
    sentence = "The field survey records snow depth across each study site."
    size = width / pdf.get_text_length(sentence, fontsize=1)
    for line in range(count):
        page.insert_text((left, top + 21*line), sentence, fontsize=size)


class LayoutHintTests(unittest.TestCase):
    def test_parallel_body_columns_and_full_width_material(self):
        with pdf.open() as doc:
            page = doc.new_page(width=600, height=760)
            add_lines(page, 40, 190, 220, 12)
            add_lines(page, 326, 190, 230, 12)
            add_lines(page, 75, 95, 450, 1)
            hint = layout_hint(page)
            self.assertEqual((hint["layout"], hint["flow_columns"]), ("two_column", 2))
            add_lines(page, 45, 117, 492, 3)
            self.assertEqual(layout_hint(page)["layout"], "mixed")

            staggered = doc.new_page(width=600, height=760)
            add_lines(staggered, 40, 82, 220, 7)
            add_lines(staggered, 326, 390, 230, 7)
            self.assertEqual(layout_hint(staggered)["layout"], "undetermined")

    def test_wide_column_with_sidebar_and_landscape_three_column(self):
        with pdf.open() as doc:
            wide = doc.new_page(width=600, height=760)
            add_lines(wide, 165, 110, 390, 10)
            self.assertEqual(layout_hint(wide)["layout"], "single_column")
            add_lines(wide, 25, 115, 111, 9)
            hint = layout_hint(wide)
            self.assertEqual((hint["layout"], hint["flow_columns"]), ("mixed", 1))

            landscape = doc.new_page(width=780, height=510)
            for left in [37, 285, 520]:
                add_lines(landscape, left, 83, 205, 13)
            evidence = layout_hint(landscape)
            self.assertEqual((evidence["orientation"], evidence["layout"], evidence["flow_columns"]),
                             ("landscape", "possible_multi_column", 1))
            self.assertTrue(evidence["needs_layout_review"])
            with patch("typeset.columns_for", side_effect=AssertionError("overrode explicit column count")):
                item = {"kind": "text", "zh": "文献说明", "target": [285, 70, 487, 104]}
                report = typeset(doc, [{"page": 2, "columns": 2, "items": [item]}], io.BytesIO())
            self.assertEqual((report["pages"][0]["mode"], report["pages"][0]["columns"]), ("L0", 2))
            self.assertEqual(report["pages"][0]["placements"][0]["box"], item["target"])

    def test_suspicious_unicode_and_material_outside_crop(self):
        self.assertEqual(text_layer_state("A readable sentence " * 30 + "\ue005"), "present")
        self.assertEqual(text_layer_state("word \ue005 " * 15), "suspicious")
        with pdf.open() as doc:
            page = doc.new_page(width=600, height=760)
            def line(bounds, content):
                return {"bbox": bounds, "dir": (1, 0), "spans": [{"text": content}]}
            outside = line((-1700, 110, -200, 150), "Hidden outside crop " * 10)
            bad = line((20, 100, 500, 135), "xyz\ufffd" * 40)
            self.assertEqual(layout_hint(page, [{"lines": [outside]}])["layout"], "blank")
            hint = layout_hint(page, [{"lines": [outside, bad]}])
            self.assertEqual((hint["layout"], hint["text_layer"]), ("undetermined", "suspicious"))

    def test_preflight_is_not_an_ocr_or_blank_page_approval(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "pages.pdf"
            work = root / "work"
            with pdf.open() as doc:
                for shade in (0, 255):
                    page = doc.new_page()
                    page.insert_image(page.rect, stream=b"P6\n2 2\n255\n" + bytes([shade])*12, keep_proportion=False)
                doc.new_page()
                doc.new_page().insert_text((46, 130), "Addendum")
                doc.save(source)
            prepare(source, work, None)
            idx = json.loads((work / "inventory.json").read_bytes())
            self.assertEqual(idx["scope"], "preflight")
            hints = [page["layout_hint"] for page in idx["pages"]]
            self.assertEqual([(h["layout"], h["text_layer"]) for h in hints], [
                ("undetermined", "none"), ("undetermined", "none"), ("blank", "none"), ("undetermined", "sparse")])
            self.assertEqual([h["image_coverage"] for h in hints], [1, 1, 0, 0])
            self.assertTrue(all(h["needs_layout_review"] for h in hints))
            manifest = json.loads((work / "translation.json").read_bytes())
            self.assertTrue(all(p["visual_reviewed"] is False for p in manifest["pages"]))
            # Old inventories without diagnostics remain valid. A scanned page
            # requires actual items and review, even when it has zero block IDs.
            idx.pop("scope")
            for page in idx["pages"]:
                page.pop("layout_hint")
            (work / "inventory.json").write_text(json.dumps(idx), encoding="utf-8")
            for page in manifest["pages"]:
                page.update(visual_reviewed=True, blank_reviewed=True)
            with pdf.open(source) as doc:
                with self.assertRaisesRegex(ValueError, "Page 1 has no translation"):
                    validate(source, doc, work, manifest, False)
                manifest["pages"][0]["items"].append({"kind": "text", "zh": "扫描图中逐区核对的译文。"})
                manifest["pages"][3]["items"].append({"kind": "heading", "zh": "补遗", "covers": ["p4b1"]})
                self.assertEqual(validate(source, doc, work, manifest, False), [])


if __name__ == "__main__":
    unittest.main()
