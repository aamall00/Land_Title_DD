"""Graph Service — stores and retrieves the knowledge graph (entities + relationships)."""

import logging
from typing import Any

from app.database import get_supabase
from app.services.ner_agent import extract_entities_from_text

logger = logging.getLogger(__name__)


# ── Entity resolution helpers ──────────────────────────────────────────────

def _normalise(value: str) -> str:
    """Normalise an entity value for canonical matching (strip + uppercase)."""
    return value.strip().upper()


def _resolve_canonical(db, entity_type: str, value: str) -> str | None:
    """Find or create a canonical_entities record.

    Returns the canonical UUID, or None if an unrecoverable error occurs.
    """
    canonical_val = _normalise(value)

    # Try to find an existing canonical record
    result = db.table("canonical_entities") \
        .select("id, aliases") \
        .eq("entity_type", entity_type) \
        .eq("canonical_val", canonical_val) \
        .limit(1) \
        .execute()

    if result.data:
        rec = result.data[0]
        # Append the original surface form to aliases if it's new
        aliases: list = rec.get("aliases") or []
        if value not in aliases and value != canonical_val:
            aliases.append(value)
            try:
                db.table("canonical_entities") \
                    .update({"aliases": aliases}) \
                    .eq("id", rec["id"]) \
                    .execute()
            except Exception as e:
                logger.debug(f"Alias update skipped for {canonical_val}: {e}")
        return rec["id"]

    # Insert a new canonical record
    try:
        insert_res = db.table("canonical_entities").insert({
            "entity_type": entity_type,
            "canonical_val": canonical_val,
            "aliases": [value] if value != canonical_val else [],
        }).execute()
        if insert_res.data:
            return insert_res.data[0]["id"]
    except Exception:
        # Race condition — another concurrent request inserted the same record
        retry = db.table("canonical_entities") \
            .select("id") \
            .eq("entity_type", entity_type) \
            .eq("canonical_val", canonical_val) \
            .limit(1) \
            .execute()
        if retry.data:
            return retry.data[0]["id"]

    logger.warning(f"Could not resolve canonical for {entity_type}/{canonical_val}")
    return None


# ── Main store function ────────────────────────────────────────────────────

# ── Orphan-linker configuration ────────────────────────────────────────────
#
# Graph model has TWO anchor levels:
#
#   PROPERTY  ←[PERTAINS_TO]─  DOCUMENT  ─[...]→  transaction entities
#       │                                           (parties, dates, amounts)
#       └──[BOUNDED_BY / SITUATED_IN / ...]→  physical/location entities
#
# Transaction-specific entities anchor to the DOCUMENT node so that the same
# person appearing as buyer in one deed and seller in another is unambiguous.
# Physical/permanent attributes (survey no, area, boundaries) anchor directly
# to PROPERTY.

# Level-2: entities that belong to the DOCUMENT, not directly to PROPERTY
_DOCUMENT_ANCHORED_TYPES = frozenset({
    # Transaction parties
    "VENDOR", "VENDEE", "WITNESS", "POA_HOLDER",
    "GRANTOR", "GRANTEE",
    # Registration / office
    "SRO", "BANK",
    # Dates
    "EXECUTION_DATE", "REGISTRATION_DATE",
    "EC_PERIOD_FROM", "EC_PERIOD_TO",
    # Financial
    "CONSIDERATION", "STAMP_DUTY", "GUIDANCE_VALUE", "AMOUNT",
    # Document references
    "DOCUMENT_NO", "PRIOR_DEED", "TRANSACTION", "CHARGE", "MORTGAGE", "RELEASE",
    # Mutation / Khata
    "PREVIOUS_OWNER", "MUTATION_NO", "MUTATION_DATE",
    "KHATA_NO", "ANNUAL_TAX", "ASSESSMENT_YEAR", "ASSESSMENT_NO",
    "LAND_REVENUE", "LIABILITY", "REASON",
    # Owner is transaction-specific (khata/mutation doc context)
    "OWNER", "OCCUPANT",
})

# Level-1: entities that anchor directly to PROPERTY (physical/permanent)
_PROPERTY_ANCHORED_TYPES = frozenset({
    "SURVEY_NO", "HISSA_NO", "LAYOUT", "SITE_NO",
    "AREA", "SITE_AREA", "BOUNDARY",
    "LAND_CLASS", "CROP", "WATER_SOURCE",
    "VILLAGE", "HOBLI", "TALUK", "WARD", "ULB", "SITE_ADDRESS",
})

