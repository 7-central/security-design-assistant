import io
from typing import TypedDict

import pypdf


def validate_pdf_file(file_content: bytes) -> tuple[bool, str]:
    """
    Validate that the file content is a valid PDF.

    Args:
        file_content: The file content as bytes

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not file_content:
        return False, "File is empty"

    try:
        pdf_reader = pypdf.PdfReader(io.BytesIO(file_content))
        if len(pdf_reader.pages) == 0:
            return False, "PDF has no pages"
        return True, ""
    except pypdf.errors.PdfReadError:
        return False, "Invalid PDF file"
    except Exception as e:
        return False, f"Error reading PDF: {e!s}"


def validate_file_size(file_size: int, max_size_bytes: int) -> tuple[bool, str]:
    """
    Validate that the file size is within limits.

    Args:
        file_size: Size of the file in bytes
        max_size_bytes: Maximum allowed size in bytes

    Returns:
        Tuple of (is_valid, error_message)
    """
    if file_size <= 0:
        return False, "File is empty"

    if file_size > max_size_bytes:
        max_size_mb = max_size_bytes // (1024 * 1024)
        return False, f"File size exceeds {max_size_mb}MB limit"

    return True, ""


class ContextClassification(TypedDict):
    type: str  # "docx" | "pdf" | "text"
    format: str  # "file" | "string"


def classify_context(
    context_file_content: bytes | None = None,
    context_text: str | None = None,
    mime_type: str | None = None,
    filename: str | None = None
) -> ContextClassification | None:
    """
    Classify the type and format of context input.

    Args:
        context_file_content: File content as bytes (optional)
        context_text: Text content as string (optional)
        mime_type: MIME type of the file (optional)
        filename: Original filename (optional)

    Returns:
        Classification dict with type and format, or None if no context provided
    """
    # No context provided
    if context_file_content is None and not context_text:
        return None

    # Text context provided
    if context_text:
        return {"type": "text", "format": "string"}

    # File context provided
    if context_file_content is not None:
        # Try to detect type from MIME type first
        if mime_type:
            if "pdf" in mime_type.lower():
                return {"type": "pdf", "format": "file"}
            elif "wordprocessingml" in mime_type.lower() or "msword" in mime_type.lower():
                return {"type": "docx", "format": "file"}
            elif "text" in mime_type.lower():
                return {"type": "text", "format": "file"}

        # Fallback to filename extension
        if filename:
            filename_lower = filename.lower()
            if filename_lower.endswith(".pdf"):
                return {"type": "pdf", "format": "file"}
            elif filename_lower.endswith(".docx"):
                return {"type": "docx", "format": "file"}
            elif filename_lower.endswith((".txt", ".text")):
                return {"type": "text", "format": "file"}

        # Try to detect by file content signatures
        if len(context_file_content) >= 4:
            # PDF signature
            if context_file_content[:4] == b"%PDF":
                return {"type": "pdf", "format": "file"}
            # DOCX signature (ZIP file starting with PK)
            elif context_file_content[:2] == b"PK":
                # Additional check for DOCX structure would go here
                # For now, assume DOCX if it's a ZIP
                return {"type": "docx", "format": "file"}

        # Default to text if cannot determine
        return {"type": "text", "format": "file"}

    return None
