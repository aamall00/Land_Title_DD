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
    """
    PropertyUpdate schema for partial property information updates.

    This Pydantic BaseModel is used for PATCH/PUT requests to update existing property records.
    All fields are optional, allowing clients to update only the properties they need to modify
    without requiring a complete property object.

    Attributes:
        property_name (Optional[str]): The name or identifier of the property. Can be None if not being updated.
        survey_number (Optional[str]): The official survey number assigned to the property. Can be None if not being updated.
        khata_number (Optional[str]): The khata (tax) number for property tax identification. Can be None if not being updated.
        taluk (Optional[str]): The taluk (administrative subdivision) where the property is located. Can be None if not being updated.
        hobli (Optional[str]): The hobli (sub-district) administrative division. Can be None if not being updated.
        village (Optional[str]): The village name where the property is situated. Can be None if not being updated.
        district (Optional[str]): The district name for geographical classification. Can be None if not being updated.
        total_area (Optional[str]): The total area of the property (typically in square feet or acres). Can be None if not being updated.
        address (Optional[str]): The complete physical address of the property. Can be None if not being updated.
        notes (Optional[str]): Additional notes or remarks about the property. Can be None if not being updated.

    Note:
        All fields use Optional[str] annotation, meaning each field can accept either a string value or None.
        This design pattern enables partial updates where only non-None fields need to be processed,
        while None values indicate no update is required for that particular field.
    """
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


# ── Knowledge Graph ────────────────────────────────────────────────────────

class EntityResponse(BaseModel):
    id:           UUID
    document_id:  UUID
    property_id:  UUID
    entity_type:  str
    value:        str
    canonical_id: Optional[UUID] = None
    metadata:     dict[str, Any] = {}
    created_at:   datetime


class RelationshipResponse(BaseModel):
    id:            UUID
    document_id:   UUID
    property_id:   UUID
    source_entity: UUID
    target_entity: UUID
    relation_type: str
    attributes:    dict[str, Any] = {}
    created_at:    datetime


class CanonicalEntityResponse(BaseModel):
    id:            UUID
    entity_type:   str
    canonical_val: str
    aliases:       list[str] = []
    created_at:    datetime


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