# Preferred relationship type when synthetically anchoring an orphan
_ORPHAN_REL: dict[str, str] = {
    # Parties → DOCUMENT
    "VENDOR":            "HAS_VENDOR",
    "VENDEE":            "HAS_VENDEE",
    "WITNESS":           "ATTESTED_BY",
    "POA_HOLDER":        "ACTS_ON_BEHALF_OF",
    "GRANTOR":           "INVOLVES_GRANTOR",
    "GRANTEE":           "INVOLVES_GRANTEE",
    "SRO":               "REGISTERED_AT",
    "BANK":              "INVOLVES_BANK",
    # Dates → DOCUMENT
    "EXECUTION_DATE":    "EXECUTED_ON",
    "REGISTRATION_DATE": "REGISTERED_ON",
    "EC_PERIOD_FROM":    "VALID_FROM",
    "EC_PERIOD_TO":      "VALID_TO",
    "MUTATION_DATE":     "MUTATED_ON",
    "ASSESSMENT_YEAR":   "ASSESSED_FOR",
    # Financial → DOCUMENT
    "CONSIDERATION":     "TRANSACTED_FOR",
    "STAMP_DUTY":        "TRANSACTED_FOR",
    "GUIDANCE_VALUE":    "TRANSACTED_FOR",
    "AMOUNT":            "DOCUMENT_AMOUNT",
    "ANNUAL_TAX":        "ASSESSED_FOR",
    # Mutation / Khata → DOCUMENT
    "PREVIOUS_OWNER":    "TRANSFERRED_TO",
    "MUTATION_NO":       "HAS_MUTATION",
    "KHATA_NO":          "HAS_KHATA",
    "OWNER":             "OWNED_BY",
    "OCCUPANT":          "CULTIVATED_BY",
    # Physical → PROPERTY
    "SURVEY_NO":         "PART_OF",
    "BOUNDARY":          "BOUNDED_BY",
    "VILLAGE":           "SITUATED_IN",
    "TALUK":             "SITUATED_IN",
    "LAND_CLASS":        "CLASSIFIED_AS",
}

# Within DOCUMENT-anchored orphans, prefer these party types as secondary anchors
_DOC_PARTY_PRIORITY = [
    "VENDOR", "VENDEE", "OWNER", "GRANTOR", "GRANTEE", "OCCUPANT",
]
# Within PROPERTY-anchored orphans, prefer these
_PROP_ANCHOR_PRIORITY = ["PROPERTY", "SURVEY_NO"]


def _find_doc_party(entity_id_map: dict[tuple[str, str], str]) -> tuple[str, str] | None:
    """Return key of the best document-level party anchor."""
    for anchor_type in _DOC_PARTY_PRIORITY:
        for key in entity_id_map:
            if key[0] == anchor_type:
                return key
    return None


def _find_property_anchor(entity_id_map: dict[tuple[str, str], str]) -> tuple[str, str] | None:
    """Return key of the best property-level anchor."""
    for anchor_type in _PROP_ANCHOR_PRIORITY:
        for key in entity_id_map:
            if key[0] == anchor_type:
                return key
    return None


