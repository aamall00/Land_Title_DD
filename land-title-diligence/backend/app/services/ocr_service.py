"""OCR Service — extracts text from PDF / image files.

Supports three providers:
  - 'tesseract'     (local, free)   — printed text; Kannada via tessdata
  - 'textract'      (AWS, paid)     — better accuracy for handwritten / mixed-language docs
  - 'google_vision' (GCP, paid)     — best accuracy for handwritten Kannada
"""

import io
import logging
import os
from pathlib import Path
from typing import Optional

import pytesseract

from app.config import get_settings

logger = logging.getLogger(__name__)

_s = get_settings()
if _s.tesseract_cmd:
    pytesseract.pytesseract.tesseract_cmd = _s.tesseract_cmd

# ── Helpers ────────────────────────────────────────────────────────────────

def _pdf_to_images(pdf_bytes: bytes) -> list:
    """Convert each PDF page to a PIL Image at 300 DPI."""
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        images = []
        for page in doc:
            pix = page.get_pixmap(dpi=300)
            img_bytes = pix.tobytes("png")
            from PIL import Image
            images.append(Image.open(io.BytesIO(img_bytes)))
        return images
    except Exception as e:
        logger.error(f"PDF→image conversion failed: {e}")
        raise


def _preprocess_for_handwriting(img) -> object:
    """Denoise, threshold, and deskew an image for handwritten Kannada OCR.

    Returns a PIL Image ready for pytesseract.
    """
    import cv2
    import numpy as np
    from PIL import Image

    arr = np.array(img.convert("RGB"))
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)

    # Denoise — reduces pen-stroke noise without blurring strokes
    denoised = cv2.fastNlMeansDenoising(gray, h=10)

    # Adaptive threshold — handles uneven lighting (common in scanned docs)
    thresh = cv2.adaptiveThreshold(
        denoised, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, 31, 10,
    )

    # Deskew — corrects slight rotation from scanning
    coords = np.column_stack(np.where(thresh < 128))
    if len(coords) > 10:
        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle += 90
        (h, w) = thresh.shape
        M = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
        thresh = cv2.warpAffine(
            thresh, M, (w, h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE,
        )

    return Image.fromarray(thresh)


# ── Tesseract Provider ──────────────────────────────────────────────────────

def _ocr_tesseract(pdf_bytes: bytes, mime_type: str) -> tuple[str, int]:
    """Run Tesseract OCR (Kannada + English) with handwriting preprocessing.
    Returns (full_text, page_count).
    """
    import pytesseract
    from PIL import Image

    lang = "kan+eng"  # Kannada + English; requires 'kan' tessdata installed

    # PSM 6 = assume uniform block of text; works well for dense docs
    config = "--psm 6"

    def _ocr_image(img) -> str:
        preprocessed = _preprocess_for_handwriting(img)
        return pytesseract.image_to_string(preprocessed, lang=lang, config=config)

    if mime_type in ("image/png", "image/jpeg", "image/jpg", "image/tiff", "image/webp"):
        img = Image.open(io.BytesIO(pdf_bytes))
        return _ocr_image(img), 1

    images = _pdf_to_images(pdf_bytes)
    pages_text = [_ocr_image(img) for img in images]
    return "\n\n--- PAGE BREAK ---\n\n".join(pages_text), len(images)


# ── Textract Provider ───────────────────────────────────────────────────────

def _ocr_textract(pdf_bytes: bytes, mime_type: str) -> tuple[str, int]:
    """AWS Textract OCR — good Kannada + English accuracy.
    Returns (full_text, page_count).
    """
    import boto3
    s = get_settings()

    client = boto3.client(
        "textract",
        aws_access_key_id=s.aws_access_key_id,
        aws_secret_access_key=s.aws_secret_access_key,
        region_name=s.aws_region,
    )

    if mime_type in ("image/png", "image/jpeg", "image/jpg"):
        response = client.detect_document_text(Document={"Bytes": pdf_bytes})
        blocks = response.get("Blocks", [])
        lines = [b["Text"] for b in blocks if b["BlockType"] == "LINE"]
        return "\n".join(lines), 1

    # Multi-page PDF — convert page-by-page via PyMuPDF
    images = _pdf_to_images(pdf_bytes)
    all_text = []
    for img in images:
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        response = client.detect_document_text(Document={"Bytes": buf.getvalue()})
        blocks = response.get("Blocks", [])
        lines = [b["Text"] for b in blocks if b["BlockType"] == "LINE"]
        all_text.append("\n".join(lines))
    return "\n\n--- PAGE BREAK ---\n\n".join(all_text), len(images)


# ── Google Cloud Vision Provider ────────────────────────────────────────────

def _ocr_google_vision(pdf_bytes: bytes, mime_type: str) -> tuple[str, int]:
    """Google Cloud Vision OCR — best accuracy for handwritten Kannada.

    Requires:
      - google-cloud-vision installed
      - GOOGLE_APPLICATION_CREDENTIALS env var set, or
        google_application_credentials path in .env pointing to a GCP
        service account JSON with 'Cloud Vision API' enabled.

    Returns (full_text, page_count).
    """
    from google.cloud import vision as gvision

    s = get_settings()
    if s.google_application_credentials:
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = s.google_application_credentials

    client = gvision.ImageAnnotatorClient()
    ctx = gvision.ImageContext(language_hints=["kn", "en"])

    def _vision_page(image_bytes: bytes) -> str:
        image = gvision.Image(content=image_bytes)
        response = client.document_text_detection(image=image, image_context=ctx)
        if response.error.message:
            raise RuntimeError(f"Google Vision error: {response.error.message}")
        return response.full_text_annotation.text or ""

    if mime_type in ("image/png", "image/jpeg", "image/jpg", "image/tiff", "image/webp"):
        return _vision_page(pdf_bytes), 1

    images = _pdf_to_images(pdf_bytes)
    all_text = []
    for img in images:
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        all_text.append(_vision_page(buf.getvalue()))
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
        elif provider == "google_vision":
            return _ocr_google_vision(file_bytes, mime_type)
        else:
            return _ocr_tesseract(file_bytes, mime_type)
    except Exception as e:
        logger.error(f"OCR failed ({provider}): {e}")
        # Return empty — document still stored, just not searchable
        return "", 0
