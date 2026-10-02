# app/services/pdf_service.py
"""
PDF Processing Service for ClauseGuard.

Production Responsibilities:
1. Validation: Inspect PDF magic bytes (%PDF-), encryption, and page counts.
2. Extraction: Extract text page-by-page with metadata (crucial for legal citation in RAG).
3. Text Sanitization: Clean noisy characters, normalize whitespace, fix broken hyphenated line breaks.
4. Scanned PDF Detection: Detect image-only/scanned documents where selectable text is missing.
"""

import re
import fitz  # PyMuPDF


class PDFProcessingError(Exception):
    """Custom exception raised when PDF extraction or validation fails."""
    pass


def validate_pdf_bytes(file_bytes: bytes, max_size_mb: int = 10) -> tuple[bool, str]:
    """
    Validates PDF file integrity, size, and header.

    Args:
        file_bytes: Raw binary content of the uploaded file.
        max_size_mb: Maximum allowed file size in Megabytes.

    Returns:
        tuple[bool, str]: (is_valid, error_message). If valid, error_message is empty.
    """
    # 1. Check file size
    size_in_mb = len(file_bytes) / (1024 * 1024)
    if size_in_mb > max_size_mb:
        return False, f"File size ({size_in_mb:.1f} MB) exceeds maximum limit of {max_size_mb} MB."

    if len(file_bytes) == 0:
        return False, "The uploaded file is completely empty."

    # 2. Check Magic Bytes (%PDF-)
    # A genuine PDF file always starts with the bytes %PDF-
    if not file_bytes.startswith(b"%PDF-"):
        return False, "Invalid file format. File does not start with standard PDF signature."

    # 3. Check readability and encryption with PyMuPDF
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
    except Exception as exc:
        return False, f"Could not read PDF structure: {str(exc)}"

    if doc.is_encrypted:
        doc.close()
        return False, "PDF is password protected or encrypted. Please remove password and re-upload."

    if doc.page_count == 0:
        doc.close()
        return False, "PDF contains zero pages."

    doc.close()
    return True, ""


def clean_text(raw_text: str) -> str:
    """
    Normalizes extracted raw text for LLM token efficiency and clean regex matching.

    Operations:
    - Normalizes unicode quotation marks and dashes.
    - Fixes hyphenated word wraps at line ends (e.g., 'termi-\nnation' -> 'termination').
    - Collapses excessive newlines and multiple spaces into clean paragraphs.
    """
    if not raw_text:
        return ""

    # Replace fancy curly quotes and unicode dashes with standard ascii equivalents
    text = raw_text.replace("“", '"').replace("”", '"').replace("’", "'").replace("‘", "'")
    text = text.replace("—", "-").replace("–", "-")

    # Fix hyphenated words broken across lines: e.g. "employ-\nment" -> "employment"
    text = re.sub(r'(\w+)-\n(\w+)', r'\1\2', text)

    # Replace multiple horizontal spaces/tabs with a single space
    text = re.sub(r'[ \t]+', ' ', text)

    # Collapse more than two consecutive newlines into double newlines (paragraphs)
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()


def detect_scanned_pdf(pages_data: list[dict], threshold_chars_per_page: int = 50) -> bool:
    """
    Detects if the document is a scanned image or photo without an OCR text layer.

    If average text per page is below the threshold, standard text extraction
    will yield empty results, requiring OCR or user notification.
    """
    if not pages_data:
        return True

    total_chars = sum(p["char_count"] for p in pages_data)
    avg_chars = total_chars / len(pages_data)
    return avg_chars < threshold_chars_per_page


def extract_text_from_pdf_bytes(file_bytes: bytes, filename: str = "document.pdf") -> dict:
    """
    Extracts text page-by-page and aggregates full content with rich metadata.

    Args:
        file_bytes: Raw binary bytes of the PDF.
        filename: Original file name.

    Returns:
        dict: {
            "filename": str,
            "page_count": int,
            "full_text": str,
            "pages": list[dict],       # [{"page_number": 1, "text": ..., "word_count": ...}]
            "is_scanned": bool,
            "total_words": int,
            "total_chars": int
        }
    """
    is_valid, error_msg = validate_pdf_bytes(file_bytes)
    if not is_valid:
        raise PDFProcessingError(error_msg)

    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
    except Exception as exc:
        raise PDFProcessingError(f"Failed to parse PDF document: {str(exc)}")

    pages: list[dict] = []
    full_text_chunks: list[str] = []
    total_words = 0
    total_chars = 0

    for page_idx in range(doc.page_count):
        page = doc.load_page(page_idx)
        raw_page_text = page.get_text("text")
        cleaned_page_text = clean_text(raw_page_text)

        word_count = len(cleaned_page_text.split()) if cleaned_page_text else 0
        char_count = len(cleaned_page_text)

        pages.append({
            "page_number": page_idx + 1,  # 1-indexed for human readability
            "text": cleaned_page_text,
            "word_count": word_count,
            "char_count": char_count,
        })

        if cleaned_page_text:
            full_text_chunks.append(cleaned_page_text)
            total_words += word_count
            total_chars += char_count

    doc.close()

    is_scanned = detect_scanned_pdf(pages)
    aggregated_full_text = "\n\n".join(full_text_chunks)

    return {
        "filename": filename,
        "page_count": len(pages),
        "full_text": aggregated_full_text,
        "pages": pages,
        "is_scanned": is_scanned,
        "total_words": total_words,
        "total_chars": total_chars
    }