def extract_and_store_entities(
    document_id: str,
    property_id: str,
    ocr_text: str,
    doc_type: str,
) -> tuple[int, int]:
    """Run NER on OCR text and persist entities + relationships to the database.

    Returns:
        (entity_count, relationship_count)
    """
    db = get_supabase()

    ner_result = extract_entities_from_text(ocr_text, doc_type)
    entities_raw: list[dict] = ner_result.get("entities") or []
    relationships_raw: list[dict] = ner_result.get("relationships") or []

    if not entities_raw:
        logger.info(f"No entities extracted for document {document_id}")
        return 0, 0

    # ── Strategy 3: synthetic DOCUMENT anchor node ─────────────────────────
    # Insert a virtual node representing the document. Transaction-specific
    # entities (parties, dates, amounts) will hang off this node.
    # The document itself is later linked to PROPERTY via PERTAINS_TO.
    doc_anchor_id: str | None = None
    try:
        doc_canonical_id = _resolve_canonical(db, "DOCUMENT", document_id)
        res = db.table("entities").insert({
            "document_id": document_id,
            "property_id": property_id,
            "entity_type": "DOCUMENT",
            "value": document_id,
            "canonical_id": doc_canonical_id,
            "metadata": {"doc_type": doc_type, "synthetic": True},
        }).execute()
        if res.data:
            doc_anchor_id = res.data[0]["id"]
    except Exception as e:
        logger.warning(f"Document anchor node creation failed: {e}")

    # ── Persist entities ───────────────────────────────────────────────────
    # Maps (entity_type, value) → db UUID for relationship resolution
    entity_id_map: dict[tuple[str, str], str] = {}

    for ent in entities_raw:
        entity_type = (ent.get("entity_type") or "").strip().upper()
        value = (ent.get("value") or "").strip()
        if not entity_type or not value:
            continue

        metadata: dict[str, Any] = ent.get("metadata") or {}

        canonical_id = None
        try:
            canonical_id = _resolve_canonical(db, entity_type, value)
        except Exception as e:
            logger.warning(f"Canonical resolution failed for {entity_type}/{value}: {e}")

        try:
            res = db.table("entities").insert({
                "document_id": document_id,
                "property_id": property_id,
                "entity_type": entity_type,
                "value": value,
                "canonical_id": canonical_id,
                "metadata": metadata,
            }).execute()
            if res.data:
                entity_id_map[(entity_type, value)] = res.data[0]["id"]
        except Exception as e:
            logger.warning(f"Entity insert failed for {entity_type}/{value}: {e}")

    # ── Persist relationships ──────────────────────────────────────────────
    rel_count = 0

    # Track which entity IDs already have at least one relationship
    connected_ids: set[str] = set()

    for rel in relationships_raw:
        src_type = (rel.get("source_type") or "").strip().upper()
        src_val = (rel.get("source_value") or "").strip()
        tgt_type = (rel.get("target_type") or "").strip().upper()
        tgt_val = (rel.get("target_value") or "").strip()
        relation_type = (rel.get("relation_type") or "").strip().upper()
        attributes: dict = rel.get("attributes") or {}

        if not all([src_type, src_val, tgt_type, tgt_val, relation_type]):
            continue

        source_id = entity_id_map.get((src_type, src_val))
        target_id = entity_id_map.get((tgt_type, tgt_val))

        if not source_id or not target_id:
            logger.debug(
                f"Skipping relationship {relation_type}: "
                f"missing entity IDs for ({src_type}/{src_val}) → ({tgt_type}/{tgt_val})"
            )
            continue

        try:
            db.table("relationships").insert({
                "document_id": document_id,
                "property_id": property_id,
                "source_entity": source_id,
                "target_entity": target_id,
                "relation_type": relation_type,
                "attributes": attributes,
            }).execute()
            rel_count += 1
            connected_ids.add(source_id)
            connected_ids.add(target_id)
        except Exception as e:
            logger.warning(f"Relationship insert failed ({relation_type}): {e}")

    # ── Link DOCUMENT anchor → PROPERTY ───────────────────────────────────
    # The document node connects to the PROPERTY entity (Level-1 anchor) so
    # that all transaction-specific entities hanging off DOCUMENT are
    # reachable from PROPERTY through the document hop.
    if doc_anchor_id:
        prop_key = _find_property_anchor(entity_id_map)
        if prop_key:
            prop_entity_id = entity_id_map[prop_key]
            try:
                db.table("relationships").insert({
                    "document_id": document_id,
                    "property_id": property_id,
                    "source_entity": doc_anchor_id,
                    "target_entity": prop_entity_id,
                    "relation_type": "PERTAINS_TO",
                    "attributes": {"synthetic": True},
                }).execute()
                rel_count += 1
                connected_ids.add(doc_anchor_id)
                connected_ids.add(prop_entity_id)
            except Exception as e:
                logger.warning(f"DOCUMENT→PROPERTY link failed: {e}")

    # ── Strategy 2: orphan linker ──────────────────────────────────────────
    # For every unconnected entity, route it to the correct anchor level:
    #   - Document-anchored types  → DOCUMENT node  (parties, dates, amounts)
    #   - Property-anchored types  → PROPERTY node  (physical attributes)
    #   - Anything else            → DOCUMENT node  (safe default)
    orphan_count = 0
    for (etype, evalue), eid in entity_id_map.items():
        if eid in connected_ids:
            continue  # already connected

        rel_type = _ORPHAN_REL.get(etype, "SOURCED_FROM")

        if etype in _PROPERTY_ANCHORED_TYPES:
            # Physical / permanent attribute → anchor to PROPERTY
            anchor_key = _find_property_anchor(entity_id_map)
            anchor_id = entity_id_map[anchor_key] if anchor_key else doc_anchor_id
        elif etype in _DOCUMENT_ANCHORED_TYPES:
            # Transaction-specific → prefer a same-document party, then DOCUMENT node
            party_key = _find_doc_party(entity_id_map)
            if party_key and party_key != (etype, evalue):
                anchor_id = entity_id_map[party_key]
            else:
                anchor_id = doc_anchor_id
        else:
            # Unknown type → fall back to DOCUMENT node
            anchor_id = doc_anchor_id
            rel_type = "SOURCED_FROM"

        if not anchor_id:
            logger.debug(f"No anchor found for orphan {etype}/{evalue}")
            continue

        try:
            db.table("relationships").insert({
                "document_id": document_id,
                "property_id": property_id,
                "source_entity": anchor_id,
                "target_entity": eid,
                "relation_type": rel_type,
                "attributes": {"synthetic": True},
            }).execute()
            rel_count += 1
            orphan_count += 1
            connected_ids.add(eid)
        except Exception as e:
            logger.warning(f"Orphan link failed for {etype}/{evalue}: {e}")

    if orphan_count:
        logger.info(f"Document {document_id}: synthetic edges added for {orphan_count} orphan nodes")

    logger.info(
        f"Document {document_id}: stored {len(entity_id_map)} entities, "
        f"{rel_count} relationships"
    )
    return len(entity_id_map), rel_count


