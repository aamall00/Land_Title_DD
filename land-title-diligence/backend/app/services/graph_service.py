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
        except Exception as e:
            logger.warning(f"Relationship insert failed ({relation_type}): {e}")

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
