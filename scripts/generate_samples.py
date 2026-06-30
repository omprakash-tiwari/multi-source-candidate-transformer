"""Generate binary resume samples (.docx and .pdf) from the plain-text resume.

This keeps the binary fixtures reproducible and out of version-control churn.
The default sample run uses the .txt resume; these formats demonstrate that the
resume adapter also handles real PDF/DOCX. Run:

    python scripts/generate_samples.py

Outputs land in data/samples_formats/ (NOT data/samples/, to avoid the same
resume being ingested three times in the default run).
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC_TXT = ROOT / "data" / "samples" / "resume_jane_doe.txt"
OUT_DIR = ROOT / "data" / "samples_formats"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    text = SRC_TXT.read_text(encoding="utf-8")

    # --- DOCX ---
    try:
        from docx import Document

        doc = Document()
        for line in text.splitlines():
            doc.add_paragraph(line)
        docx_path = OUT_DIR / "resume_jane_doe.docx"
        doc.save(str(docx_path))
        print(f"wrote {docx_path}")
    except Exception as exc:  # pragma: no cover - convenience script
        print(f"skipped DOCX ({exc})")

    # --- PDF ---
    try:
        from fpdf import FPDF

        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", size=11)
        for line in text.splitlines():
            # latin-1 safe fallback for the default core font
            safe = line.encode("latin-1", "replace").decode("latin-1")
            pdf.multi_cell(0, 6, safe if safe else " ", new_x="LMARGIN", new_y="NEXT")
        pdf_path = OUT_DIR / "resume_jane_doe.pdf"
        pdf.output(str(pdf_path))
        print(f"wrote {pdf_path}")
    except Exception as exc:  # pragma: no cover - convenience script
        print(f"skipped PDF ({exc})")


if __name__ == "__main__":
    main()
