# app/services/agent_service.py
"""
LangGraph State Machine Agent Service for ClauseGuard.

Production Responsibilities:
1. Define AnalysisState: Typed container passing through all pipeline nodes.
2. Node Execution:
   - Node 1: PDF text extraction and validation
   - Node 2: Rules-based risk scanning (Phase 1)
   - Node 3: Vector indexing in Qdrant for RAG
   - Node 4: LLM synthesis and plain-English breakdown (Phase 2 via Groq)
   - Node 5: Response assembly and schema normalization
3. Graph Compilation: Compile StateGraph into an executable, resilient workflow.
"""

import time
from typing import Optional, TypedDict
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, START, END

from app.config import settings
from app.services.pdf_service import extract_text_from_pdf_bytes, PDFProcessingError
from app.services.risk_service import analyze_document_risk
from app.services.vector_service import vector_service
from app.prompts.analysis import SYSTEM_LEGAL_ANALYST_PROMPT, DOCUMENT_ANALYSIS_PROMPT, CHAT_RAG_PROMPT


# ==========================================
# 1. STATE DEFINITION
# ==========================================

class AnalysisState(TypedDict):
    """
    The shared state container passed between all nodes in the LangGraph pipeline.
    Each node receives this state, updates specific keys, and passes it forward.
    """
    doc_id: str
    filename: str
    file_bytes: bytes
    start_time: float

    # Extracted document content
    pdf_data: Optional[dict]
    full_text: str
    is_scanned: bool

    # Phase 1: Rule-based risk findings
    rule_analysis: Optional[dict]

    # Phase 2: LLM analysis
    llm_summary: str

    # Performance & final structured payload
    processing_time_seconds: float
    error: Optional[str]
    final_response: Optional[dict]


# ==========================================
# 2. LLM CLIENT INITIALIZATION
# ==========================================

def get_llm(temperature: float = 0.1) -> ChatGroq:
    """
    Initializes the Groq LLM client using Llama 3.3.
    Temperature 0.1 ensures highly factual, consistent legal analysis.
    """
    return ChatGroq(
        model_name="llama-3.3-70b-versatile",
        groq_api_key=settings.GROQ_API_KEY,
        temperature=temperature,
        max_retries=2,
        timeout=30
    )


# ==========================================
# 3. GRAPH NODES (Pipeline Workers)
# ==========================================

def extract_pdf_node(state: AnalysisState) -> dict:
    """
    Node 1: Extracts text, page data, and metadata from the raw PDF bytes.
    """
    try:
        pdf_data = extract_text_from_pdf_bytes(
            file_bytes=state["file_bytes"],
            filename=state["filename"]
        )
        return {
            "pdf_data": pdf_data,
            "full_text": pdf_data["full_text"],
            "is_scanned": pdf_data["is_scanned"],
            "error": None
        }
    except Exception as exc:
        return {
            "error": f"PDF Extraction Failed: {str(exc)}",
            "full_text": "",
            "is_scanned": False,
            "pdf_data": None
        }


def rules_risk_node(state: AnalysisState) -> dict:
    """
    Node 2: Runs Phase 1 rules-based keyword scanning against the contract text.
    """
    if state.get("error"):
        return {}

    full_text = state.get("full_text", "")
    if not full_text.strip():
        # Scanned PDF or empty text
        return {
            "rule_analysis": {
                "score": 0,
                "level": "LOW",
                "level_emoji": "🟢",
                "doc_type": "general",
                "doc_type_label": "Scanned Document",
                "advice": "This document appears to be a scanned image with no selectable text.",
                "warnings": [],
                "total_issues": 0
            }
        }

    rule_results = analyze_document_risk(full_text)
    return {"rule_analysis": rule_results}


def vector_index_node(state: AnalysisState) -> dict:
    """
    Node 3: Chunks text and indexes embeddings into Qdrant for follow-up chat RAG.
    """
    if state.get("error"):
        return {}

    pdf_data = state.get("pdf_data")
    if pdf_data and pdf_data.get("pages"):
        try:
            vector_service.index_document_pages(
                doc_id=state["doc_id"],
                pages_data=pdf_data["pages"]
            )
        except Exception as exc:
            # We log or note the error, but do not crash the pipeline if vector indexing has a minor hiccup
            print(f"[Warning] Vector indexing encountered an issue: {exc}")

    return {}


