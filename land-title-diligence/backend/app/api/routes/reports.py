import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException, Header, BackgroundTasks

from app.database import get_supabase
from app.models.schemas import ReportRequest, ReportResponse, ReportType
from app.services.report_service import generate_due_diligence_report

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/properties/{property_id}/reports", tags=["Reports"])


def _require_user(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    token = authorization.split(" ", 1)[1]
    db = get_supabase()
    result = db.auth.get_user(token)
    if not result or not result.user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return str(result.user.id)


@router.post("", response_model=ReportResponse, status_code=201)
async def generate_report(
    property_id: UUID,
    body: ReportRequest,
    authorization: str | None = Header(default=None),
):
    """Generate a full due diligence report. This calls Claude multiple times — may take 30-60s."""
    user_id = _require_user(authorization)
    db = get_supabase()

    # Verify property ownership
    prop = db.table("properties") \
        .select("id") \
        .eq("id", str(property_id)) \
        .eq("user_id", user_id) \
        .single() \
        .execute()
    if not prop.data:
        raise HTTPException(status_code=404, detail="Property not found")

    # Check at least one document is ready
    docs = db.table("documents") \
        .select("id") \
        .eq("property_id", str(property_id)) \
        .eq("status", "ready") \
        .limit(1) \
        .execute()
    if not docs.data:
        raise HTTPException(
            status_code=422,
            detail="No processed documents found. Upload and wait for processing to complete.",
        )

    report = await generate_due_diligence_report(
        property_id=str(property_id),
        report_type=body.report_type.value,
    )
    return report


@router.get("", response_model=list[ReportResponse])
async def list_reports(
    property_id: UUID,
    authorization: str | None = Header(default=None),
):
    user_id = _require_user(authorization)
    db = get_supabase()

    prop = db.table("properties") \
        .select("id") \
        .eq("id", str(property_id)) \
        .eq("user_id", user_id) \
        .single() \
        .execute()
    if not prop.data:
        raise HTTPException(status_code=404, detail="Property not found")

    result = db.table("reports") \
        .select("*") \
        .eq("property_id", str(property_id)) \
        .order("generated_at", desc=True) \
        .execute()

    return result.data or []


@router.get("/{report_id}", response_model=ReportResponse)
async def get_report(
    property_id: UUID,
    report_id: UUID,
    authorization: str | None = Header(default=None),
):
    user_id = _require_user(authorization)
    db = get_supabase()

    result = db.table("reports") \
        .select("*") \
        .eq("id", str(report_id)) \
        .eq("property_id", str(property_id)) \
        .single() \
        .execute()

    if not result.data:
        raise HTTPException(status_code=404, detail="Report not found")
    return result.data
