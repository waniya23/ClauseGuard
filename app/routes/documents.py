# app/routes/documents.py
"""
Document Analysis Endpoints for ClauseGuard.

Endpoints:
- POST /api/documents/analyze : Upload and analyze PDF contract using LangGraph pipeline.
- GET  /api/documents/{doc_id}: Retrieve cached analysis report for an analyzed document.
"""

import os
import time
import uuid
from typing import Dict, Any
from fastapi import APIRouter, UploadFile, File, HTTPException, status
from app.config import settings
from app.models.schemas import DocumentAnalysisResponse
from app.services.agent_service import analysis_pipeline

router = APIRouter(prefix="/api/documents", tags=["Documents"])

# In-memory document store for fast retrieval by doc_id
DOCUMENTS_STORE: Dict[str, Dict[str, Any]] = {}


@router.post(
    "/analyze",
    response_model=DocumentAnalysisResponse,
    status_code=status.HTTP_200_OK,
    summary="Upload and analyze a PDF contract",
    description="Processes PDF bytes through validation, Phase-1 rule scanning, Qdrant vector indexing, and Groq LLM synthesis."
)
async def analyze_document(file: UploadFile = File(...)):
    """
    Accepts a PDF document upload, executes the LangGraph state machine,
    and returns a structured risk score and analysis.
    """
    # 1. Validate file extension
    ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file format. Please upload a PDF, PNG, JPG, or JPEG file."
        )

    # 2. Read file bytes
    try:
        file_bytes = await file.read()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read uploaded file: {str(exc)}"
        )

    # 3. Check file size against configured limit
    size_mb = len(file_bytes) / (1024 * 1024)
    if size_mb > settings.MAX_FILE_SIZE_MB:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size ({size_mb:.2f} MB) exceeds maximum allowed size ({settings.MAX_FILE_SIZE_MB} MB)."
        )

    # 4. Generate unique doc_id
    doc_id = f"doc_{uuid.uuid4().hex[:12]}"

    # 5. Save temporary copy in uploads directory
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    temp_file_path = os.path.join(settings.UPLOAD_DIR, f"{doc_id}_{file.filename}")
    try:
        with open(temp_file_path, "wb") as f:
            f.write(file_bytes)
    except Exception as exc:
        print(f"[Warning] Could not persist temp file to uploads/: {exc}")

    # 6. Initialize LangGraph State
    initial_state = {
        "doc_id": doc_id,
        "filename": file.filename,
        "file_bytes": file_bytes,
        "start_time": time.time(),
        "pdf_data": None,
        "full_text": "",
        "is_scanned": False,
        "rule_analysis": None,
        "llm_summary": "",
        "processing_time_seconds": 0.0,
        "error": None,
        "final_response": None
    }

    # 7. Execute the LangGraph pipeline
    try:
        final_state = analysis_pipeline.invoke(initial_state)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error executing analysis pipeline: {str(exc)}"
        )

    # 8. Check for unrecoverable errors
    if final_state.get("error"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=final_state["error"]
        )

    response_payload = final_state.get("final_response")
    if not response_payload:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Pipeline completed but produced empty response payload."
        )

    # 9. Cache in document store for future retrieval
    DOCUMENTS_STORE[doc_id] = response_payload

    return response_payload


@router.get(
    "/{doc_id}",
    response_model=DocumentAnalysisResponse,
    status_code=status.HTTP_200_OK,
    summary="Get previously analyzed document by ID"
)
async def get_document_analysis(doc_id: str):
    """
    Retrieves the analysis result for a given doc_id from memory store.
    """
    if doc_id not in DOCUMENTS_STORE:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID '{doc_id}' not found."
        )

    return DOCUMENTS_STORE[doc_id]
