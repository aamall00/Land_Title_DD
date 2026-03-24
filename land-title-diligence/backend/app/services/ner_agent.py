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
HOLDS_KHATA_FOR, SITUATED_IN, PAYS_TAX_TO, PART_OF, TRANSFERRED_TO,
EXECUTED_ON, REGISTERED_ON, VALID_FROM, VALID_TO, MUTATED_ON,
TRANSACTED_FOR, DOCUMENT_AMOUNT, ASSESSED_FOR, HAS_KHATA, HAS_MUTATION

Graph model — TWO distinct anchor levels:

LEVEL 1 — PROPERTY (physical, permanent attributes only):
  Connect directly to PROPERTY using: BOUNDED_BY, SITUATED_IN, PART_OF, CLASSIFIED_AS,
  CULTIVATED_BY, IRRIGATED_BY
  Entity types that belong at this level: SURVEY_NO, HISSA_NO, LAYOUT, SITE_NO, AREA,
  SITE_AREA, BOUNDARY, LAND_CLASS, CROP, WATER_SOURCE, VILLAGE, HOBLI, TALUK, WARD,
  ULB, SITE_ADDRESS

LEVEL 2 — DOCUMENT (transaction/event-specific entities):
  Transaction parties, dates, amounts, and registration details belong to the DOCUMENT
  (sale deed, EC, mutation, etc.), NOT directly to PROPERTY.
  The document itself connects to PROPERTY via PERTAINS_TO.
  Use these relationships to anchor Level-2 entities to DOCUMENT-level peers:

  Parties:
  - SELLS_TO        : VENDOR → VENDEE
  - INVOLVES_GRANTOR: TRANSACTION → GRANTOR
  - INVOLVES_GRANTEE: TRANSACTION → GRANTEE
  - ACTS_ON_BEHALF_OF: POA_HOLDER → VENDOR or VENDEE
  - ATTESTED_BY     : VENDOR → WITNESS

  Registration:
  - REGISTERED_AT   : VENDOR → SRO
  - EXECUTED_ON     : VENDOR → EXECUTION_DATE
  - REGISTERED_ON   : VENDOR → REGISTRATION_DATE

  Financial:
  - TRANSACTED_FOR  : VENDOR → CONSIDERATION
  - TRANSACTED_FOR  : VENDOR → STAMP_DUTY
  - TRANSACTED_FOR  : VENDOR → GUIDANCE_VALUE
  - DOCUMENT_AMOUNT : TRANSACTION → AMOUNT

  Title chain:
  - DERIVES_TITLE_FROM: VENDEE → PRIOR_DEED
  - HOLDS_MORTGAGE_ON : BANK → PROPERTY
  - ENCUMBERS         : CHARGE → PROPERTY

  Mutation / Khata:
  - TRANSFERRED_TO  : PREVIOUS_OWNER → OWNER
  - MUTATED_ON      : OWNER → MUTATION_DATE
  - HAS_MUTATION    : OWNER → MUTATION_NO
  - HAS_KHATA       : OWNER → KHATA_NO
  - ASSESSED_FOR    : OWNER → ANNUAL_TAX
  - ASSESSED_FOR    : OWNER → ASSESSMENT_YEAR

  EC:
  - VALID_FROM      : TRANSACTION → EC_PERIOD_FROM
  - VALID_TO        : TRANSACTION → EC_PERIOD_TO

CRITICAL RULE — Do NOT create direct VENDOR→PROPERTY, VENDEE→PROPERTY,
  GRANTOR→PROPERTY, or GRANTEE→PROPERTY relationships. These parties are
  transaction-specific: the same person can be a buyer in one deed and a
  seller in another. They must only connect to PROPERTY indirectly through
  the transaction chain (VENDOR→VENDEE→PROPERTY via deed context).

Rules:
- CRITICAL: Every extracted entity MUST appear in at least one relationship.
  If an entity has no natural peer, connect it to the most relevant Level-2
  party (VENDOR, VENDEE, OWNER, GRANTOR) using the best-fitting type above.
- For BOUNDARY relationships, set attributes.direction to N/S/E/W.
- For monetary entities (CONSIDERATION, STAMP_DUTY, AMOUNT, ANNUAL_TAX), set metadata.unit to "INR".
- For area entities (AREA, SITE_AREA), set metadata.unit to the unit found (acres/guntas/sqft/sqmt).
- Set metadata.confidence between 0.0-1.0 based on clarity of extraction.
- Only extract entities that are explicitly present in the text.
- Normalize dates to DD-MM-YYYY format in metadata.notes if possible.
- Always output all entity values in English. If the source text is in another language (e.g., Kannada), transliterate names and places into English Roman script."""

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
            max_tokens=8192,
            system=system,
            messages=[{"role": "user", "content": f"Document text:\n\n{text_sample}"}],
        )

        raw = response.content[0].text.strip()

        # Strip accidental markdown fences
        if raw.startswith("```"):
            # Remove opening fence (```json or ```)
            raw = raw[3:]
            if raw.startswith("json"):
                raw = raw[4:]
            # Remove closing fence if present
            if raw.endswith("```"):
                raw = raw[:-3]
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
        # Attempt partial recovery: extract whatever arrays were completed before truncation
        try:
            import re
            entities, relationships = [], []
            # Try to pull out the entities array even if relationships was cut off
            m = re.search(r'"entities"\s*:\s*(\[.*?\])', raw, re.DOTALL)
            if m:
                entities = json.loads(m.group(1))
            m = re.search(r'"relationships"\s*:\s*(\[.*?\])', raw, re.DOTALL)
            if m:
                relationships = json.loads(m.group(1))
            if entities or relationships:
                logger.warning(
                    f"NER partial recovery: {len(entities)} entities, "
                    f"{len(relationships)} relationships for doc_type={doc_type}"
                )
                return {"entities": entities, "relationships": relationships}
        except Exception:
            pass
        return {"entities": [], "relationships": []}
    except Exception as e:
        logger.error(f"NER extraction failed for doc_type={doc_type}: {e}", exc_info=True)
        return {"entities": [], "relationships": []}
