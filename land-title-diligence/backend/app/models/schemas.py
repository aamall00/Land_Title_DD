from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import datetime
from uuid import UUID
from enum import Enum


# ── Enums ──────────────────────────────────────────────────────────────────

class DocType(str, Enum):
    EC           = "EC"
    RTC          = "RTC"
    SALE_DEED    = "SALE_DEED"
    KHATA        = "KHATA"
    MUTATION     = "MUTATION"
    SKETCH       = "SKETCH"
    LEGAL_HEIR   = "LEGAL_HEIR"
    COURT        = "COURT"
    BBMP_APPROVAL = "BBMP_APPROVAL"
    BDA_APPROVAL  = "BDA_APPROVAL"
    OTHER        = "OTHER"


class RiskLevel(str, Enum):
    LOW      = "LOW"
    MEDIUM   = "MEDIUM"
    HIGH     = "HIGH"
    CRITICAL = "CRITICAL"


class ReportType(str, Enum):
    FULL_DUE_DILIGENCE = "full_due_diligence"
    TITLE_CHAIN        = "title_chain"
    RISK_SUMMARY       = "risk_summary"


# ── Property ───────────────────────────────────────────────────────────────

class PropertyCreate(BaseModel):
    property_name: str
    survey_number: Optional[str] = None
    khata_number:  Optional[str] = None
    taluk:         Optional[str] = None
    hobli:         Optional[str] = None
    village:       Optional[str] = None
    district:      str = "Bangalore Urban"
    total_area:    Optional[str] = None
    address:       Optional[str] = None
    notes:         Optional[str] = None


class PropertyUpdate(BaseModel):
    property_name: Optional[str] = None
    survey_number: Optional[str] = None
    khata_number:  Optional[str] = None
    taluk:         Optional[str] = None
    hobli:         Optional[str] = None
    village:       Optional[str] = None
    district:      Optional[str] = None
    total_area:    Optional[str] = None
    address:       Optional[str] = None
    notes:         Optional[str] = None


class PropertyResponse(BaseModel):
    id:            UUID
    user_id:       UUID
    property_name: str
    survey_number: Optional[str]
    khata_number:  Optional[str]
    taluk:         Optional[str]
    hobli:         Optional[str]
    village:       Optional[str]
    district:      Optional[str]
    total_area:    Optional[str]
    address:       Optional[str]
    notes:         Optional[str]
    created_at:    datetime
    updated_at:    datetime
    document_count: Optional[int] = 0


# ── Document ───────────────────────────────────────────────────────────────

class DocumentResponse(BaseModel):
    id:            UUID
    property_id:   UUID
    user_id:       UUID
    original_name: str
    file_url:      str
    file_size:     Optional[int]
    mime_type:     Optional[str]
    page_count:    Optional[int]
    doc_type:      DocType
    language:      Optional[str]
    ocr_text:      Optional[str]
    metadata:      dict[str, Any] = {}
    status:        str
    error_message: Optional[str]
    uploaded_at:   datetime


class DocumentTypeUpdate(BaseModel):
    doc_type: DocType


# ── Query ──────────────────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    question:  str = Field(..., min_length=3, max_length=2000)
    doc_types: Optional[list[DocType]] = None   # filter to specific doc types
    top_k:     int = Field(default=6, ge=1, le=20)


class QuerySource(BaseModel):
    document_id:   UUID
    original_name: str
    doc_type:      DocType
    chunk_text:    str
    similarity:    float


class QueryResponse(BaseModel):
    id:          UUID
    property_id: UUID
    question:    str
    answer:      str
    sources:     list[QuerySource]
    tokens_used: Optional[int]
    asked_at:    datetime


# ── Due Diligence Check ────────────────────────────────────────────────────

class CheckResult(BaseModel):
    status:   str            # 'PASS' | 'FAIL' | 'WARN' | 'MISSING'
    summary:  str
    findings: list[str] = []
    sources:  list[str] = []  # document names referenced


class DueDiligenceContent(BaseModel):
    title_chain:         Optional[CheckResult] = None
    encumbrances:        Optional[CheckResult] = None
    litigation:          Optional[CheckResult] = None
    khata_consistency:   Optional[CheckResult] = None
    measurement_match:   Optional[CheckResult] = None
    layout_approval:     Optional[CheckResult] = None
    missing_documents:   list[str] = []
    red_flags:           list[str] = []
    overall_risk:        RiskLevel = RiskLevel.MEDIUM
    summary:             str = ""


# ── Report ─────────────────────────────────────────────────────────────────

class ReportRequest(BaseModel):
    report_type: ReportType = ReportType.FULL_DUE_DILIGENCE


class ReportResponse(BaseModel):
    id:           UUID
    property_id:  UUID
    report_type:  ReportType
    content:      DueDiligenceContent
    red_flags:    list[str]
    risk_score:   Optional[int]
    risk_level:   Optional[RiskLevel]
    generated_at: datetime
