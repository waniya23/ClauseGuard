# tests/test_basic.py
"""
Automated Unit and Integration Tests for ClauseGuard.
"""

from fastapi.testclient import TestClient
from app.main import app
from app.services.risk_service import (
    detect_document_type,
    analyze_document_risk,
    get_advice
)
from app.services.pdf_service import (
    clean_text,
    detect_scanned_pdf,
    is_image_bytes
)

client = TestClient(app)


def test_health_check_endpoint():
    """Verify that the /health endpoint responds with status ok/healthy."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "app" in data


def test_root_serves_html():
    """Verify that root / serves the frontend index.html."""
    response = client.get("/")
    assert response.status_code == 200
    assert "ClauseGuard" in response.text


def test_document_type_detection():
    """Verify keyword-based document type detection."""
    rental_text = "The tenant shall pay monthly rent to the landlord for the premises and security deposit."
    assert detect_document_type(rental_text) == "rental"

    employment_text = "The employee will receive monthly salary, undergo probation, and must give notice period before resignation."
    assert detect_document_type(employment_text) == "employment"


def test_risk_scoring_detection():
    """Verify that risky clauses are properly flagged."""
    risky_contract = """
    This agreement may be terminated immediately without notice.
    The security deposit is strictly non-refundable under any circumstance.
    The employee shall not compete with the company for 2 years.
    """
    analysis = analyze_document_risk(risky_contract)
    assert analysis["score"] > 0
    assert analysis["total_issues"] >= 2
    assert len(analysis["warnings"]) >= 2

    # Check that non-compete warning was flagged
    clauses = [w["clause"] for w in analysis["warnings"]]
    assert "unilateral_termination" in clauses or "non_refundable_deposit" in clauses


def test_clean_text_normalizer():
    """Verify text cleaning and broken hyphenation fix."""
    messy_text = "This is an employ-\nment contract with “curly quotes” and    extra spaces."
    cleaned = clean_text(messy_text)
    assert "employment" in cleaned
    assert '"curly quotes"' in cleaned
    assert "   " not in cleaned


def test_image_bytes_detector():
    """Verify image magic bytes identification."""
    jpeg_header = b"\xff\xd8\xff\xe0"
    png_header = b"\x89PNG\r\n\x1a\n"
    pdf_header = b"%PDF-1.4"

    assert is_image_bytes(jpeg_header) is True
    assert is_image_bytes(png_header) is True
    assert is_image_bytes(pdf_header) is False


def test_chat_validation_endpoint():
    """Verify that chat endpoint properly validates empty questions."""
    response = client.post("/api/chat/ask", json={"doc_id": "test", "question": "   "})
    assert response.status_code == 400
