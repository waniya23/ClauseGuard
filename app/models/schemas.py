# app/models/schemas.py

from pydantic import BaseModel, Field

class RiskWarning(BaseModel):
    clause_type: str = Field(
        description="Type of risky clause found"
    )
    warning_message: str = Field(
        description="Human readable warning"
    )
    risk_points: int = Field(
        description="Points this clause adds to risk score"
    )

class DocumentAnalysisResponse(BaseModel):
    """
    Schema for the response returned after a PDF document has been successfully analyzed.
    Provides risk level metrics, warnings list, a generated summary, and metadata.
    """
    doc_id: str = Field(
        ..., 
        description="Unique identifier of the analyzed document",
        examples=["doc_98765"]
    )
    filename: str = Field(
        ..., 
        description="The original name of the analyzed PDF file",
        examples=["employment_contract.pdf"]
    )
    risk_score: int = Field(
        ..., 
        description="Overall calculated risk score ranging from 0 to 100",
        ge=0,
        le=100,
        examples=[65]
    )
    risk_level: str = Field(
        ..., 
        description="Categorized risk level of the document (LOW/MEDIUM/HIGH)",
        examples=["HIGH"]
    )
    warnings: list[RiskWarning] = Field(
        ..., 
        description="List of specific risk warnings and clauses found in the document"
    )
    summary: str = Field(
        ..., 
        description="A brief executive summary of the document analysis",
        examples=["The document contains high-risk clauses including non-compete terms that exceed standard durations."]
    )
    processing_time_seconds: float = Field(
        ..., 
        description="Time taken to parse and analyze the document in seconds",
        examples=[3.72]
    )

class ChatRequest(BaseModel):
    """
    Schema representing a user's follow-up question regarding a specific document.
    """
    doc_id: str = Field(
        ..., 
        description="The unique identifier of the document to query",
        examples=["doc_98765"]
    )
    question: str = Field(
        ..., 
        description="The follow-up question about the document's content or clauses",
        examples=["Is there a non-compete clause in this contract?"]
    )

class ChatResponse(BaseModel):
    """
    Schema representing the AI answer response to a follow-up question.
    """
    answer: str = Field(
        ..., 
        description="The AI-generated answer based on the document's context",
        examples=["Yes, Section 8 contains a non-compete clause that restricts competition for 24 months post-employment."]
    )
    doc_id: str = Field(
        ..., 
        description="The unique identifier of the document associated with the answer",
        examples=["doc_98765"]
    )