# app/services/pdf_service.py
"""
PDF and Document Ingestion Service for ClauseGuard.

Production Responsibilities:
1. Multi-format support: Accepts native PDF, PNG, JPG, and JPEG.
2. Image to PDF Conversion: Converts single-image uploads into memory PDF streams.
3. Clean Extraction: Extracts digital text with hyphenation correction and page tracking.
4. Vision OCR Fallback: Uses Groq Vision (llama-3.2-11b-vision-preview) to transcribe scanned documents.
"""

import base64
import os
import re
import fitz  # PyMuPDF
from groq import Groq
from app.config import settings


class PDFProcessingError(Exception):
    """Custom exception raised when document extraction or validation fails."""
    pass


def is_image_bytes(file_bytes: bytes) -> bool:
    """Detects whether binary payload is a standard image (JPEG, PNG, WEBP)."""
    return (
        file_bytes.startswith(b"\xff\xd8\xff") or  # JPEG
        file_bytes.startswith(b"\x89PNG") or       # PNG
        file_bytes.startswith(b"RIFF")             # WEBP
    )


def convert_image_bytes_to_pdf_bytes(image_bytes: bytes) -> bytes:
    """Converts uploaded raw image bytes into a standardized single-page PDF in memory."""
    try:
        img_doc = fitz.open(stream=image_bytes)
        pdf_bytes = img_doc.convert_to_pdf()
        img_doc.close()
        return pdf_bytes
    except Exception as exc:
        raise PDFProcessingError(f"Could not convert uploaded image to document format: {str(exc)}")


def validate_document_bytes(file_bytes: bytes, max_size_mb: int = 10) -> tuple[bool, str, bytes]:
    """
    Validates file size, integrity, and normalizes images into PDF streams.

    Returns:
        tuple[bool, str, bytes]: (is_valid, error_message, normalized_pdf_bytes)
    """
    if len(file_bytes) == 0:
        return False, "The uploaded file is empty.", b""

    size_in_mb = len(file_bytes) / (1024 * 1024)
    if size_in_mb > max_size_mb:
        return False, f"File size ({size_in_mb:.1f} MB) exceeds maximum limit of {max_size_mb} MB.", b""

    # Handle image bytes by converting to in-memory PDF
    if is_image_bytes(file_bytes):
        try:
            converted_pdf = convert_image_bytes_to_pdf_bytes(file_bytes)
            return True, "", converted_pdf
        except Exception as exc:
            return False, str(exc), b""

    # Validate PDF signature
    if not file_bytes.startswith(b"%PDF-"):
        return False, "Unsupported file format. Please upload a PDF, PNG, JPG, or JPEG file.", b""

    # Check readability and encryption
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
    except Exception as exc:
        return False, f"Could not read PDF structure: {str(exc)}", b""

    if doc.is_encrypted:
        doc.close()
        return False, "PDF is password protected. Please remove password and re-upload.", b""

    if doc.page_count == 0:
        doc.close()
        return False, "PDF contains zero pages.", b""

    doc.close()
    return True, "", file_bytes


def clean_text(raw_text: str) -> str:
    """
    Normalizes text, removes unicode quotation marks, and fixes hyphenated word wraps.
    """
    if not raw_text:
        return ""

    text = raw_text.replace("“", '"').replace("”", '"').replace("’", "'").replace("‘", "'")
    text = text.replace("—", "-").replace("–", "-")

    # Fix broken hyphenated words: e.g. "employ-\nment" -> "employment"
    text = re.sub(r'(\w+)-\n(\w+)', r'\1\2', text)

    # Normalize horizontal whitespace
    text = re.sub(r'[ \t]+', ' ', text)

    # Collapse excessive newlines
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()


def detect_scanned_pdf(pages_data: list[dict], threshold_chars_per_page: int = 50) -> bool:
    """
    Returns True if average characters per page is below threshold (scanned image or photo).
    """
    if not pages_data:
        return True

    total_chars = sum(p["char_count"] for p in pages_data)
    avg_chars = total_chars / len(pages_data)
    return avg_chars < threshold_chars_per_page


def ocr_page_image_with_groq_vision(image_bytes: bytes) -> str:
    """
    Uses Groq's Vision LLM (llama-3.2-11b-vision-preview) to transcribe scanned document pages.
    Free, fast, and does not require local C++ tesseract installation.
    """
    if not settings.GROQ_API_KEY:
        return ""

    try:
        client = Groq(api_key=settings.GROQ_API_KEY)
        base64_image = base64.b64encode(image_bytes).decode("utf-8")

        response = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Transcribe all visible text from this contract or legal document image verbatim. "
                                "Preserve the original wording, clauses, and structure. "
                                "Return ONLY the transcribed text. Do not add preamble, greetings, or commentary."
                            )
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            model="llama-3.2-11b-vision-preview",
            temperature=0.1
        )
        return response.choices[0].message.content or ""
    except Exception as exc:
        print(f"[Warning] Groq Vision OCR failed: {exc}")
        return ""


def extract_text_from_document_bytes(file_bytes: bytes, filename: str = "document.pdf") -> dict:
    """
    Extracts text page-by-page. If pages have no digital text layer, triggers Groq Vision OCR.
    """
    is_valid, error_msg, normalized_pdf_bytes = validate_document_bytes(file_bytes)
    if not is_valid:
        raise PDFProcessingError(error_msg)

    try:
        doc = fitz.open(stream=normalized_pdf_bytes, filetype="pdf")
    except Exception as exc:
        raise PDFProcessingError(f"Failed to parse document: {str(exc)}")

    pages: list[dict] = []
    full_text_chunks: list[str] = []
    total_words = 0
    total_chars = 0

    # 1. First pass: Digital text extraction
    for page_idx in range(doc.page_count):
        page = doc.load_page(page_idx)
        raw_text = page.get_text("text")
        cleaned = clean_text(raw_text)

        word_count = len(cleaned.split()) if cleaned else 0
        char_count = len(cleaned)

        pages.append({
            "page_number": page_idx + 1,
            "text": cleaned,
            "word_count": word_count,
            "char_count": char_count,
            "_fitz_page_idx": page_idx
        })

    is_scanned = detect_scanned_pdf(pages)

    # 2. Second pass: If document is scanned/photo, use Groq Vision OCR
    if is_scanned:
        print("[Info] Scanned document or photo detected. Triggering Groq Vision OCR...")
        for p in pages:
            # Render page to high-res PNG image for Vision API
            page_obj = doc.load_page(p["_fitz_page_idx"])
            pixmap = page_obj.get_pixmap(dpi=150)
            page_png_bytes = pixmap.tobytes("png")

            ocr_transcription = ocr_page_image_with_groq_vision(page_png_bytes)
            cleaned_ocr = clean_text(ocr_transcription)

            if cleaned_ocr:
                p["text"] = cleaned_ocr
                p["word_count"] = len(cleaned_ocr.split())
                p["char_count"] = len(cleaned_ocr)

    # Cleanup temp internal reference and aggregate full text
    for p in pages:
        p.pop("_fitz_page_idx", None)
        if p["text"]:
            full_text_chunks.append(p["text"])
            total_words += p["word_count"]
            total_chars += p["char_count"]

    doc.close()

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
