"""Reproduce three reviewed English-to-Chinese excerpts.

From the repository root, run: python benchmarks/run.py <new-output-directory>
Use the Python environment that runs the skill with PyMuPDF installed. The
redistributable original papers are in round-08-cross-domain/originals.
Use --legacy to reproduce the ten-page pilot from its four local originals
and reviewed translation manifests.

The output contains translated excerpts, their renderer QA JSON, coverage.csv,
and one side-by-side PNG per source page. Coverage counts inventory text blocks;
placement collisions count reported rectangles, not glyph-level or semantic
errors. Review the comparison images for those errors.
"""

import argparse
import csv
import itertools
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pymupdf as pdf


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "skills" / "translate-paper-zh" / "scripts" / "paper.py"
TRANSLATIONS = Path(__file__).resolve().parent / "translations"
PUBLIC_CASES = {
    "MetSim": ("2", "15d896f177c6afa074840c277d8400cdbf1b7f831bd997d2d342ec595af6a2b3"),
    "SnowDepth": ("5", "5551a1e0b2840dd9cb7b4fc5d81037cc2b8cabc32b4fde19d5b9f60eb41ed56d"),
    "Zeckendorf": ("1", "8f0022b4c706645c949851366edffef14cc1bbc5af30bc7c0e4e8766c82063ec"),
}
LEGACY_CASES = {
    "SkySense": ("1-3", "5ba66a028d4c3a135f7ad1d258addfe0e418fd4057aea968c3d32d307911877a"),
    "DETR": ("5-6", "cf016cbc2c80a6bc43ae0058d1824fba77630ddb7e4ac7224e6d0905a51356f8"),
    "GenCD": ("1-2", "4ccb29bd9902086f47ae17f844b40a97323ffffe7d09d47aedb020d8715c1b11"),
    "SPGAN": ("10-12", "eab3f1359e9df2de11491e8f21231f0e5b3bafe2e1077d4a857ba5bba6824caf"),
}


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def comparison(path, original, translated, tag, page):
    source_number = page["source_page"]
    panels = [(original, source_number, "Original")]
    panels.extend((translated, n, "Chinese") for n in range(page["out_first"], page["out_last"] + 1))
    width, gap, label_height = 800, 12, 40
    heights = [width * doc[n - 1].rect.height / doc[n - 1].rect.width for doc, n, _ in panels]
    with pdf.open() as sheet:
        canvas = sheet.new_page(width=(width + gap) * len(panels) + gap, height=max(heights) + label_height + gap)
        for index, ((doc, number, label), height) in enumerate(zip(panels, heights)):
            left = gap + index * (width + gap)
            canvas.insert_text((left, 26), f"{tag}  |  {label} {number} / {len(doc)}", fontsize=17)
            target = pdf.Rect(left, label_height, left + width, label_height + height)
            canvas.show_pdf_page(target, doc, number - 1)
            canvas.draw_rect(target, color=(0.76, 0.76, 0.76), width=0.6)
        canvas.get_pixmap(alpha=False).save(path)


def geometry(page, translated):
    collisions, outside = [], []
    placements = page["placements"]
    for mark in placements:
        box = pdf.Rect(mark["box"])
        if box.is_empty or not translated[mark["out"] - 1].rect.contains(box):
            outside.append(f"p{mark['out']} item{mark['item'] + 1}")
    for a, b in itertools.combinations(placements, 2):
        if a["out"] != b["out"]:
            continue
        area = (pdf.Rect(a["box"]) & pdf.Rect(b["box"])).get_area()
        if area > 1:
            collisions.append(f"p{a['out']} items{a['item'] + 1}/{b['item'] + 1} {area:.1f}pt2")
    return collisions, outside


def evaluate(tag, selection, fingerprint, stage, work, source_dir, *, notebook_paper):
    manifest_path = TRANSLATIONS / f"{tag}.json"
    manifest = read_json(manifest_path)
    source = source_dir / manifest["source"]
    output = stage / f"{tag}-zh.pdf"
    subprocess.run([sys.executable, CLI, "prepare", source, work, "--pages", selection], check=True)
    inventory = read_json(work / "inventory.json")
    if inventory["sha256"] != fingerprint:
        raise ValueError(f"{tag}: the source PDF differs from the reviewed edition")
    shutil.copyfile(manifest_path, work / "translation.json")
    render = [sys.executable, CLI, "render", source, work, output]
    if notebook_paper:
        render.append("--notebook-paper")
    subprocess.run(render, check=True)
    report = read_json(output.with_suffix(".qa.json"))
    credited = {bid for p in manifest["pages"] for item in p["items"] for bid in item.get("covers", [])}
    rows = []
    with pdf.open(source) as original, pdf.open(output) as translated:
        for page, reviewed, prepared in zip(report["pages"], manifest["pages"], inventory["pages"], strict=True):
            n = page["source_page"]
            if n != reviewed["page"] or n != prepared["page"]:
                raise ValueError(f"{tag}: unexpected source-page mapping")
            blocks = {b["id"] for b in prepared["blocks"]}
            missing = sorted(blocks - credited)
            placed = {m["item"] for m in page["placements"]}
            unplaced = sorted(set(range(len(reviewed["items"]))) - placed)
            collisions, outside = geometry(page, translated)
            name = f"{tag}-p{n:03}.png"
            comparison(stage / "comparisons" / name, original, translated, tag, page)
            rows.append({
                "paper": tag, "scope": report["scope"], "selected_source_pages": selection,
                "source_pdf_total_pages": len(original), "source_page": n,
                "source_blocks": len(blocks), "missing_block_count": len(missing),
                "missing_block_ids": " ".join(missing), "translation_items": len(reviewed["items"]),
                "unplaced_item_count": len(unplaced), "mode": page["mode"],
                "first_output_page": page["out_first"], "last_output_page": page["out_last"],
                "output_pdf_total_pages": len(translated), "collision_count": len(collisions),
                "collision_details": "; ".join(collisions), "out_of_page_count": len(outside),
                "out_of_page_details": "; ".join(outside), "comparison": f"comparisons/{name}",
            })
    return rows


def run(output, *, legacy=False):
    if output.exists():
        raise FileExistsError(f"Output directory must be new: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="paper-translation-") as temporary:
        root = Path(temporary)
        stage = root / "results"
        (stage / "comparisons").mkdir(parents=True)
        rows = []
        cases = LEGACY_CASES if legacy else PUBLIC_CASES
        sources = ROOT / "Paper_Translation_Stimulation"
        if not legacy:
            sources = sources / "round-08-cross-domain" / "originals"
        for tag, (selection, fingerprint) in cases.items():
            rows.extend(evaluate(tag, selection, fingerprint, stage, root / tag, sources,
                                 notebook_paper=not legacy))
        with (stage / "coverage.csv").open("x", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        # Reserve a new directory after all renders have finished. Concurrent
        # runs using the same destination cannot overwrite each other's output.
        output.mkdir()
        (output / "comparisons").mkdir()
        for item in stage.rglob("*"):
            if item.is_file():
                with item.open("rb") as src, (output / item.relative_to(stage)).open("xb") as dest:
                    shutil.copyfileobj(src, dest)
    print(f"{len(rows)} source pages compared in {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("output", type=Path, help="new directory for translated PDFs, QA, CSV, and comparisons")
    parser.add_argument("--legacy", action="store_true", help="run the original four local cases")
    args = parser.parse_args()
    try:
        run(args.output.resolve(), legacy=args.legacy)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Pilot failed: {error}\n")