def llm_synthesis_node(state: AnalysisState) -> dict:
    """
    Node 4: Uses Groq LLM (Llama 3.3) to generate a friendly, plain-English summary,
    rights & obligations breakdown, and practical negotiation advice.
    """
    if state.get("error"):
        return {"llm_summary": "Analysis could not be generated due to an error in reading the document."}

    full_text = state.get("full_text", "")
    if state.get("is_scanned") or not full_text.strip():
        return {
            "llm_summary": (
                "### Notice: Scanned Document Detected\n\n"
                "ClauseGuard could not find selectable text in this PDF. It appears to be a scanned image or photo. "
                "Please upload a text-selectable PDF or convert your document using an OCR tool."
            )
        }

    rule_analysis = state.get("rule_analysis") or {}
    doc_type = rule_analysis.get("doc_type_label", "Contract")
    warnings_list = rule_analysis.get("warnings", [])

    # Format detected warnings for prompt context
    if warnings_list:
        warnings_formatted = "\n".join(
            f"- [{w['clause']}] Warning: {w['warning']} (Law: {w['law_reference']})"
            for w in warnings_list
        )
    else:
        warnings_formatted = "No explicit high-risk keywords flagged by Phase 1 automated rules."

    # Prepare prompt messages
    user_prompt_content = DOCUMENT_ANALYSIS_PROMPT.format(
        doc_type=doc_type,
        detected_warnings=warnings_formatted,
        contract_text=full_text[:12000]  # Feed generous context (12k chars) to stay safely within token limits
    )

    try:
        llm = get_llm()
        messages = [
            SystemMessage(content=SYSTEM_LEGAL_ANALYST_PROMPT),
            HumanMessage(content=user_prompt_content)
        ]
        response = llm.invoke(messages)
        summary_text = response.content
    except Exception as exc:
        summary_text = (
            f"Automated risk scoring completed, but AI detailed synthesis could not be reached: {str(exc)}.\n\n"
            f"Please review the detected warnings listed in the dashboard."
        )

    return {"llm_summary": summary_text}


def assemble_response_node(state: AnalysisState) -> dict:
    """
    Node 5: Packages the final analysis into a structured response matching DocumentAnalysisResponse schema.
    """
    elapsed = time.time() - state.get("start_time", time.time())
    rule_analysis = state.get("rule_analysis") or {}

    # Map warnings into format expected by frontend & schemas
    raw_warnings = rule_analysis.get("warnings", [])
    formatted_warnings = []
    for w in raw_warnings:
        formatted_warnings.append({
            "clause_type": w.get("clause", "Unknown"),
            "warning_message": f"{w.get('warning', '')} (Reference: {w.get('law_reference', '')})",
            "risk_points": w.get("points", 0)
        })

    final_payload = {
        "doc_id": state["doc_id"],
        "filename": state["filename"],
        "risk_score": rule_analysis.get("score", 0),
        "risk_level": rule_analysis.get("level", "LOW"),
        "warnings": formatted_warnings,
        "summary": state.get("llm_summary", "Summary not available."),
        "processing_time_seconds": round(elapsed, 2),
        "doc_type": rule_analysis.get("doc_type", "general"),
        "doc_type_label": rule_analysis.get("doc_type_label", "General Agreement"),
        "advice": rule_analysis.get("advice", "Review terms carefully."),
        "total_issues": rule_analysis.get("total_issues", 0),
        "is_scanned": state.get("is_scanned", False)
    }

    return {
        "processing_time_seconds": round(elapsed, 2),
        "final_response": final_payload
    }


# ==========================================
# 4. GRAPH CONSTRUCTION & COMPILATION
# ==========================================

def build_analysis_graph() -> StateGraph:
    """
    Builds and compiles the sequential LangGraph pipeline.
    Workflow: START -> extract_pdf -> rules_risk -> vector_index -> llm_synthesis -> assemble_response -> END
    """
    workflow = StateGraph(AnalysisState)

    # Register nodes
    workflow.add_node("extract_pdf", extract_pdf_node)
    workflow.add_node("rules_risk", rules_risk_node)
    workflow.add_node("vector_index", vector_index_node)
    workflow.add_node("llm_synthesis", llm_synthesis_node)
    workflow.add_node("assemble_response", assemble_response_node)

    # Connect edges
    workflow.add_edge(START, "extract_pdf")
    workflow.add_edge("extract_pdf", "rules_risk")
    workflow.add_edge("rules_risk", "vector_index")
    workflow.add_edge("vector_index", "llm_synthesis")
    workflow.add_edge("llm_synthesis", "assemble_response")
    workflow.add_edge("assemble_response", END)

    return workflow.compile()


# Global compiled pipeline instance
analysis_pipeline = build_analysis_graph()


# ==========================================
# 5. CHAT RAG EXECUTION FUNCTION
# ==========================================

def answer_document_question(doc_id: str, question: str, chat_history: str = "") -> str:
    """
    Executes a RAG query for follow-up questions:
    1. Retrieves top relevant chunks from Qdrant with page numbers.
    2. Constructs grounded prompt.
    3. Calls Groq LLM to answer in plain, jargon-free English.
    """
    relevant_chunks = vector_service.search_relevant_chunks(doc_id=doc_id, query=question, top_k=4)

    if not relevant_chunks:
        context_str = "No specific clauses found in the document matching this question."
    else:
        context_parts = []
        for c in relevant_chunks:
            page_num = c.get("page_number", "Unknown")
            chunk_txt = c.get("text", "")
            context_parts.append(f"--- [From Page {page_num}] ---\n{chunk_txt}")
        context_str = "\n\n".join(context_parts)

    user_prompt = CHAT_RAG_PROMPT.format(
        retrieved_context=context_str,
        chat_history=chat_history or "No previous messages.",
        question=question
    )

    llm = get_llm(temperature=0.2)
    messages = [
        SystemMessage(content=SYSTEM_LEGAL_ANALYST_PROMPT),
        HumanMessage(content=user_prompt)
    ]

    try:
        response = llm.invoke(messages)
        return response.content
    except Exception as exc:
        return f"Unable to generate an answer at this time: {str(exc)}"
