"""PDF processing utilities for handling both genuine and scanned PDFs."""
import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, ClassVar

import pypdf
from pdf2image import convert_from_path
from PIL import Image

logger = logging.getLogger(__name__)


class PDFType(Enum):
    """PDF document type classification."""

    GENUINE = "genuine"
    SCANNED = "scanned"


@dataclass
class PageDimensions:
    """Page dimensions in millimeters."""

    width: float
    height: float

    def to_dict(self) -> dict[str, float]:
        """Convert to dictionary representation."""
        return {"width": self.width, "height": self.height}


@dataclass
class PageContent:
    """Content extracted from a PDF page."""

    page_num: int
    text: str | None = None
    image: Image.Image | None = None
    dimensions: PageDimensions | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        result = {"page": self.page_num}
        if self.text is not None:
            result["text"] = self.text
        if self.dimensions:
            result["dimensions"] = self.dimensions.to_dict()
        return result


@dataclass
class PDFMetadata:
    """PDF document metadata."""

    pdf_type: PDFType
    total_pages: int
    dimensions: list[PageDimensions]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "type": self.pdf_type.value,
            "pages": self.total_pages,
            "dimensions": [dim.to_dict() for dim in self.dimensions],
        }


class PDFProcessingError(Exception):
    """Base exception for PDF processing errors."""

    pass


class CorruptedPDFError(PDFProcessingError):
    """Raised when PDF file is corrupted."""

    pass


class PasswordProtectedPDFError(PDFProcessingError):
    """Raised when PDF is password protected."""

    pass


class MissingDependencyError(PDFProcessingError):
    """Raised when required system dependency is missing."""

    pass


