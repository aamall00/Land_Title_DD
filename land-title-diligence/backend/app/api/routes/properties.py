from fastapi import APIRouter, HTTPException, Header
from uuid import UUID

from app.database import get_supabase
from app.models.schemas import PropertyCreate, PropertyUpdate, PropertyResponse

router = APIRouter(prefix="/properties", tags=["Properties"])


def _require_user(authorization: str | None) -> str:
    """Extract user_id from JWT via Supabase auth.getUser().
    Raises 401 if missing/invalid.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    token = authorization.split(" ", 1)[1]
    db = get_supabase()
    result = db.auth.get_user(token)
    if not result or not result.user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return str(result.user.id)


@router.get("", response_model=list[PropertyResponse])
async def list_properties(authorization: str | None = Header(default=None)):
    user_id = _require_user(authorization)
    db = get_supabase()

    result = db.table("properties") \
        .select("*") \
        .eq("user_id", user_id) \
        .order("created_at", desc=True) \
        .execute()

    properties = []
    for row in (result.data or []):
        row["document_count"] = 0
        properties.append(row)

    return properties


@router.post("", response_model=PropertyResponse, status_code=201)
async def create_property(
    body: PropertyCreate,
    authorization: str | None = Header(default=None),
):
    user_id = _require_user(authorization)
    db = get_supabase()

    payload = body.model_dump()
    payload["user_id"] = user_id

    try:
        result = db.table("properties").insert(payload).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to create property")

    row = result.data[0]
    row["document_count"] = 0
    return row


@router.get("/{property_id}", response_model=PropertyResponse)
async def get_property(
    property_id: UUID,
    authorization: str | None = Header(default=None),
):
    user_id = _require_user(authorization)
    db = get_supabase()

    result = db.table("properties") \
        .select("*") \
        .eq("id", str(property_id)) \
        .eq("user_id", user_id) \
        .single() \
        .execute()

    if not result.data:
        raise HTTPException(status_code=404, detail="Property not found")

    row = result.data
    row["document_count"] = 0
    return row


@router.patch("/{property_id}", response_model=PropertyResponse)
async def update_property(
    property_id: UUID,
    body: PropertyUpdate,
    authorization: str | None = Header(default=None),
):
    user_id = _require_user(authorization)
    db = get_supabase()

    # Verify ownership
    existing = db.table("properties") \
        .select("id") \
        .eq("id", str(property_id)) \
        .eq("user_id", user_id) \
        .single() \
        .execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Property not found")

    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    updates["updated_at"] = "now()"

    result = db.table("properties") \
        .update(updates) \
        .eq("id", str(property_id)) \
        .execute()

    if not result.data:
        raise HTTPException(status_code=500, detail="Update failed")

    row = result.data[0]
    row["document_count"] = 0
    return row


@router.delete("/{property_id}", status_code=204)
async def delete_property(
    property_id: UUID,
    authorization: str | None = Header(default=None),
):
    user_id = _require_user(authorization)
    db = get_supabase()

    existing = db.table("properties") \
        .select("id") \
        .eq("id", str(property_id)) \
        .eq("user_id", user_id) \
        .single() \
        .execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Property not found")

    # Cascade deletes documents, embeddings, queries, reports
    db.table("properties").delete().eq("id", str(property_id)).execute()
