import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

import pymupdf as pdf

SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "translate-paper-zh" / "scripts"
sys.path.insert(0, str(SCRIPTS))
from annotate import annotate, compact_source, HIGHLIGHT_OPACITY, INK, MARGIN, PAPER_RGB, YELLOW_MARKER, rgb


class ManuscriptTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.folder = Path(tmp.name)
        self.clean = self.folder / "clean.pdf"
        self.notes = self.folder / "notes.json"
        self.out = self.folder / "result.pdf"
        with pdf.open() as doc:
            p = doc.new_page(width=330, height=420)
            p.insert_text((24,66), "Unique anchor")
            p.insert_text((38,155), "middle other words other words")
            p.draw_rect(pdf.Rect(230,45,299,111), color=(.25,.6,.1), fill=(.9,.7,.63))
            p.insert_link({"kind":pdf.LINK_URI, "from":pdf.Rect(24,51,112,68),
                           "uri":"https://example.org/paper"})
            p.add_text_annot((170,75), "Original editorial note")
            p = doc.new_page(width=320,height=420)
            p.insert_text((22,80),"Second page")
            p.insert_text((22,120),"Translation: AI")
            p.insert_link({"kind":pdf.LINK_GOTO, "from":pdf.Rect(21,64,120,85), "page":0,
                           "to":pdf.Point(25,66)})
            doc.set_toc([[1,"Paper",1],[2,"Study",2]])
            doc.set_metadata({"title":"Source","author":"Original Author",
                              "subject":"CC BY 4.0 attribution"})
            doc.save(self.clean)
        self.digest = hashlib.sha256(self.clean.read_bytes()).hexdigest()
        self.first = {"page":1, "kind":"evidence", "anchor":{"text":"Unique anchor"},
                      "mark":"underline", "lines":["只在这里说明。"], "source":"原第 1 页"}

    def manifest(self, notes=None, digest=None):
        data = {"base_sha256":digest or self.digest,
                "notes":notes if notes is not None else [self.first]}
        self.notes.write_text(json.dumps(data,ensure_ascii=False),encoding="utf-8")

    def test_source_keeps_locators_with_their_cited_pages(self):
        cases = [
            (14, "原第 14 页 · 式 (A)；原第 17 页 · 表 A", "p. 14 · 式(A) / p. 17 · 表A"),
            (1, "原第 1 页 · 摘要；原第 2 页 · 表 1；原第 3 页 · §2",
             "p. 1 · 摘要 / p. 2 · 表1 / p. 3 · §2"),
            (13, "原第 13 页 · §A；原第 14 页 · 图 A（b，c）", "p. 13 · §A / p. 14 · 图A(b,c)"),
            (9, "原第 8 页 · 原第 9 页 · §5", "pp. 8–9 · §5"),
            (9, "p. 8 · §5；p. 9 · §5", "p. 8 · §5 / p. 9 · §5"),
            (20, "原第 20 页 · §D.2–D.3", "§D.2–D.3"),
            (3, "原第 3 页 · §3.3 · 表 2", "§3.3 · 表2"),
            (3, "图 2 · §3.1（原第 4 页）", "图2 / p. 4 · §3.1"),
            (3, "原第 3 页", ""),
            (3, "原第 2 页", "p. 2"),
        ]
        for page, source, expected in cases:
            with self.subTest(source=source):
                self.assertEqual(compact_source(source, page), expected)

        self.manifest([dict(self.first, source="原第 1 页 · 式 (A)；原第 2 页 · 表 A")])
        annotate(self.clean, self.notes, self.out)
        with pdf.open(self.out) as manuscript:
            margin = pdf.Rect(330, 0, manuscript[0].rect.width, manuscript[0].rect.height)
            self.assertIn("p. 1 · 式(A) / p. 2 · 表A", manuscript[0].get_text(clip=margin))

    def test_manuscript_preserves_base_and_writes_searchable_notes(self):
        second = {"page":1, "kind":"idea", "anchor":{"bbox":[232,49,247,62]},
                  "mark":"circle", "lines":["能否换一个样区验证？","预训练 ImageNet1k",
                                          "逐个像元手算 2/(1+3)=50%", "比较 nMAE 和 MAE",
                                          "复核 mIoU、F1、R²"], "source":"原第 1 页图示"}
        self.manifest([self.first,second])
        annotate(self.clean,self.notes,self.out)
        self.assertEqual(hashlib.sha256(self.clean.read_bytes()).hexdigest(),self.digest)
        with pdf.open(self.clean) as base, pdf.open(self.out) as result:
            self.assertEqual(len(base),len(result))
            self.assertEqual(result[0].rect.width,base[0].rect.width+MARGIN)
            self.assertEqual(result[1].rect,base[1].rect)
            self.assertEqual(result.get_toc(),base.get_toc())
            self.assertEqual(result.metadata["author"],"Original Author")
            self.assertEqual(result.metadata["subject"],"CC BY 4.0 attribution")
            self.assertEqual(result[0].get_links()[0]["uri"],base[0].get_links()[0]["uri"])
            self.assertEqual(result[1].get_links()[0]["to"],base[1].get_links()[0]["to"])
            self.assertEqual(result[0].get_links()[0]["from"],base[0].get_links()[0]["from"])
            for i in (0,1):
                pix = result[i].get_pixmap(annots=False,clip=base[i].rect)
                self.assertEqual(pix.samples,base[i].get_pixmap(annots=False).samples)
            first_page=result[0]
            for word in ("只在这里说明", "能否换一个样区验证"):
                found=first_page.search_for(word)
                self.assertTrue(found, word)
                self.assertTrue(all(r.x0>=base[0].rect.width for r in found))
            annotations=list(first_page.annots())
            self.assertTrue(any(a.info["content"]=="Original editorial note" for a in annotations))
            marks=[a for a in annotations if a.info["title"]=="阅读手记"]
            self.assertGreaterEqual(len(marks),2)
            self.assertTrue(all(a.type[1]=="Ink" for a in marks))
            self.assertTrue(any(a.info["content"].startswith("能否换一个样区验证？") for a in marks))
            spans = [s for b in first_page.get_text("dict", clip=pdf.Rect(330,0,510,420))["blocks"]
                     for line in b.get("lines",[]) for s in line["spans"]]
            for plain_token in ("ImageNet1k", "2/(1+3)=50%", "mIoU", "F1", "R²"):
                self.assertTrue(any(plain_token in s["text"] and "WenKai" in s["font"]
                                    for s in spans))
            self.assertTrue(any("nMAE" in s["text"] and "Caveat" in s["font"] for s in spans))
            self.assertIn("Second page",result[1].get_text())
            self.assertIn("Translation: AI",result[1].get_text())
        with self.assertRaisesRegex(ValueError,"new output"):
            annotate(self.clean,self.notes,self.out)

    def test_rejects_wrong_source_and_ambiguous_or_missing_anchors(self):
        for anchor in ({"text":"other words"},{"text":"not in document"},{"bbox":[-10,60,44,65]}):
            with self.subTest(anchor=anchor):
                self.manifest([dict(self.first,anchor=anchor)])
                with self.assertRaisesRegex(ValueError,"note 1"):
                    annotate(self.clean,self.notes,self.out)
                self.assertFalse(self.out.exists())
        self.manifest(digest="0"*64)
        with self.assertRaisesRegex(ValueError,"base_sha256"):
            annotate(self.clean,self.notes,self.out)
        self.assertFalse(self.out.exists())

    def test_no_category_heading_or_index_in_visible_text_or_popups(self):
        self.manifest([dict(self.first,kind="calculation",lines=["差值只有两米。"],
                            source="原第 1 页 · 式 (A)"),
                       dict(self.first,kind="idea",anchor={"bbox":[200,200,240,215]},
                            lines=["换个地区还成立吗？"], source="原第 1 页 · § 3.4"),
                       dict(self.first,anchor={"text":"middle"},lines=["看看表中数值。"],
                            source="原第 1 页 · 表 2")])
        annotate(self.clean,self.notes,self.out)
        with pdf.open(self.out) as result:
            page=result[0]
            margin=page.get_text(clip=pdf.Rect(330,0,510,420)).splitlines()
            self.assertEqual(set(margin),{"差值只有两米。","换个地区还成立吗？","看看表中数值。",
                                          "式(A)","§3.4","表2"})
            inks=[a for a in page.annots() if a.info["title"]=="阅读手记"]
            self.assertGreaterEqual(len(inks),3)
            self.assertEqual(len({tuple(a.colors["stroke"]) for a in inks}),3)
            for a in inks:
                self.assertIn(a.info["subject"],{"式(A)","§3.4","表2"})
                self.assertNotIn("AI",a.info["content"])
                self.assertNotEqual(a.type[1],"FreeText")

    def test_rejects_template_headings_but_preserves_ordinary_technical_language(self):
        for prefix in ("AI手算","AI 证据：","【AI设想】","AI 追问:","研究设想：","[追问]"):
            with self.subTest(prefix=prefix):
                self.manifest([self.first,dict(self.first,lines=[prefix+"是否可复现？"])])
                with self.assertRaisesRegex(ValueError,"note 2: remove the template heading"):
                    annotate(self.clean,self.notes,self.out)
                self.assertFalse(self.out.exists())
        self.manifest([dict(self.first,lines=["AI 模型对样本量敏感吗？"]),
                       dict(self.first,anchor={"text":"middle"},lines=["证据来自第二组样方。"])])
        annotate(self.clean,self.notes,self.out)
        with pdf.open(self.out) as doc:
            margin=doc[0].get_text(clip=pdf.Rect(330,0,510,420))
            self.assertIn("AI 模型对样本量敏感吗？",margin)
            self.assertIn("证据来自第二组样方。",margin)

    def test_margin_overflow_does_not_leave_partial_result(self):
        self.manifest([dict(self.first,lines=["很长的读书笔记"]*30)])
        with self.assertRaisesRegex(ValueError,"not fit"):
            annotate(self.clean,self.notes,self.out)
        self.assertFalse(self.out.exists())

    def test_ink_is_independent_of_kind_with_legacy_color_compatibility(self):
        input_note=dict(self.first)
        del input_note["kind"]
        self.manifest([dict(input_note,ink="purple",kind="idea")])
        with self.assertRaisesRegex(ValueError,"note 1: choose ink"):
            annotate(self.clean,self.notes,self.out)
        self.assertFalse(self.out.exists())
        self.manifest([dict(input_note,ink="green",lines=["这组数据来自哪里？"]),
                       dict(input_note,kind="calculation",ink="ochre",anchor={"text":"middle"},
                            lines=["是否与海拔有关？"]),
                       dict(input_note,kind="evidence",anchor={"bbox":[202,245,245,250]},
                            lines=["先看限定条件。"])])
        annotate(self.clean,self.notes,self.out)
        with pdf.open(self.out) as doc:
            page=doc[0]
            expected={"这组数据来自哪里？":"yellow","是否与海拔有关？":"red","先看限定条件。":"blue"}
            for a in page.annots():
                if a.info["title"]=="阅读手记":
                    ink=expected[a.info["content"]]
                    for actual, expected_value in zip(a.colors["stroke"], INK[ink], strict=True):
                        self.assertAlmostEqual(actual, expected_value, places=5)

    def test_highlight_is_native_and_punctuation_stays_on_the_line(self):
        sentence = "未必同季。先挑同一种林型，"
        self.manifest([dict(self.first, ink="yellow", mark="highlight", lines=[sentence])])
        annotate(self.clean, self.notes, self.out)
        with pdf.open(self.out) as doc:
            page = doc[0]
            mark = next(a for a in page.annots() if a.type[1] == "Highlight")
            self.assertEqual(mark.blendmode, "Multiply")
            self.assertAlmostEqual(mark.opacity, HIGHLIGHT_OPACITY, places=5)
            for actual, expected in zip(mark.colors["stroke"], YELLOW_MARKER, strict=True):
                self.assertAlmostEqual(actual, expected, places=5)
            self.assertIn(sentence, page.get_text(clip=pdf.Rect(330,0,510,420)).splitlines())

    def test_uniform_paper_extends_an_unmarked_page_without_changing_its_contents(self):
        self.manifest()
        annotate(self.clean, self.notes, self.out, uniform_margin=True)
        with pdf.open(self.clean) as base, pdf.open(self.out) as result:
            page = result[1]
            self.assertEqual(page.rect.width, base[1].rect.width + MARGIN)
            self.assertEqual(page.get_text(), base[1].get_text())
            self.assertFalse(list(page.annots()))
            self.assertEqual(page.get_pixmap(clip=base[1].rect).samples, base[1].get_pixmap().samples)

    def khaki_input(self):
        self.clean = self.folder / "khaki.pdf"
        with pdf.open() as doc:
            for _ in range(2):
                page = doc.new_page(width=330, height=420)
                page.draw_rect(page.rect, color=None, fill=rgb(*PAPER_RGB))
                page.insert_text((24, 80), "Unique anchor")
                page.insert_text((34, 180), "Another control")
                page.draw_rect(pdf.Rect(170, 40, 300, 120), color=None, fill=(1,1,1))
                # A scientific panel happens to use the same colour as the paper inside it.
                page.draw_rect(pdf.Rect(175, 45, 295, 115), color=None, fill=rgb(*PAPER_RGB))
                # A directly embedded source crop can have no white backing object at all.
                with pdf.open() as chart:
                    chart_page = chart.new_page(width=100, height=45)
                    chart_page.draw_rect(chart_page.rect, color=None, fill=rgb(*PAPER_RGB))
                    page.show_pdf_page(pdf.Rect(180,200,280,245), chart, 0)
            doc.save(self.clean)
        self.digest = hashlib.sha256(self.clean.read_bytes()).hexdigest()

    def test_notebook_places_searchable_callout_and_sketch_on_original_paper(self):
        self.khaki_input()
        note = dict(self.first, lines=["先看控制变量，再读数据。"],
                    inline={"bbox":[25,100,154,153], "lines":["固定骨干"],
                            "sketch":{"kind":"flow", "steps":["RGB","树高"]}},
                    also=[{"anchor":{"text":"Another control"},"mark":"bracket"}],
                    sketch={"kind":"table","rows":[["输入","MAE"],["RGB","3.73"]]})
        self.manifest([note])
        annotate(self.clean,self.notes,self.out,uniform_margin=True,notebook_paper=True)
        with pdf.open(self.out) as result:
            page = result[0]
            area = pdf.Rect(25,100,154,153)
            for text in ("固定骨干", "RGB", "树高"):
                self.assertTrue(page.search_for(text, clip=area),text)
            label = page.get_text("dict",clip=area)["blocks"][0]["lines"][0]["spans"][0]
            self.assertIn("Yozai",label["font"])
            self.assertTrue(page.search_for("3.73",clip=pdf.Rect(330,0,510,420)))
            self.assertGreaterEqual(len(list(page.annots())),3)  # primary, bracket, direct arrow
            for p in result:
                pix=p.get_pixmap(annots=False)
                self.assertEqual(pix.pixel(337,10),PAPER_RGB)
                self.assertEqual(pix.pixel(12,10),PAPER_RGB)
            self.assertEqual(result[1].get_text().strip(),"Unique anchor\nAnother control")

    def test_notebook_refuses_writing_over_words_panels_and_other_labels(self):
        self.khaki_input()
        for inline,other,problem in [
            ({"bbox":[20,64,115,90],"lines":["不能覆盖"]}, [], "overlaps"),
            ({"bbox":[180,50,270,75],"lines":["不能覆盖"]}, [], "overlaps"),
            ({"bbox":[183,210,270,238],"lines":["不能覆盖"]}, [], "overlaps"),
            ({"bbox":[20,115,30,132],"lines":["长句放不下"]}, [], "does not fit"),
            ({"bbox":[20,113,140,132],"lines":["两个框重叠"]},
             [dict(self.first,inline={"bbox":[24,115,132,149],"lines":["仍在同一处"]})], "overlaps"),
        ]:
            with self.subTest(inline=inline):
                self.manifest([dict(self.first, inline=inline),*other])
                with self.assertRaisesRegex(ValueError,problem):
                    annotate(self.clean,self.notes,self.out,notebook_paper=True)
                self.assertFalse(self.out.exists())

    def test_reference_at_line_break_stays_searchable(self):
        from annotate import wrap_line

        font = pdf.Font("helv")
        limit = font.text_length("UNet [", fontsize=10)
        self.assertEqual(wrap_line("UNet [58]", font, 10, limit, body=True), ["UNet", "[58]"])

    def test_references_link_only_the_written_notes(self):
        self.khaki_input()
        # Put a matching original citation outside both the note and its margin.
        with pdf.open(self.clean) as doc:
            doc[0].insert_text((170, 270), "See reference [72]")
            revised = self.folder / "with-citation.pdf"
            doc.save(revised)
        self.clean = revised
        self.digest = hashlib.sha256(revised.read_bytes()).hexdigest()
        note = dict(self.first, lines=["骨干来自 [72]。"],
                    inline={"bbox":[23,100,155,130], "lines":["见 [72]"]})
        self.manifest([note])
        spec = json.loads(self.notes.read_text(encoding="utf-8"))
        spec["reference_links"] = {"[72]":"file:///example.org/paper"}
        self.notes.write_text(json.dumps(spec), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            annotate(self.clean,self.notes,self.out,notebook_paper=True)
        url = "https://example.org/original"
        spec["reference_links"] = {"[72]":url}
        self.notes.write_text(json.dumps(spec), encoding="utf-8")
        annotate(self.clean,self.notes,self.out,notebook_paper=True)
        with pdf.open(self.out) as doc:
            links = [link for link in doc[0].get_links() if link.get("uri") == url]
            self.assertEqual(len(links), 2)
            self.assertTrue(any(link["from"].x0 >= 330 for link in links))
            self.assertTrue(any(pdf.Rect(23,100,155,130).contains(link["from"]) for link in links))


if __name__=="__main__":
    unittest.main()
