"""Document Type Classifier — infers doc type from filename + text content.

Classification order:
1. Filename keywords (fast, free)
2. OCR text keywords
3. Default: OTHER
"""

import re
import logging

logger = logging.getLogger(__name__)

# Map of doc_type → keyword patterns (filename and/or text)
_PATTERNS: list[tuple[str, list[str]]] = [
    ("EC", [
        r"\bencumbrance\b", r"\bec\b", r"\bkaveri\b",
        r"ಭಾರ\s*ರಹಿತ", r"ಪ್ರಮಾಣ\s*ಪತ್ರ",
        r"sub.?registrar", r"encumbrance certificate",
    ]),
    ("RTC", [
        r"\brtc\b", r"\bpahani\b", r"\bbhoomi\b",
        r"ಆರ್.ಟಿ.ಸಿ", r"ಪಹಣಿ", r"ಹಕ್ಕು\s*ಪತ್ರ",
        r"record of rights", r"tenancy.*crop",
    ]),
    ("SALE_DEED", [
        r"sale\s*deed", r"sale\s*agreement", r"registered\s*deed",
        r"ಮಾರಾಟ\s*ಪತ್ರ", r"ಹಕ್ಕು\s*ಪರಭಾರೆ",
        r"vendor.*vendee", r"conveyed.*consideration",
    ]),
    ("KHATA", [
        r"\bkhata\b", r"ಖಾತಾ", r"bbmp.*assessment",
        r"property\s*tax\s*extract", r"khata\s*certificate",
        r"khata\s*extract",
    ]),
    ("MUTATION", [
        r"\bmutation\b", r"mutation\s*register", r"ಮ್ಯುಟೇಷನ್",
        r"transfer\s*of\s*ownership", r"change\s*of\s*ownership",
        r"mutation\s*number", r"M\.R\.\s*No",
    ]),
    ("SKETCH", [
        r"\bsketch\b", r"\bfmb\b", r"field\s*measurement",
        r"survey\s*sketch", r"cadastral", r"ಸರ್ವೆ\s*ನಕ್ಷೆ",
        r"boundary\s*map", r"plot\s*plan",
    ]),
    ("LEGAL_HEIR", [
        r"legal\s*heir", r"succession", r"ಉತ್ತರಾಧಿಕಾರ",
        r"heir\s*certificate", r"heirship",
    ]),
    ("COURT", [
        r"\bcourt\b", r"\bsuit\b", r"\binjunction\b",
        r"\bstay\s*order\b", r"\blitig", r"\bplaint\b",
        r"high\s*court", r"district\s*court", r"civil\s*court",
    ]),
    ("BBMP_APPROVAL", [
        r"\bbbmp\b.*approv", r"bbmp.*sanction", r"bruhat\s*bengaluru",
        r"occupancy\s*certificate", r"building\s*plan.*bbmp",
    ]),
    ("BDA_APPROVAL", [
        r"\bbda\b.*approv", r"bda.*sanction", r"bangalore\s*development",
        r"layout.*bda", r"bda.*allotment",
    ]),
]


def classify_document(filename: str, ocr_text: str = "") -> str:
    """Classify a document into a DocType enum value.

    Args:
        filename:  original file name
        ocr_text:  extracted OCR text (may be empty)

    Returns:
        DocType string, e.g. "EC", "RTC", "OTHER"
    """
    search_text = (filename + " " + (ocr_text[:3000] if ocr_text else "")).lower()

    for doc_type, patterns in _PATTERNS:
        for pattern in patterns:
            if re.search(pattern, search_text, re.IGNORECASE):
                logger.debug(f"Classified as {doc_type} via pattern '{pattern}'")
                return doc_type

    return "OTHER"


def extract_metadata_from_text(ocr_text: str) -> dict:
    """Extract key metadata fields from OCR text using regex heuristics.

    Returns a dict with any of: survey_no, owner_name, year, taluk, area, ec_period
    """
    if not ocr_text:
        return {}

    metadata: dict = {}
    text = ocr_text[:5000]  # Only scan first 5k chars for speed

    # Survey number — "Sy. No. 45", "Survey No: 45/2", "Sy.No.123"
    m = re.search(
        r"(?:sy\.?\s*no\.?|survey\s*no\.?|ಸರ್ವೆ\s*ನಂ\.?)\s*[:\-]?\s*([0-9]{1,4}[A-Za-z/0-9\-]*)",
        text, re.IGNORECASE,
    )
    if m:
        metadata["survey_no"] = m.group(1).strip()

    # Khata number
    m = re.search(
        r"(?:khata\s*no\.?|ಖಾತಾ\s*ಸಂಖ್ಯೆ)\s*[:\-]?\s*([0-9]{1,6}[A-Za-z/0-9\-]*)",
        text, re.IGNORECASE,
    )
    if m:
        metadata["khata_no"] = m.group(1).strip()

    # Year — "Registered on 12/05/2019", "Date: 01-03-2022"
    years = re.findall(r'\b(20[0-2][0-9]|19[7-9][0-9])\b', text)
    if years:
        metadata["year"] = years[0]
        metadata["all_years"] = sorted(set(years))

    # Area — "2400 sq ft", "0.12 acres", "1200 Sq.Mtr"
    m = re.search(
        r"([0-9,]+\.?[0-9]*)\s*(sq\.?\s*ft|sq\.?\s*mtr|acres?|guntas?|ಗುಂಟೆ|ಎಕರೆ)",
        text, re.IGNORECASE,
    )
    if m:
        metadata["area"] = f"{m.group(1)} {m.group(2)}"

    # Taluk
    taluk_pattern = r"(?:taluk|ತಾಲ್ಲೂಕು)\s*[:\-]?\s*([A-Za-zಾ-ೌ\s]{3,25}?)(?:\s*,|\s*\n|\s*district)"
    m = re.search(taluk_pattern, text, re.IGNORECASE)
    if m:
        metadata["taluk"] = m.group(1).strip()

    return metadata
