import io
from pathlib import Path
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
    filename: str | None = None,
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


def validate_file_path(file_path: str | Path, must_exist: bool = False) -> tuple[bool, str]:
    """Validate a file path for security and correctness.

    Args:
        file_path: Path to validate
        must_exist: Whether the file must exist

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not file_path:
        return False, "File path is empty"

    try:
        path = Path(file_path)

        # Check for path traversal attempts
        if ".." in str(path):
            return False, "Path traversal detected"

        # Check for null bytes (security issue)
        if "\x00" in str(path):
            return False, "Null byte in path"

        # Convert to absolute path for further checks
        abs_path = path.absolute()

        # Check if path exists when required
        if must_exist and not abs_path.exists():
            return False, f"File does not exist: {path}"

        # Check if it's a file (not directory) when it exists
        if abs_path.exists() and abs_path.is_dir():
            return False, f"Path is a directory, not a file: {path}"

        return True, ""

    except Exception as e:
        return False, f"Invalid path: {e}"


def validate_file_extension(file_path: str | Path, allowed_extensions: list[str]) -> tuple[bool, str]:
    """Validate that a file has an allowed extension.

    Args:
        file_path: Path to the file
        allowed_extensions: List of allowed extensions (with or without dots)

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not file_path:
        return False, "File path is empty"

    if not allowed_extensions:
        return False, "No allowed extensions specified"

    try:
        path = Path(file_path)
        file_extension = path.suffix.lower()

        # Normalize allowed extensions (ensure they start with a dot)
        normalized_extensions = []
        for ext in allowed_extensions:
            ext = ext.lower()
            if not ext.startswith("."):
                ext = "." + ext
            normalized_extensions.append(ext)

        if not file_extension:
            return False, f"File has no extension: {path.name}"

        if file_extension not in normalized_extensions:
            return False, f"Invalid file extension '{file_extension}'. Allowed: {', '.join(normalized_extensions)}"

        return True, ""

    except Exception as e:
        return False, f"Error validating extension: {e}"


def validate_path_is_absolute(file_path: str | Path) -> tuple[bool, str]:
    """Validate that a path is absolute (not relative).

    Args:
        file_path: Path to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not file_path:
        return False, "File path is empty"

    try:
        path = Path(file_path)

        if not path.is_absolute():
            return False, f"Path is not absolute: {path}"

        return True, ""

    except Exception as e:
        return False, f"Error validating path: {e}"


def validate_path_no_special_chars(file_path: str | Path) -> tuple[bool, str]:
    """Validate that a path contains no potentially dangerous special characters.

    Args:
        file_path: Path to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not file_path:
        return False, "File path is empty"

    # Define dangerous characters
    dangerous_chars = ["<", ">", "|", "&", ";", "$", "`", "\n", "\r", "\x00"]

    path_str = str(file_path)

    for char in dangerous_chars:
        if char in path_str:
            return False, f"Path contains dangerous character: {char!r}"

    return True, ""
