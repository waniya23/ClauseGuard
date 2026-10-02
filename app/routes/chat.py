# app/routes/chat.py
"""
Chat and Follow-up Q&A Endpoints for ClauseGuard.

Endpoint:
- POST /api/chat/ask : Ask follow-up questions about an analyzed contract using RAG.
"""

from fastapi import APIRouter, HTTPException, status
from app.models.schemas import ChatRequest, ChatResponse
from app.services.agent_service import answer_document_question
from app.routes.documents import DOCUMENTS_STORE

router = APIRouter(prefix="/api/chat", tags=["Chat"])


@router.post(
    "/ask",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
    summary="Ask a follow-up question about an analyzed document",
    description="Uses Qdrant vector retrieval and Groq LLM to answer questions grounded in the specific contract."
)
async def ask_question(request: ChatRequest):
    """
    Handles follow-up chat queries for a specific document.
    """
    clean_question = request.question.strip()
    if not clean_question:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question cannot be empty."
        )

    # Validate doc_id
    if not request.doc_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document ID ('doc_id') is required."
        )

    # Optional check: If document was analyzed in current session, we can include doc type context
    doc_info = DOCUMENTS_STORE.get(request.doc_id, {})
    doc_type_label = doc_info.get("doc_type_label", "")
    history_context = f"Contract Type: {doc_type_label}" if doc_type_label else ""

    try:
        answer = answer_document_question(
            doc_id=request.doc_id,
            question=clean_question,
            chat_history=history_context
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate answer: {str(exc)}"
        )

    return ChatResponse(
        answer=answer,
        doc_id=request.doc_id
    )
