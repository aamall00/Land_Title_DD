"""OCR Service — extracts text from PDF / image files.

Supports two providers:
  - 'tesseract' (local, free)  — good for printed text; Kannada support via tessdata
  - 'textract'  (AWS, paid)    — better accuracy for handwritten / mixed-language docs
"""

import io
import base64
import logging
from pathlib import Path
from typing import Optional

from app.config import get_settings

logger = logging.getLogger(__name__)


# ── Helpers ────────────────────────────────────────────────────────────────

def _pdf_to_images(pdf_bytes: bytes) -> list:
    """Convert each PDF page to a PIL Image."""
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        images = []
        for page in doc:
            pix = page.get_pixmap(dpi=200)
            img_bytes = pix.tobytes("png")
            from PIL import Image
            images.append(Image.open(io.BytesIO(img_bytes)))
        return images
    except Exception as e:
        logger.error(f"PDF→image conversion failed: {e}")
        raise


# ── Tesseract Provider ──────────────────────────────────────────────────────

def _ocr_tesseract(pdf_bytes: bytes, mime_type: str) -> tuple[str, int]:
    """Run Tesseract OCR (Kannada + English) on a document.
    Returns (full_text, page_count).
    """
    import pytesseract
    from PIL import Image

    lang = "kan+eng"   # Kannada + English; install 'kan' tessdata

    if mime_type in ("image/png", "image/jpeg", "image/jpg", "image/tiff"):
        img = Image.open(io.BytesIO(pdf_bytes))
        text = pytesseract.image_to_string(img, lang=lang)
        return text, 1

    # PDF — convert pages first
    images = _pdf_to_images(pdf_bytes)
    pages_text = []
    for img in images:
        pages_text.append(pytesseract.image_to_string(img, lang=lang))
    return "\n\n--- PAGE BREAK ---\n\n".join(pages_text), len(images)


# ── Textract Provider ───────────────────────────────────────────────────────

def _ocr_textract(pdf_bytes: bytes, mime_type: str) -> tuple[str, int]:
    """AWS Textract OCR — best Kannada + English accuracy.
    Returns (full_text, page_count).
    """
    import boto3
    from app.config import get_settings
    s = get_settings()

    client = boto3.client(
        "textract",
        aws_access_key_id=s.aws_access_key_id,
        aws_secret_access_key=s.aws_secret_access_key,
        region_name=s.aws_region,
    )

    # Textract synchronous API handles single-page docs and images
    # For multi-page PDFs we use start_document_text_detection (async)
    if mime_type in ("image/png", "image/jpeg", "image/jpg"):
        response = client.detect_document_text(
            Document={"Bytes": pdf_bytes}
        )
        blocks = response.get("Blocks", [])
        lines = [b["Text"] for b in blocks if b["BlockType"] == "LINE"]
        return "\n".join(lines), 1

    # Multi-page PDF — use S3 upload + async job
    # For simplicity, fall back to page-by-page via PyMuPDF
    images = _pdf_to_images(pdf_bytes)
    all_text = []
    for img in images:
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        response = client.detect_document_text(
            Document={"Bytes": buf.getvalue()}
        )
        blocks = response.get("Blocks", [])
        lines = [b["Text"] for b in blocks if b["BlockType"] == "LINE"]
        all_text.append("\n".join(lines))
    return "\n\n--- PAGE BREAK ---\n\n".join(all_text), len(images)


# ── Public API ──────────────────────────────────────────────────────────────

def extract_text(file_bytes: bytes, mime_type: str) -> tuple[str, int]:
    """Extract text from a document file.

    Returns:
        (ocr_text: str, page_count: int)
    """
    s = get_settings()
    provider = s.ocr_provider.lower()

    logger.info(f"OCR provider={provider}, mime={mime_type}, size={len(file_bytes)//1024}KB")

    try:
        if provider == "textract":
            return _ocr_textract(file_bytes, mime_type)
        else:
            return _ocr_tesseract(file_bytes, mime_type)
    except Exception as e:
        logger.error(f"OCR failed: {e}")
        # Return empty — document still stored, just not searchable
        return "", 0