class PDFProcessor:
    """Handles PDF processing for both genuine and scanned documents."""

    # Standard paper sizes in mm (portrait orientation)
    STANDARD_SIZES: ClassVar[dict[str, tuple[int, int]]] = {
        "A0": (841, 1189),
        "A1": (594, 841),
        "A2": (420, 594),
        "A3": (297, 420),
        "A4": (210, 297),
    }

    # Points to mm conversion factor
    POINTS_TO_MM = 0.352778

    def __init__(self, dpi: int = 300, max_pages_in_memory: int = 50):
        """Initialize PDF processor.

        Args:
            dpi: DPI for image conversion of scanned PDFs
            max_pages_in_memory: Maximum pages to process at once for memory efficiency
        """
        self.dpi = dpi
        self.max_pages_in_memory = max_pages_in_memory

    def detect_pdf_type(self, pdf_path: str | Path) -> PDFType:
        """Detect if PDF is genuine (with text) or scanned (images only).

        Args:
            pdf_path: Path to PDF file

        Returns:
            PDFType.GENUINE or PDFType.SCANNED

        Raises:
            CorruptedPDFError: If PDF is corrupted
            PasswordProtectedPDFError: If PDF is password protected
        """
        pdf_path = Path(pdf_path)

        try:
            with open(pdf_path, "rb") as pdf_file:
                reader = pypdf.PdfReader(pdf_file)

                # Check if encrypted
                if reader.is_encrypted:
                    raise PasswordProtectedPDFError(f"PDF file '{pdf_path}' is password protected")

                # Check first few pages for text content
                pages_to_check = min(3, len(reader.pages))
                total_text = ""

                for i in range(pages_to_check):
                    page = reader.pages[i]
                    text = page.extract_text()
                    if text:
                        total_text += text.strip()

                # If we found meaningful text, it's a genuine PDF
                if len(total_text) > 50:  # Arbitrary threshold for meaningful text
                    return PDFType.GENUINE
                else:
                    return PDFType.SCANNED

        except pypdf.errors.PdfReadError as e:
            logger.error(f"Failed to read PDF file: {e}")
            raise CorruptedPDFError(f"PDF file '{pdf_path}' is corrupted or invalid") from e
        except Exception as e:
            logger.error(f"Unexpected error detecting PDF type: {e}")
            raise

    def _points_to_dimensions(self, width_pt: float, height_pt: float) -> PageDimensions:
        """Convert dimensions from points to millimeters.

        Args:
            width_pt: Width in points
            height_pt: Height in points

        Returns:
            PageDimensions in millimeters
        """
        width_mm = round(width_pt * self.POINTS_TO_MM, 2)
        height_mm = round(height_pt * self.POINTS_TO_MM, 2)

        # Validate reasonable dimensions (min 50mm, max 5000mm)
        if width_mm < 50 or height_mm < 50:
            logger.warning(f"Unusually small page dimensions detected: {width_mm}x{height_mm}mm")
        elif width_mm > 5000 or height_mm > 5000:
            logger.warning(f"Unusually large page dimensions detected: {width_mm}x{height_mm}mm")

        return PageDimensions(width=width_mm, height=height_mm)

    def detect_standard_size(self, dimensions: PageDimensions) -> str | None:
        """Detect if dimensions match a standard paper size.

        Args:
            dimensions: Page dimensions in millimeters

        Returns:
            Standard size name (e.g., "A4") or None if non-standard
        """
        tolerance = 5  # mm tolerance for matching

        # Check both portrait and landscape orientations
        for size_name, (std_width, std_height) in self.STANDARD_SIZES.items():
            # Portrait orientation
            if abs(dimensions.width - std_width) <= tolerance and abs(dimensions.height - std_height) <= tolerance:
                return size_name
            # Landscape orientation
            if abs(dimensions.width - std_height) <= tolerance and abs(dimensions.height - std_width) <= tolerance:
                return f"{size_name} (landscape)"

        return None

    def extract_text_from_genuine_pdf(self, pdf_path: str | Path) -> list[PageContent]:
        """Extract text and dimensions from genuine PDF.

        Args:
            pdf_path: Path to PDF file

        Returns:
            List of PageContent with text and dimensions

        Raises:
            CorruptedPDFError: If PDF is corrupted
        """
        pdf_path = Path(pdf_path)
        pages = []

        try:
            with open(pdf_path, "rb") as pdf_file:
                reader = pypdf.PdfReader(pdf_file)

                for page_num, page in enumerate(reader.pages, 1):
                    # Extract text
                    text = page.extract_text()

                    # Get page dimensions
                    mediabox = page.mediabox
                    width_pt = float(mediabox.width)
                    height_pt = float(mediabox.height)
                    dimensions = self._points_to_dimensions(width_pt, height_pt)

                    pages.append(PageContent(page_num=page_num, text=text, dimensions=dimensions))

                    logger.info(f"Extracted text from page {page_num}, dimensions: {dimensions}")

            return pages

        except pypdf.errors.PdfReadError as e:
            logger.error(f"Failed to extract text from PDF: {e}")
            raise CorruptedPDFError(f"PDF file '{pdf_path}' is corrupted or invalid") from e
        except Exception as e:
            logger.error(f"Unexpected error extracting text: {e}")
            raise

    def convert_scanned_pdf_to_images(self, pdf_path: str | Path) -> list[PageContent]:
        """Convert scanned PDF pages to PNG images.

        Args:
            pdf_path: Path to PDF file

        Returns:
            List of PageContent with images and dimensions

        Raises:
            MissingDependencyError: If poppler-utils is not installed
            PDFProcessingError: If conversion fails
        """
        pdf_path = Path(pdf_path)
        pages = []

        try:
            # Get total page count first
            with open(pdf_path, "rb") as pdf_file:
                reader = pypdf.PdfReader(pdf_file)
                total_pages = len(reader.pages)

            # Process in batches for memory efficiency
            for batch_start in range(0, total_pages, self.max_pages_in_memory):
                batch_end = min(batch_start + self.max_pages_in_memory, total_pages)

                # Convert batch of pages
                images = convert_from_path(
                    str(pdf_path),
                    dpi=self.dpi,
                    first_page=batch_start + 1,  # pdf2image uses 1-based indexing
                    last_page=batch_end,
                )

                for idx, image in enumerate(images):
                    page_num = batch_start + idx + 1
                    # Calculate dimensions in mm
                    # At 300 DPI: 1 inch = 25.4 mm = 300 pixels
                    pixels_per_mm = self.dpi / 25.4
                    width_mm = image.width / pixels_per_mm
                    height_mm = image.height / pixels_per_mm
                    dimensions = PageDimensions(width=round(width_mm, 2), height=round(height_mm, 2))

                    pages.append(PageContent(page_num=page_num, image=image, dimensions=dimensions))

                    logger.info(f"Converted page {page_num} to image, dimensions: {dimensions}")

                # Clear batch from memory
                del images

            return pages

        except ImportError as e:
            logger.error(f"pdf2image import error: {e}")
            raise MissingDependencyError(
                "pdf2image is not installed or poppler-utils is missing. "
                "Please install poppler-utils system package."
            ) from e
        except Exception as e:
            if "poppler" in str(e).lower():
                raise MissingDependencyError(
                    "poppler-utils is not installed. Please install it using your system package manager."
                ) from None
            logger.error(f"Failed to convert PDF to images: {e}")
            raise PDFProcessingError(f"Failed to convert PDF '{pdf_path}' to images") from e

    def extract_metadata(self, pdf_path: str | Path) -> PDFMetadata:
        """Extract metadata from PDF file.

        Args:
            pdf_path: Path to PDF file

        Returns:
            PDFMetadata with type, page count, and dimensions

        Raises:
            CorruptedPDFError: If PDF is corrupted
            PasswordProtectedPDFError: If PDF is password protected
        """
        pdf_path = Path(pdf_path)

        # Detect PDF type
        pdf_type = self.detect_pdf_type(pdf_path)

        try:
            with open(pdf_path, "rb") as pdf_file:
                reader = pypdf.PdfReader(pdf_file)
                total_pages = len(reader.pages)

                # Extract dimensions for each page
                dimensions = []
                standard_sizes = []
                for page_num, page in enumerate(reader.pages, 1):
                    mediabox = page.mediabox
                    width_pt = float(mediabox.width)
                    height_pt = float(mediabox.height)
                    page_dims = self._points_to_dimensions(width_pt, height_pt)
                    dimensions.append(page_dims)

                    # Detect standard size
                    std_size = self.detect_standard_size(page_dims)
                    if std_size:
                        standard_sizes.append(f"Page {page_num}: {std_size}")

                metadata = PDFMetadata(pdf_type=pdf_type, total_pages=total_pages, dimensions=dimensions)

                logger.info(f"PDF metadata: {metadata.to_dict()}")
                if standard_sizes:
                    logger.info(f"Detected standard sizes: {', '.join(standard_sizes)}")
                return metadata

        except pypdf.errors.PdfReadError as e:
            logger.error(f"Failed to extract metadata from PDF: {e}")
            raise CorruptedPDFError(f"PDF file '{pdf_path}' is corrupted or invalid") from e
        except Exception as e:
            logger.error(f"Unexpected error extracting metadata: {e}")
            raise

    def process_pdf(self, pdf_path: str | Path) -> tuple[list[PageContent], PDFMetadata]:
        """Process PDF file and extract content based on type.

        Args:
            pdf_path: Path to PDF file

        Returns:
            Tuple of (pages, metadata)

        Raises:
            Various PDF processing errors
        """
        pdf_path = Path(pdf_path)

        # Extract metadata first
        metadata = self.extract_metadata(pdf_path)

        # Process based on type
        if metadata.pdf_type == PDFType.GENUINE:
            pages = self.extract_text_from_genuine_pdf(pdf_path)
        else:
            pages = self.convert_scanned_pdf_to_images(pdf_path)

        return pages, metadata
