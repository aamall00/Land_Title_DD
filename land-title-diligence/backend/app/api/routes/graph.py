import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException, Header

from app.database import get_supabase

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/properties/{property_id}/graph", tags=["Graph"])


def _require_user(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    token = authorization.split(" ", 1)[1]
    db = get_supabase()
    result = db.auth.get_user(token)
    if not result or not result.user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return str(result.user.id)


@router.get("")
async def get_property_graph(
    property_id: UUID,
    authorization: str | None = Header(default=None),
):
    """Return graph nodes (entities) and links (relationships) for a property.

    Entities sharing the same canonical_id are merged into a single node so
    the same person/survey-number appearing across multiple documents is shown
    as one node with a document-count badge.
    """
    user_id = _require_user(authorization)
    db = get_supabase()

    # Verify ownership
    prop = (
        db.table("properties")
        .select("id")
        .eq("id", str(property_id))
        .eq("user_id", user_id)
        .single()
        .execute()
    )
    if not prop.data:
        raise HTTPException(status_code=404, detail="Property not found")

    # Fetch all entity occurrences for this property
    ent_res = (
        db.table("entities")
        .select("id, entity_type, value, canonical_id, document_id")
        .eq("property_id", str(property_id))
        .limit(500)
        .execute()
    )
    entities: list[dict] = ent_res.data or []

    # Fetch all relationships for this property
    rel_res = (
        db.table("relationships")
        .select("source_entity, target_entity, relation_type, attributes")
        .eq("property_id", str(property_id))
        .limit(500)
        .execute()
    )
    relationships: list[dict] = rel_res.data or []

    # ── Build nodes ────────────────────────────────────────────────────────
    # entity occurrence id → canonical node id
    entity_to_node: dict[str, str] = {}
    nodes_map: dict[str, dict] = {}

    for ent in entities:
        node_id: str = ent.get("canonical_id") or ent["id"]
        entity_to_node[ent["id"]] = node_id

        if node_id not in nodes_map:
            nodes_map[node_id] = {
                "id": node_id,
                "name": ent["value"],
                "type": ent["entity_type"],
                "doc_count": 1,
                "docs": {ent["document_id"]},
            }
        else:
            nodes_map[node_id]["docs"].add(ent["document_id"])
            nodes_map[node_id]["doc_count"] = len(nodes_map[node_id]["docs"])

    # Convert sets to counts for JSON serialisation
    for node in nodes_map.values():
        node.pop("docs", None)

    # ── Build links ────────────────────────────────────────────────────────
    links: list[dict] = []
    seen: set[tuple] = set()

    for rel in relationships:
        src = entity_to_node.get(rel["source_entity"])
        tgt = entity_to_node.get(rel["target_entity"])
        if not src or not tgt or src == tgt:
            continue
        key = (src, tgt, rel["relation_type"])
        if key in seen:
            continue
        seen.add(key)
        links.append({
            "source": src,
            "target": tgt,
            "label": rel["relation_type"],
            "attributes": rel.get("attributes") or {},
        })

    logger.info(
        f"Graph for property {property_id}: "
        f"{len(nodes_map)} nodes, {len(links)} links"
    )
    return {"nodes": list(nodes_map.values()), "links": links}