# ── Context retrieval ──────────────────────────────────────────────────────

def get_property_graph_context(property_id: str, max_entities: int = 150) -> str:
    """Retrieve KG entities and relationships for a property and format them
    as a concise text block suitable for prepending to LLM prompts.

    Returns an empty string if no entities exist yet.
    """
    db = get_supabase()

    ent_result = db.table("entities") \
        .select("id, entity_type, value, metadata") \
        .eq("property_id", property_id) \
        .limit(max_entities) \
        .execute()

    entities: list[dict] = ent_result.data or []
    if not entities:
        return ""

    # Build a map from entity UUID → entity record for relationship display
    entity_map: dict[str, dict] = {e["id"]: e for e in entities}

    rel_result = db.table("relationships") \
        .select("relation_type, attributes, source_entity, target_entity") \
        .eq("property_id", property_id) \
        .limit(100) \
        .execute()

    relationships: list[dict] = rel_result.data or []

    # Group entities by type (deduplicated display values)
    by_type: dict[str, list[str]] = {}
    for ent in entities:
        etype = ent["entity_type"]
        val = ent["value"]
        unit = (ent.get("metadata") or {}).get("unit")
        display = f"{val} ({unit})" if unit else val
        bucket = by_type.setdefault(etype, [])
        if display not in bucket:
            bucket.append(display)

    lines = ["=== Knowledge Graph Context ===", "Key Entities:"]
    for etype, values in sorted(by_type.items()):
        lines.append(f"  {etype}: {', '.join(values[:10])}")

    if relationships:
        lines.append("Relationships:")
        for rel in relationships[:50]:
            src = entity_map.get(rel.get("source_entity") or "")
            tgt = entity_map.get(rel.get("target_entity") or "")
            if src and tgt:
                attrs = rel.get("attributes") or {}
                attr_str = (
                    f" [{', '.join(f'{k}={v}' for k, v in attrs.items())}]"
                    if attrs else ""
                )
                lines.append(
                    f"  {src['value']} ({src['entity_type']}) "
                    f"--[{rel['relation_type']}]--> "
                    f"{tgt['value']} ({tgt['entity_type']}){attr_str}"
                )

    lines.append("=== End Knowledge Graph ===")
    return "\n".join(lines)


# ── Cleanup helpers ────────────────────────────────────────────────────────

def delete_document_entities(document_id: str) -> None:
    """Remove all entities and their relationships for the given document."""
    db = get_supabase()
    # Relationships cascade via FK; delete explicitly in case FK cascade not set
    try:
        db.table("relationships").delete().eq("document_id", document_id).execute()
    except Exception as e:
        logger.warning(f"Relationship delete failed for doc {document_id}: {e}")
    try:
        db.table("entities").delete().eq("document_id", document_id).execute()
    except Exception as e:
        logger.warning(f"Entity delete failed for doc {document_id}: {e}")
    logger.info(f"Deleted entities/relationships for document {document_id}")


def delete_property_entities(property_id: str) -> None:
    """Remove all entities and relationships for the given property."""
    db = get_supabase()
    try:
        db.table("relationships").delete().eq("property_id", property_id).execute()
    except Exception as e:
        logger.warning(f"Relationship delete failed for property {property_id}: {e}")
    try:
        db.table("entities").delete().eq("property_id", property_id).execute()
    except Exception as e:
        logger.warning(f"Entity delete failed for property {property_id}: {e}")
    logger.info(f"Deleted entities/relationships for property {property_id}")
