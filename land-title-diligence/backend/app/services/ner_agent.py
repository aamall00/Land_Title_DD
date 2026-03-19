"""NER Agent — Named Entity Recognition for Karnataka land documents using Claude."""

import json
import logging
from typing import Any

import anthropic

from app.config import get_settings

logger = logging.getLogger(__name__)

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=get_settings().anthropic_api_key)
    return _client


# ── System Prompt ──────────────────────────────────────────────────────────

NER_SYSTEM_PROMPT = """You are an expert in Karnataka land records and legal documents.
Extract all named entities and relationships from the given document text.
Document type: {doc_type}

Respond ONLY with a JSON object in this exact schema (no preamble, no markdown fences):
{{
  "entities": [
    {{
      "entity_type": "",
      "value": "",
      "metadata": {{ "unit": null, "confidence": 0.9, "notes": "" }}
    }}
  ],
  "relationships": [
    {{
      "source_type": "",
      "source_value": "",
      "relation_type": "",
      "target_type": "",
      "target_value": "",
      "attributes": {{}}
    }}
  ]
}}

Entity types to extract based on doc_type:

sale_deed → VENDOR, VENDEE, WITNESS, POA_HOLDER, SRO, PROPERTY,
            SURVEY_NO, LAYOUT, SITE_NO, BOUNDARY, PRIOR_DEED,
            CONSIDERATION, STAMP_DUTY, GUIDANCE_VALUE,
            EXECUTION_DATE, REGISTRATION_DATE, BANK

ec        → PROPERTY, SURVEY_NO, SRO, GRANTOR, GRANTEE,
            TRANSACTION, CHARGE, MORTGAGE, RELEASE,
            DOCUMENT_NO, AMOUNT, BANK, EC_PERIOD_FROM, EC_PERIOD_TO

rtc_pahani → SURVEY_NO, HISSA_NO, OWNER, OCCUPANT, AREA,
             LAND_CLASS, CROP, WATER_SOURCE, VILLAGE,
             HOBLI, TALUK, LAND_REVENUE, LIABILITY

khata     → OWNER, KHATA_NO, PROPERTY, WARD, SITE_AREA,
            ULB, ASSESSMENT_NO, ANNUAL_TAX, ASSESSMENT_YEAR,
            SITE_ADDRESS

mutation  → OWNER, PREVIOUS_OWNER, SURVEY_NO, KHATA_NO,
            MUTATION_NO, MUTATION_DATE, TALUK, VILLAGE, REASON

other     → PARTY, OWNER, SURVEY_NO, PROPERTY, DATE, AMOUNT,
            LOCATION, DOCUMENT_NO, AUTHORITY

Relationship types to extract:
SELLS_TO, ACQUIRES, REGISTERED_AT, ATTESTED_BY, DERIVES_TITLE_FROM,
BOUNDED_BY, ACTS_ON_BEHALF_OF, ENCUMBERS, HOLDS_MORTGAGE_ON,
INVOLVES_GRANTOR, INVOLVES_GRANTEE, ISSUED_BY, OWNED_BY,
CULTIVATED_BY, CLASSIFIED_AS, IRRIGATED_BY, LIABLE_FOR,
HOLDS_KHATA_FOR, SITUATED_IN, PAYS_TAX_TO, PART_OF, TRANSFERRED_TO

Rules:
- For BOUNDARY relationships, set attributes.direction to N/S/E/W.
- For monetary entities (CONSIDERATION, STAMP_DUTY, AMOUNT, ANNUAL_TAX), set metadata.unit to "INR".
- For area entities (AREA, SITE_AREA), set metadata.unit to the unit found (acres/guntas/sqft/sqmt).
- Set metadata.confidence between 0.0-1.0 based on clarity of extraction.
- Only extract entities that are explicitly present in the text.
- Normalize dates to DD-MM-YYYY format in metadata.notes if possible."""

# Map internal DocType values to prompt-friendly names
_DOC_TYPE_LABEL: dict[str, str] = {
    "SALE_DEED": "sale_deed",
    "EC": "ec",
    "RTC": "rtc_pahani",
    "KHATA": "khata",
    "MUTATION": "mutation",
    "SKETCH": "other",
    "LEGAL_HEIR": "other",
    "COURT": "other",
    "BBMP_APPROVAL": "other",
    "BDA_APPROVAL": "other",
    "OTHER": "other",
}


def _build_text_sample(ocr_text: str, max_chars: int = 10000) -> str:
    """Return a representative sample of the document text.

    For long documents, take the first 7000 and last 3000 characters to capture
    both the parties/header section and the concluding clauses/registration details.
    """
    if len(ocr_text) <= max_chars:
        return ocr_text
    head = ocr_text[:7000]
    tail = ocr_text[-3000:]
    return f"{head}\n\n[... document continues ...]\n\n{tail}"


def extract_entities_from_text(ocr_text: str, doc_type: str) -> dict[str, Any]:
    """Run NER extraction on the given OCR text using Claude.

    Returns:
        {"entities": [...], "relationships": [...]}
        Returns empty lists on failure so callers can proceed safely.
    """
    if not ocr_text or not ocr_text.strip():
        return {"entities": [], "relationships": []}

    client = _get_client()
    s = get_settings()

    doc_type_label = _DOC_TYPE_LABEL.get(doc_type.upper(), "other")
    system = NER_SYSTEM_PROMPT.format(doc_type=doc_type_label)
    text_sample = _build_text_sample(ocr_text)

    try:
        response = client.messages.create(
            model=s.claude_model,
            max_tokens=2048,
            system=system,
            messages=[{"role": "user", "content": f"Document text:\n\n{text_sample}"}],
        )

        raw = response.content[0].text.strip()

        # Strip accidental markdown fences
        if raw.startswith("```"):
            parts = raw.split("```")
            raw = parts[1] if len(parts) > 1 else raw
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        result = json.loads(raw)

        entities = result.get("entities") or []
        relationships = result.get("relationships") or []
        logger.info(
            f"NER extracted {len(entities)} entities, {len(relationships)} relationships "
            f"for doc_type={doc_type}"
        )
        return {"entities": entities, "relationships": relationships}

    except json.JSONDecodeError as e:
        logger.error(f"NER JSON parse error for doc_type={doc_type}: {e}")
        return {"entities": [], "relationships": []}
    except Exception as e:
        logger.error(f"NER extraction failed for doc_type={doc_type}: {e}", exc_info=True)
        return {"entities": [], "relationships": []}
