import io
import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException, Header, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import JSONResponse

from app.database import get_supabase
from app.config import get_settings
from app.models.schemas import DocumentResponse, DocumentTypeUpdate, DocType
from app.services.ocr_service import extract_text
from app.services.embedding_service import chunk_text
from app.services.vector_service import store_document_embeddings, delete_document_embeddings
from app.utils.document_classifier import classify_document, extract_metadata_from_text

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/properties/{property_id}/documents", tags=["Documents"])


def _require_user(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    token = authorization.split(" ", 1)[1]
    db = get_supabase()
    result = db.auth.get_user(token)
    if not result or not result.user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return str(result.user.id)


def _verify_property(property_id: str, user_id: str):
    db = get_supabase()
    res = db.table("properties") \
        .select("id") \
        .eq("id", property_id) \
        .eq("user_id", user_id) \
        .single() \
        .execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Property not found")


async def _process_document(document_id: str, property_id: str, file_bytes: bytes, mime_type: str):
    """Background task: OCR → classify → embed → mark ready."""
    db = get_supabase()
    try:
        # Mark as processing
        db.table("documents").update({"status": "processing"}).eq("id", document_id).execute()

        # OCR
        ocr_text, page_count = extract_text(file_bytes, mime_type)

        # Get filename for classification
        doc_result = db.table("documents").select("original_name, doc_type").eq("id", document_id).single().execute()
        original_name = doc_result.data.get("original_name", "") if doc_result.data else ""
        existing_type = doc_result.data.get("doc_type", "OTHER") if doc_result.data else "OTHER"

        # Auto-classify if still OTHER
        doc_type = existing_type
        if doc_type == "OTHER":
            doc_type = classify_document(original_name, ocr_text)

        # Extract metadata
        metadata = extract_metadata_from_text(ocr_text)

        # Update document record
        db.table("documents").update({
            "ocr_text": ocr_text,
            "page_count": page_count,
            "doc_type": doc_type,
            "metadata": metadata,
            "status": "ready",
        }).eq("id", document_id).execute()

        # Store embeddings with doc_type context header
        if ocr_text.strip():
            store_document_embeddings(
                document_id=document_id,
                property_id=property_id,
                ocr_text=ocr_text,
                doc_type=doc_type,
                extra_metadata=metadata,
            )

        logger.info(f"Document {document_id} processed: {doc_type}, {page_count} pages")

    except Exception as e:
        logger.error(f"Processing failed for {document_id}: {e}", exc_info=True)
        db.table("documents").update({
            "status": "error",
            "error_message": str(e)[:500],
        }).eq("id", document_id).execute()


@router.post("", response_model=DocumentResponse, status_code=202)
async def upload_document(
    property_id: UUID,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    doc_type: str = Form(default="OTHER"),
    authorization: str | None = Header(default=None),
):
    user_id = _require_user(authorization)
    _verify_property(str(property_id), user_id)

    s = get_settings()
    db = get_supabase()

    # Validate file
    file_bytes = await file.read()
    if len(file_bytes) > s.max_upload_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"File exceeds {s.max_upload_mb}MB limit")

    allowed_types = {
        "application/pdf", "image/png", "image/jpeg",
        "image/jpg", "image/tiff", "image/webp",
    }
    content_type = file.content_type or "application/octet-stream"
    if content_type not in allowed_types:
        raise HTTPException(status_code=415, detail=f"Unsupported file type: {content_type}")

    # Upload to Supabase Storage
    storage_path = f"{user_id}/{property_id}/{file.filename}"
    db.storage.from_(s.supabase_storage_bucket).upload(
        path=storage_path,
        file=file_bytes,
        file_options={"content-type": content_type},
    )

    # Get signed URL (private bucket)
    file_url = storage_path  # Store path; generate signed URLs on read

    # Insert document record
    insert_result = db.table("documents").insert({
        "property_id": str(property_id),
        "user_id": user_id,
        "original_name": file.filename,
        "file_url": file_url,
        "file_size": len(file_bytes),
        "mime_type": content_type,
        "doc_type": doc_type,
        "status": "pending",
        "metadata": {},
    }).execute()

    if not insert_result.data:
        raise HTTPException(status_code=500, detail="Failed to create document record")

    document = insert_result.data[0]

    # Kick off background processing
    background_tasks.add_task(
        _process_document,
        document["id"],
        str(property_id),
        file_bytes,
        content_type,
    )

    return document


@router.get("", response_model=list[DocumentResponse])
async def list_documents(
    property_id: UUID,
    authorization: str | None = Header(default=None),
):
    user_id = _require_user(authorization)
    _verify_property(str(property_id), user_id)

    db = get_supabase()
    result = db.table("documents") \
        .select("*") \
        .eq("property_id", str(property_id)) \
        .order("uploaded_at", desc=True) \
        .execute()
    return result.data or []


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    property_id: UUID,
    document_id: UUID,
    authorization: str | None = Header(default=None),
):
    user_id = _require_user(authorization)
    _verify_property(str(property_id), user_id)

    db = get_supabase()
    result = db.table("documents") \
        .select("*") \
        .eq("id", str(document_id)) \
        .eq("property_id", str(property_id)) \
        .single() \
        .execute()

    if not result.data:
        raise HTTPException(status_code=404, detail="Document not found")
    return result.data


@router.patch("/{document_id}/type", response_model=DocumentResponse)
async def update_doc_type(
    property_id: UUID,
    document_id: UUID,
    body: DocumentTypeUpdate,
    authorization: str | None = Header(default=None),
):
    """Manually override the auto-detected document type."""
    user_id = _require_user(authorization)
    _verify_property(str(property_id), user_id)

    db = get_supabase()
    result = db.table("documents") \
        .update({"doc_type": body.doc_type.value}) \
        .eq("id", str(document_id)) \
        .eq("property_id", str(property_id)) \
        .execute()

    if not result.data:
        raise HTTPException(status_code=404, detail="Document not found")

    # Update metadata in embeddings too
    db.table("embeddings") \
        .update({"metadata": {"doc_type": body.doc_type.value}}) \
        .eq("document_id", str(document_id)) \
        .execute()

    return result.data[0]


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    property_id: UUID,
    document_id: UUID,
    authorization: str | None = Header(default=None),
):
    user_id = _require_user(authorization)
    _verify_property(str(property_id), user_id)

    db = get_supabase()
    doc_result = db.table("documents") \
        .select("file_url") \
        .eq("id", str(document_id)) \
        .eq("property_id", str(property_id)) \
        .single() \
        .execute()

    if not doc_result.data:
        raise HTTPException(status_code=404, detail="Document not found")

    file_url = doc_result.data.get("file_url", "")

    # Remove from storage
    s = get_settings()
    try:
        db.storage.from_(s.supabase_storage_bucket).remove([file_url])
    except Exception as e:
        logger.warning(f"Storage delete failed (non-fatal): {e}")

    # Remove embeddings
    delete_document_embeddings(str(document_id))

    # Remove document row (embeddings cascade-deleted above)
    db.table("documents").delete().eq("id", str(document_id)).execute()
