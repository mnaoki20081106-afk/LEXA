"""
Phase A: OCR extraction for 大学入試英単語 SPARTA3 一覧.pdf.

This one book couldn't be handled by 01_extract_reference_books.py: its PDF
embeds a subsetted font with no ToUnicode CMap, so pdfplumber/pypdf return
only raw glyph IDs (cid:NN), not text (see that script's docstring). The page
content itself is a clean, digitally-rendered table (not a real scan), so
instead of a general scanned-PDF pipeline this renders each page to a
high-DPI image, crops to just the index+headword columns (never the Japanese
gloss column — same copyright reasoning as 01_extract_reference_books.py:
we only need position + headword, not the book's own translations), removes
the table grid lines (tesseract's layout analysis fails on bordered cells --
verified empirically: identical crop OCRs near-perfectly after line removal,
garbles almost every row before it), and OCRs with tesseract.

Verified against actual page 1 output (20 pages total, 50 entries/page):
tesseract reads all 50 lemmas on the pilot page essentially perfectly aside
from OCR noise tokens ("~~", "_", "=") tesseract inserts for faint
leftover column-rule fragments -- CLEAN_PREFIX_RE below strips those.

Column crop rectangles (in PDF points, page is A4 595x842pt) were measured
by hand against this specific book's layout and are NOT guaranteed to
generalize to a different book with a different column layout.

Usage:
    python3 01b_ocr_sparta3.py --pdf "/path/to/大学入試英単語 SPARTA3 一覧.pdf" \
        --out-dir data/interim
"""
import argparse
import json
import re
from pathlib import Path

import cv2
import fitz  # PyMuPDF
import pytesseract

LEFT_COL = fitz.Rect(15, 88, 125, 825)
RIGHT_COL = fitz.Rect(298, 88, 408, 825)
RENDER_DPI = 400

# Tesseract emits leading noise glyphs for faint grid-line remnants it
# doesn't fully erase (e.g. "~~ whistle-blowing", "= malnutrition").
LINE_RE = re.compile(r"^\s*[~=_.\s]*\s*(?P<idx>\d{1,3})[.\s~=_]*\s+(?P<word>[A-Za-z][A-Za-z\-' ]*)")


def remove_grid_lines(png_path: Path) -> "cv2.Mat":
    img = cv2.imread(str(png_path), cv2.IMREAD_GRAYSCALE)
    _, bw = cv2.threshold(img, 200, 255, cv2.THRESH_BINARY_INV)
    horiz = cv2.morphologyEx(bw, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1)))
    vert = cv2.morphologyEx(bw, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, 40)))
    lines = cv2.bitwise_or(horiz, vert)
    cleaned = cv2.bitwise_and(bw, cv2.bitwise_not(lines))
    return cv2.bitwise_not(cleaned)


def ocr_column(page: "fitz.Page", rect: fitz.Rect, tmp_dir: Path, tag: str) -> list[tuple[int, str]]:
    mat = fitz.Matrix(RENDER_DPI / 72, RENDER_DPI / 72)
    pix = page.get_pixmap(matrix=mat, clip=rect)
    png_path = tmp_dir / f"{tag}.png"
    pix.save(str(png_path))
    cleaned = remove_grid_lines(png_path)
    clean_path = tmp_dir / f"{tag}_clean.png"
    cv2.imwrite(str(clean_path), cleaned)

    text = pytesseract.image_to_string(str(clean_path), lang="eng", config="--psm 6")
    entries = []
    for line in text.splitlines():
        m = LINE_RE.match(line)
        if m:
            entries.append((int(m.group("idx")), m.group("word").strip()))
    return entries


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True, type=Path)
    ap.add_argument("--out-dir", default=Path("data/interim"), type=Path)
    ap.add_argument("--tmp-dir", default=Path("/tmp/sparta3_ocr"), type=Path)
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    args.tmp_dir.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(args.pdf)
    all_entries: list[tuple[int, str]] = []
    for page_num, page in enumerate(doc):
        left = ocr_column(page, LEFT_COL, args.tmp_dir, f"p{page_num}_left")
        right = ocr_column(page, RIGHT_COL, args.tmp_dir, f"p{page_num}_right")
        all_entries.extend(left)
        all_entries.extend(right)
        print(f"[page {page_num + 1}/{len(doc)}] left={len(left)} right={len(right)}")

    total = len(all_entries)
    out = args.out_dir / "sparta3.json"
    out.write_text(json.dumps(
        {"book_code": "sparta3", "total_entries": total,
         "entries": [{"index": i, "lemma_raw": w} for i, w in all_entries]},
        ensure_ascii=False, indent=2))
    print(f"[ok] sparta3: {total} entries -> {out}")

    idxs = sorted(i for i, _ in all_entries)
    gaps = [i for i in range(1, idxs[-1] + 1) if i not in set(idxs)] if idxs else []
    if gaps:
        print(f"[warn] {len(gaps)} index gaps (missed/misread rows), e.g. {gaps[:20]}")


if __name__ == "__main__":
    main()
