import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException, Header

from app.database import get_supabase
from app.models.schemas import QueryRequest, QueryResponse, QuerySource
from app.services.vector_service import similarity_search
from app.services.llm_service import answer_question
from app.services.graph_service import get_property_graph_context

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/properties/{property_id}/query", tags=["Query"])


def _require_user(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    token = authorization.split(" ", 1)[1]
    db = get_supabase()
    result = db.auth.get_user(token)
    if not result or not result.user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return str(result.user.id)


@router.post("", response_model=QueryResponse, status_code=201)
async def ask_question(
    property_id: UUID,
    body: QueryRequest,
    authorization: str | None = Header(default=None),
):
    user_id = _require_user(authorization)
    db = get_supabase()

    # Verify property ownership
    prop_result = db.table("properties") \
        .select("*") \
        .eq("id", str(property_id)) \
        .eq("user_id", user_id) \
        .single() \
        .execute()

    if not prop_result.data:
        raise HTTPException(status_code=404, detail="Property not found")

    property_meta = prop_result.data

    # Retrieve relevant chunks (hybrid: vector + doc_type filter)
    doc_types = [dt.value for dt in body.doc_types] if body.doc_types else None
    chunks = similarity_search(
        query=body.question,
        property_id=str(property_id),
        top_k=body.top_k,
        doc_types=doc_types,
    )

    if not chunks:
        raise HTTPException(
            status_code=422,
            detail="No documents found for this property. Please upload and process documents first.",
        )

    # Fetch knowledge graph context for richer entity-aware answers
    kg_context = get_property_graph_context(str(property_id))

    # Ask Claude
    answer, tokens_used = answer_question(
        question=body.question,
        context_chunks=chunks,
        property_metadata=property_meta,
        kg_context=kg_context or None,
    )

    # Build source list — join with documents table for names
    doc_ids = list({c["document_id"] for c in chunks})
    docs_result = db.table("documents") \
        .select("id, original_name, doc_type") \
        .in_("id", doc_ids) \
        .execute()
    doc_map = {str(d["id"]): d for d in (docs_result.data or [])}

    sources = []
    for chunk in chunks:
        doc = doc_map.get(str(chunk["document_id"]), {})
        sources.append(QuerySource(
            document_id=chunk["document_id"],
            original_name=doc.get("original_name", "Unknown"),
            doc_type=doc.get("doc_type", "OTHER"),
            chunk_text=chunk["chunk_text"],
            similarity=round(chunk.get("similarity", 0.0), 4),
        ))

    # Persist the Q&A
    insert_result = db.table("queries").insert({
        "property_id": str(property_id),
        "user_id": user_id,
        "question": body.question,
        "answer": answer,
        "sources": [s.model_dump(mode="json") for s in sources],
        "tokens_used": tokens_used,
    }).execute()

    if not insert_result.data:
        raise HTTPException(status_code=500, detail="Failed to save query")

    saved = insert_result.data[0]
    saved["sources"] = sources
    return saved


@router.get("/history", response_model=list[QueryResponse])
async def get_query_history(
    property_id: UUID,
    authorization: str | None = Header(default=None),
    limit: int = 20,
):
    user_id = _require_user(authorization)
    db = get_supabase()

    # Verify ownership
    prop = db.table("properties") \
        .select("id") \
        .eq("id", str(property_id)) \
        .eq("user_id", user_id) \
        .single() \
        .execute()
    if not prop.data:
        raise HTTPException(status_code=404, detail="Property not found")

    result = db.table("queries") \
        .select("*") \
        .eq("property_id", str(property_id)) \
        .order("asked_at", desc=True) \
        .limit(limit) \
        .execute()

    rows = []
    for row in (result.data or []):
        # sources stored as JSONB list of dicts
        raw_sources = row.get("sources", [])
        row["sources"] = [QuerySource(**s) for s in raw_sources] if raw_sources else []
        rows.append(row)

    return rows
