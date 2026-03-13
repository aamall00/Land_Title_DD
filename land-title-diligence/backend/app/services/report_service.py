"""Report Service — orchestrates all due diligence checks and builds the final report."""

import logging
from uuid import UUID

from app.database import get_supabase
from app.services.vector_service import similarity_search
from app.services.llm_service import run_due_diligence_check

logger = logging.getLogger(__name__)


# ── Check Definitions ──────────────────────────────────────────────────────

DUE_DILIGENCE_CHECKS = [
    {
        "name": "Title Chain",
        "key": "title_chain",
        "doc_types": ["EC", "SALE_DEED", "MUTATION"],
        "query": "ownership history transfer chain previous owners title",
        "prompt": (
            "Review the documents for a 30-year title chain (as required under Karnataka law). "
            "Identify all previous owners, dates of transfer, and any gaps in the chain. "
            "Check if the current owner matches across EC, Sale Deed, and Khata."
        ),
    },
    {
        "name": "Encumbrances",
        "key": "encumbrances",
        "doc_types": ["EC"],
        "query": "encumbrance mortgage loan attachment lien charge",
        "prompt": (
            "Review the Encumbrance Certificate for any outstanding mortgages, loans, "
            "court attachments, or charges. Determine if the property is free from encumbrances."
        ),
    },
    {
        "name": "Litigation",
        "key": "litigation",
        "doc_types": ["COURT", "EC", "SALE_DEED"],
        "query": "court case litigation suit dispute injunction stay",
        "prompt": (
            "Check for any pending or past litigation, court cases, disputes, injunctions, "
            "or stay orders on the property. Identify parties involved."
        ),
    },
    {
        "name": "Khata Consistency",
        "key": "khata_consistency",
        "doc_types": ["KHATA", "SALE_DEED", "RTC"],
        "query": "khata owner name BBMP property tax assessment",
        "prompt": (
            "Compare the owner name on the Khata certificate with the Sale Deed and RTC. "
            "Check if khata has been transferred to the current owner. "
            "Verify BBMP/panchayat jurisdiction."
        ),
    },
    {
        "name": "Measurement Match",
        "key": "measurement_match",
        "doc_types": ["RTC", "SALE_DEED", "SKETCH"],
        "query": "area measurement square feet acres survey number boundary dimensions",
        "prompt": (
            "Compare the land area/measurement across RTC, Sale Deed, and Survey Sketch. "
            "Flag any discrepancies in area, survey number, or boundaries."
        ),
    },
    {
        "name": "Layout & Plan Approval",
        "key": "layout_approval",
        "doc_types": ["BBMP_APPROVAL", "BDA_APPROVAL", "OTHER"],
        "query": "BBMP BDA layout plan sanction approval conversion DC order",
        "prompt": (
            "Check if the property has valid BBMP/BDA layout approval, plan sanction, "
            "or DC conversion order if required. Identify the approval date and authority."
        ),
    },
]


# ── Missing Document Check ─────────────────────────────────────────────────

REQUIRED_DOCS = {
    "EC": "Encumbrance Certificate (at least 30 years)",
    "RTC": "RTC / Pahani (latest)",
    "SALE_DEED": "Registered Sale Deed",
    "KHATA": "Khata Certificate & Extract",
    "MUTATION": "Mutation Register entries",
    "SKETCH": "Survey Sketch / FMB",
}


def _check_missing_documents(property_id: str) -> list[str]:
    """Return list of document types missing for this property."""
    db = get_supabase()
    result = db.table("documents") \
        .select("doc_type") \
        .eq("property_id", str(property_id)) \
        .eq("status", "ready") \
        .execute()

    uploaded_types = {row["doc_type"] for row in (result.data or [])}
    missing = []
    for doc_type, label in REQUIRED_DOCS.items():
        if doc_type not in uploaded_types:
            missing.append(f"{label} ({doc_type})")
    return missing


# ── Risk Scoring ────────────────────────────────────────────────────────────

def _compute_risk(check_results: dict, red_flags: list[str], missing_docs: list[str]) -> tuple[int, str]:
    """Compute a 0-100 risk score and risk level."""
    score = 0

    status_weights = {"FAIL": 25, "WARN": 10, "MISSING": 15, "PASS": 0}
    for result in check_results.values():
        if isinstance(result, dict):
            status = result.get("status", "WARN")
            score += status_weights.get(status, 10)

    score += len(red_flags) * 10
    score += len(missing_docs) * 5
    score = min(score, 100)

    if score <= 20:
        level = "LOW"
    elif score <= 45:
        level = "MEDIUM"
    elif score <= 70:
        level = "HIGH"
    else:
        level = "CRITICAL"

    return score, level


# ── Main Orchestrator ───────────────────────────────────────────────────────

async def generate_due_diligence_report(
    property_id: str,
    report_type: str = "full_due_diligence",
) -> dict:
    """Run all checks, collect red flags, build report, persist to DB."""
    db = get_supabase()

    # Fetch property metadata for context
    prop_result = db.table("properties").select("*").eq("id", str(property_id)).single().execute()
    property_meta = prop_result.data or {}

    check_results: dict = {}
    all_red_flags: list[str] = []

    # Run each check
    for check in DUE_DILIGENCE_CHECKS:
        if report_type == "title_chain" and check["key"] not in ("title_chain", "encumbrances"):
            continue
        if report_type == "risk_summary" and check["key"] not in ("encumbrances", "litigation"):
            continue

        logger.info(f"Running check: {check['name']}")
        chunks = similarity_search(
            query=check["query"],
            property_id=property_id,
            top_k=8,
            doc_types=check["doc_types"],
        )
        result = run_due_diligence_check(
            check_name=check["name"],
            check_prompt=check["prompt"],
            context_chunks=chunks,
            property_metadata=property_meta,
        )
        check_results[check["key"]] = result

        if result.get("status") in ("FAIL", "WARN"):
            for finding in result.get("findings", []):
                all_red_flags.append(f"[{check['name']}] {finding}")

    # Missing documents
    missing_docs = _check_missing_documents(property_id)

    # Risk scoring
    risk_score, risk_level = _compute_risk(check_results, all_red_flags, missing_docs)

    # Build content payload
    content = {
        **check_results,
        "missing_documents": missing_docs,
        "red_flags": all_red_flags,
        "overall_risk": risk_level,
        "summary": (
            f"Due diligence completed. Risk level: {risk_level}. "
            f"{len(all_red_flags)} issue(s) flagged, "
            f"{len(missing_docs)} document(s) missing."
        ),
    }

    # Get current user_id from the property
    user_id = property_meta.get("user_id")

    # Persist report
    insert_result = db.table("reports").insert({
        "property_id": str(property_id),
        "user_id": str(user_id),
        "report_type": report_type,
        "content": content,
        "red_flags": all_red_flags,
        "risk_score": risk_score,
        "risk_level": risk_level,
    }).execute()

    report = insert_result.data[0] if insert_result.data else {}
    report["content"] = content
    return report
