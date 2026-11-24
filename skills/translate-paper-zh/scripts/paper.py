"""Prepare source material and typeset Codex's Chinese translation with PyMuPDF."""

import argparse
import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path

import pymupdf as pdf

from layout import layout_hint, text_blocks, visibly_blank


def dump_new(path, obj):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(obj, stream, indent=2, ensure_ascii=False, allow_nan=False)


def page_numbers(selection, count):
    if not selection:
        return list(range(1, count + 1))
    result = set()
    for fragment in selection.split(","):
        left, sep, right = fragment.strip().partition("-")
        start, end = int(left), int(right) if sep else int(left)
        if not (1 <= start <= end <= count):
            raise ValueError(f"Invalid page range {fragment} (PDF has {count} pages)")
        result.update(range(start, end + 1))
    return sorted(result)


def inventory(page, blocks=None):
    result = []
    if blocks is None:
        blocks = text_blocks(page)
    for block in blocks:
        if block["type"] != 0:
            continue
        lines = block["lines"]
        text = "\n".join("".join(span["text"] for span in line["spans"]) for line in lines)
        if text.strip():
            result.append({
                "id": f"p{page.number + 1}b{len(result) + 1}",
                "bbox": [round(v, 2) for v in block["bbox"]],
                "text": text,
            })
    return result


def normalize_rotation(doc, numbers):
    for number in numbers:
        page = doc[number - 1]
        if page.rotation:
            page.remove_rotation()


def prepare(source, work, selection):
    if work.exists():
        raise ValueError("Choose a new work directory to protect existing translations")
    work.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=work.parent) as temp:
        stage = Path(temp) / "ready"
        stage.mkdir()
        write_inventory(source, stage, selection)
        stage.rename(work)


def write_inventory(source, work, selection):
    with pdf.open(source) as doc:
        numbers = page_numbers(selection, len(doc))
        normalize_rotation(doc, numbers)
        pages = []
        for number in numbers:
            page = doc[number - 1]
            page.get_pixmap(matrix=pdf.Matrix(1.5, 1.5), alpha=False).save(work / f"p{number:03}.png")
            blocks = text_blocks(page)
            pages.append({"page": number, "size": list(page.rect)[2:], "blocks": inventory(page, blocks),
                          "layout_hint": layout_hint(page, blocks)})
        with source.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        dump_new(work / "inventory.json", {
            "source": source.name, "sha256": digest, "scope": "preflight",
            "pages": pages,
        })
        dump_new(work / "translation.json", {
            "source": source.name, "terms": {}, "pages": [
                {"page": n, "visual_reviewed": False, "items": []} for n in numbers
            ],
        })


def validate(source, doc, work, manifest, preview):
    inv = json.loads((work / "inventory.json").read_text(encoding="utf-8-sig"))
    with source.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if inv["sha256"] != digest or manifest["source"] != inv["source"]:
        raise ValueError("Source fingerprint or translation source mismatch")
    source_pages = [p["page"] for p in inv["pages"]]
    if not source_pages or source_pages != sorted(set(source_pages)) or not (1 <= source_pages[0] <= source_pages[-1] <= len(doc)):
        raise ValueError("Invalid source page selection")
    normalize_rotation(doc, source_pages)
    if source_pages != [p["page"] for p in manifest["pages"]]:
        raise ValueError("Translation must contain exactly the prepared pages in order")
    declared, credited = set(), []
    for number in source_pages:
        declared.update(b["id"] for b in inventory(doc[number - 1]))
    for page in manifest["pages"]:
        number = page["page"]
        if not page["items"]:
            if page.get("blank_reviewed") is not True or not visibly_blank(doc[number-1]):
                raise ValueError(f"Page {number} has no translation or confirmed blank source")
        if not preview and page.get("visual_reviewed") is not True:
            raise ValueError(f"Page {number} requires items and a visual review")
        for item in page["items"]:
            kind, zh = item["kind"], item["zh"].strip()
            if kind not in {"heading", "text", "caption", "figure", "table", "formula", "keep"} or not zh:
                raise ValueError(f"Page {number}: invalid kind or empty translation")
            if kind == "keep":
                if item.get("reason") not in {"bibliography", "identifier", "page-furniture", "formula"}:
                    raise ValueError(f"Page {number}: state the protected category")
            elif not any("\u3400" <= ch <= "\u9fff" for ch in zh):
                raise ValueError(f"Page {number}: expected Chinese for {kind}")
            if "bbox" in item:
                box = pdf.Rect(item["bbox"])
                if box.is_empty or box.is_infinite or not doc[number-1].rect.contains(box):
                    raise ValueError(f"Page {number}: invalid box {box}")
                if item["kind"] in {"figure", "table", "formula"} and box.get_area() > .91 * doc[number-1].rect.get_area():
                    raise ValueError(f"Page {number}: crop the individual object")
            if kind in {"figure","table","formula"} and "bbox" not in item:
                raise ValueError(f"Page {number}: illustration needs a crop box")
            credited.extend(item.get("covers", []))
    if set(credited) - declared or len(credited) != len(set(credited)):
        raise ValueError("Duplicate or unknown source block ID")
    missing = sorted(declared - set(credited))
    if missing and not preview:
        raise ValueError(f"{len(missing)} source blocks unaccounted for, e.g. {missing[:12]}")
    return missing


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ["prepare", "render"]:
        arg = sub.add_parser(command)
        arg.add_argument("source", type=Path)
        arg.add_argument("work", type=Path, help="per-document work directory")
        if command == "prepare":
            arg.add_argument("--pages", help="one-based ranges, e.g. 1-3,5")
        else:
            arg.add_argument("output", type=Path)
            arg.add_argument("--preview", action="store_true", help="mark an incompletely reconciled trial PDF")
            arg.add_argument("--notebook-paper", action="store_true",
                             help="typeset translated text in WenKai on pale khaki paper, preserving source graphics")
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args.source, args.work, args.pages)
        return

    from typeset import typeset
    output = args.output.resolve()
    if args.source.resolve() == output or output.exists():
        raise ValueError("Choose a new PDF output path")
    manifest = json.loads((args.work / "translation.json").read_text(encoding="utf-8-sig"))
    with pdf.open(args.source) as doc:
        missing = validate(args.source, doc, args.work, manifest, args.preview)
        with tempfile.TemporaryDirectory(dir=output.parent) as tmp:
            candidate = Path(tmp) / "candidate.pdf"
            report = typeset(doc, manifest["pages"], candidate, args.preview, notebook_paper=args.notebook_paper)
            if args.notebook_paper:
                report["notebook_paper"] = "#FAF3E3"
            report.update(preview=args.preview, source_pages=len(doc),
                          scope="full" if len(manifest["pages"]) == len(doc) else "excerpt",
                          uncredited_blocks=missing)
            qa = output.with_suffix(".qa.json")
            if qa.exists():
                raise ValueError(f"QA output already exists: {qa}")
            with pdf.open(candidate) as check:
                if not len(check) or check.page_count != report["output_pages"]:
                    raise ValueError("PDF could not be reopened with expected page count")
            dump_new(qa, report)
            try:
                if os.name == "nt":
                    os.rename(candidate, output)  # Windows rejects an existing destination.
                else:
                    with output.open("xb") as final, candidate.open("rb") as ready:
                        try:
                            shutil.copyfileobj(ready, final)
                        except OSError:
                            final.close()
                            output.unlink()
                            raise
            except OSError:
                qa.unlink()
                raise
    print(f"{output} ({report['output_pages']} pages)")


if __name__ == "__main__":
    main()
