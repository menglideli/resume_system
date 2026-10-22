"""Render template gallery PDFs to PNGs for visual QA."""
from pathlib import Path

import pymupdf


root = Path("storage/template_gallery")
for name in ("default", "technical", "management", "compact"):
    output_dir = root / f"png_{name}"
    output_dir.mkdir(parents=True, exist_ok=True)
    with pymupdf.open(root / f"resume_{name}.pdf") as document:
        for page_number, page in enumerate(document):
            pixmap = page.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False)
            pixmap.save(output_dir / f"page-{page_number + 1}.png")
