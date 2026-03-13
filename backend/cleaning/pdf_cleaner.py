from pathlib import Path
import re
import json
from typing import Optional, Tuple

import pdfplumber
import pypdfium2 as pdfium

from backend.cleaning.ocr_module import OCRModule

# ---------------------------------
# TEXT CLEANING HELPERS
# ---------------------------------

def normalize_text(text: str) -> str:
    text = text.lower()
    text = text.replace("\u00a0", " ")
    return text


def fix_broken_lines(text: str) -> str:
    # Fix hyphenated line breaks
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    # Join lines broken mid-sentence
    text = re.sub(r"\n(?=[a-z])", " ", text)
    return text


def remove_noise(text: str) -> str:
    # Remove page numbers and headers like "Page 1"
    text = re.sub(r"page\s*\d+", "", text, flags=re.IGNORECASE)
    return text


def cleanup_whitespace(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def clean_text(text: str) -> str:
    text = normalize_text(text)
    text = fix_broken_lines(text)
    text = remove_noise(text)
    text = cleanup_whitespace(text)
    return text


# ---------------------------------
# PDF TEXT EXTRACTION
# ---------------------------------

def extract_text_from_pdf(pdf_path: Path, use_ocr_fallback: bool = True) -> Tuple[str, int, int]:
    """
    Extract text and page count from PDF.

    Uses native PDF text extraction first and falls back to OCR for pages
    that contain little or no extractable text.
    """
    all_text = []
    page_count = 0
    ocr_pages_used = 0
    ocr_reader: Optional[OCRModule] = OCRModule(languages=["en"], confidence_threshold=0.5) if use_ocr_fallback else None

    with pdfplumber.open(pdf_path) as pdf:
        page_count = len(pdf.pages)
        for page_index, page in enumerate(pdf.pages):
            text = page.extract_text()
            if text and len(text.strip()) >= 40:
                all_text.append(text)
                continue

            if not use_ocr_fallback:
                continue

            ocr_text = _extract_page_text_with_ocr(pdf_path, page_index, ocr_reader)
            if ocr_text:
                all_text.append(ocr_text)
                ocr_pages_used += 1

    combined_text = "\n".join(all_text)
    return combined_text, page_count, ocr_pages_used


def _extract_page_text_with_ocr(pdf_path: Path, page_index: int, ocr_reader: Optional[OCRModule]) -> str:
    """Render a PDF page to image and run OCR. Returns empty text on failure."""
    try:
        reader = ocr_reader or OCRModule(languages=["en"], confidence_threshold=0.5)
        pdf_doc = pdfium.PdfDocument(str(pdf_path))

        if page_index < 0 or page_index >= len(pdf_doc):
            return ""

        page = pdf_doc[page_index]
        bitmap = page.render(scale=2.0)
        image = bitmap.to_numpy()
        return reader.extract_text_from_array(image)
    except Exception:
        return ""


# ---------------------------------
# PIPELINE: PDF → CLEAN JSON
# ---------------------------------

def clean_pdf_directory(input_dir: str, output_json: str, use_ocr_fallback: bool = True):
    records = []
    input_path = Path(input_dir)

    for pdf_file in input_path.glob("*.pdf"):
        try:
            raw_text, page_count, ocr_pages_used = extract_text_from_pdf(
                pdf_file,
                use_ocr_fallback=use_ocr_fallback,
            )
            cleaned_text = clean_text(raw_text)

            # Quality gate
            if len(cleaned_text) < 150:
                continue

            record = {
                "source": "pdf",
                "title": pdf_file.stem,
                "content": cleaned_text,
                "metadata": {
                    "page_count": page_count,
                    "ocr_pages_used": ocr_pages_used,
                    "char_count": len(cleaned_text),
                    "file_path": str(pdf_file.resolve())
                }
            }

            records.append(record)

        except Exception as e:
            print(f"⚠️ Failed to process {pdf_file.name}: {e}")

    # Save JSON
    output_path = Path(output_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)

    print(f"✅ Cleaned {len(records)} PDF files")
    print(f"📄 Output saved to {output_path}")


# ---------------------------------
# RUN (Notebook / Script Friendly)
# ---------------------------------

# if __name__ == "__main__":
#     clean_pdf_directory(
#         input_dir="data/raw",
#         output_json="data/processed/clean_pdf.json"
#     )


if __name__ == "__main__":
    project_root = Path(__file__).resolve().parents[2]
    clean_pdf_directory(
        input_dir=project_root / "data" / "raw" / "pdfs",
        output_json=project_root / "data" / "processed" / "clean_pdf.json",
    )