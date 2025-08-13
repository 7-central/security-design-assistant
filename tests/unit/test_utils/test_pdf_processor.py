"""Unit tests for PDF processor module."""
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from src.utils.pdf_processor import (
    CorruptedPDFError,
    MissingDependencyError,
    PageContent,
    PageDimensions,
    PasswordProtectedPDFError,
    PDFMetadata,
    PDFProcessor,
    PDFProcessingError,
    PDFType,
)


class TestPDFProcessor:
    """Test cases for PDFProcessor class."""

    @pytest.fixture
    def pdf_processor(self):
        """Create PDFProcessor instance."""
        return PDFProcessor(dpi=300)

    @pytest.fixture
    def mock_pdf_reader(self):
        """Create mock PDF reader."""
        reader = MagicMock()
        reader.is_encrypted = False
        return reader

    def test_detect_pdf_type_genuine(self, pdf_processor, tmp_path):
        """Test detection of genuine PDF with text content."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4")

        with patch("pypdf.PdfReader") as mock_reader_class:
            # Setup mock reader
            mock_reader = MagicMock()
            mock_reader.is_encrypted = False

            # Create mock pages with text
            mock_page = MagicMock()
            mock_page.extract_text.return_value = "This is a test document with plenty of text content that should be detected as genuine PDF."
            mock_reader.pages = [mock_page, mock_page]

            mock_reader_class.return_value = mock_reader

            pdf_type = pdf_processor.detect_pdf_type(pdf_path)
            assert pdf_type == PDFType.GENUINE

    def test_detect_pdf_type_scanned(self, pdf_processor, tmp_path):
        """Test detection of scanned PDF with no text content."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4")

        with patch("pypdf.PdfReader") as mock_reader_class:
            # Setup mock reader
            mock_reader = MagicMock()
            mock_reader.is_encrypted = False

            # Create mock pages with minimal text
            mock_page = MagicMock()
            mock_page.extract_text.return_value = "  \n  "  # Just whitespace
            mock_reader.pages = [mock_page, mock_page]

            mock_reader_class.return_value = mock_reader

            pdf_type = pdf_processor.detect_pdf_type(pdf_path)
            assert pdf_type == PDFType.SCANNED

    def test_detect_pdf_type_password_protected(self, pdf_processor, tmp_path):
        """Test detection fails for password protected PDF."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4")

        with patch("pypdf.PdfReader") as mock_reader_class:
            # Setup mock reader
            mock_reader = MagicMock()
            mock_reader.is_encrypted = True

            mock_reader_class.return_value = mock_reader

            with pytest.raises(PasswordProtectedPDFError) as exc_info:
                pdf_processor.detect_pdf_type(pdf_path)

            assert "password protected" in str(exc_info.value)

    def test_detect_pdf_type_corrupted(self, pdf_processor, tmp_path):
        """Test detection fails for corrupted PDF."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"Not a PDF file")

        with patch("pypdf.PdfReader") as mock_reader_class:
            import pypdf.errors
            mock_reader_class.side_effect = pypdf.errors.PdfReadError("Invalid PDF")

            with pytest.raises(CorruptedPDFError) as exc_info:
                pdf_processor.detect_pdf_type(pdf_path)

            assert "corrupted" in str(exc_info.value)

    def test_detect_pdf_type_edge_case_exact_threshold(self, pdf_processor, tmp_path):
        """Test detection with text exactly at threshold."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4")

        with patch("pypdf.PdfReader") as mock_reader_class:
            mock_reader = MagicMock()
            mock_reader.is_encrypted = False
            
            # Create text exactly at 50 character threshold
            mock_page = MagicMock()
            mock_page.extract_text.return_value = "a" * 50  # Exactly 50 characters
            mock_reader.pages = [mock_page]
            
            mock_reader_class.return_value = mock_reader
            
            pdf_type = pdf_processor.detect_pdf_type(pdf_path)
            assert pdf_type == PDFType.SCANNED  # Should be scanned as it's not > 50

    def test_detect_pdf_type_multi_page_mixed_content(self, pdf_processor, tmp_path):
        """Test detection with mixed content across pages."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4")

        with patch("pypdf.PdfReader") as mock_reader_class:
            mock_reader = MagicMock()
            mock_reader.is_encrypted = False
            
            # First page: no text, second page: minimal text, third page: lots of text
            mock_pages = []
            page1 = MagicMock()
            page1.extract_text.return_value = ""
            mock_pages.append(page1)
            
            page2 = MagicMock()
            page2.extract_text.return_value = "small"
            mock_pages.append(page2)
            
            page3 = MagicMock()
            page3.extract_text.return_value = "This page has significant text content that should trigger genuine detection."
            mock_pages.append(page3)
            
            mock_reader.pages = mock_pages
            mock_reader_class.return_value = mock_reader
            
            pdf_type = pdf_processor.detect_pdf_type(pdf_path)
            assert pdf_type == PDFType.GENUINE  # Should detect as genuine due to page 3

    def test_detect_pdf_type_whitespace_only(self, pdf_processor, tmp_path):
        """Test detection with various whitespace characters."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4")

        with patch("pypdf.PdfReader") as mock_reader_class:
            mock_reader = MagicMock()
            mock_reader.is_encrypted = False
            
            mock_page = MagicMock()
            mock_page.extract_text.return_value = "  \n\t\r  \n  "  # Various whitespace
            mock_reader.pages = [mock_page]
            
            mock_reader_class.return_value = mock_reader
            
            pdf_type = pdf_processor.detect_pdf_type(pdf_path)
            assert pdf_type == PDFType.SCANNED

    def test_points_to_dimensions(self, pdf_processor):
        """Test conversion from points to millimeters."""
        # A4 size: 595 x 842 points should be ~210 x 297 mm
        dimensions = pdf_processor._points_to_dimensions(595, 842)

        assert dimensions.width == pytest.approx(210, rel=0.1)
        assert dimensions.height == pytest.approx(297, rel=0.1)
        assert isinstance(dimensions, PageDimensions)

    def test_points_to_dimensions_unusual_sizes(self, pdf_processor):
        """Test dimension conversion with unusual page sizes."""
        # Test unusually small dimensions (should log warning)
        with patch("src.utils.pdf_processor.logger.warning") as mock_warning:
            small_dims = pdf_processor._points_to_dimensions(100, 100)  # ~35mm x 35mm
            assert small_dims.width < 50
            mock_warning.assert_called()
            
        # Test unusually large dimensions (should log warning)
        with patch("src.utils.pdf_processor.logger.warning") as mock_warning:
            large_dims = pdf_processor._points_to_dimensions(15000, 15000)  # ~5291mm x 5291mm
            assert large_dims.width > 5000
            mock_warning.assert_called()

    def test_detect_standard_size(self, pdf_processor):
        """Test detection of standard paper sizes."""
        # Test A4 portrait
        a4_portrait = PageDimensions(210, 297)
        assert pdf_processor.detect_standard_size(a4_portrait) == "A4"
        
        # Test A4 landscape
        a4_landscape = PageDimensions(297, 210)
        assert pdf_processor.detect_standard_size(a4_landscape) == "A4 (landscape)"
        
        # Test A3 portrait
        a3_portrait = PageDimensions(297, 420)
        assert pdf_processor.detect_standard_size(a3_portrait) == "A3"
        
        # Test with tolerance (slightly off dimensions)
        a4_almost = PageDimensions(212, 295)  # Within 5mm tolerance
        assert pdf_processor.detect_standard_size(a4_almost) == "A4"
        
        # Test non-standard size
        custom = PageDimensions(250, 350)
        assert pdf_processor.detect_standard_size(custom) is None

    def test_extract_text_from_genuine_pdf(self, pdf_processor, tmp_path):
        """Test text extraction from genuine PDF."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4")

        with patch("pypdf.PdfReader") as mock_reader_class:
            # Setup mock reader
            mock_reader = MagicMock()

            # Create mock pages
            mock_pages = []
            for i in range(2):
                mock_page = MagicMock()
                mock_page.extract_text.return_value = f"Page {i+1} text content"

                # Mock mediabox for dimensions
                mock_mediabox = MagicMock()
                mock_mediabox.width = 595  # A4 width in points
                mock_mediabox.height = 842  # A4 height in points
                mock_page.mediabox = mock_mediabox

                mock_pages.append(mock_page)

            mock_reader.pages = mock_pages
            mock_reader_class.return_value = mock_reader

            pages = pdf_processor.extract_text_from_genuine_pdf(pdf_path)

            assert len(pages) == 2
            assert pages[0].page_num == 1
            assert pages[0].text == "Page 1 text content"
            assert pages[0].dimensions.width == pytest.approx(210, rel=0.1)
            assert pages[1].page_num == 2
            assert pages[1].text == "Page 2 text content"

    def test_extract_text_corrupted_pdf(self, pdf_processor, tmp_path):
        """Test text extraction fails for corrupted PDF."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"Not a PDF")

        with patch("pypdf.PdfReader") as mock_reader_class:
            import pypdf.errors
            mock_reader_class.side_effect = pypdf.errors.PdfReadError("Invalid PDF")

            with pytest.raises(CorruptedPDFError):
                pdf_processor.extract_text_from_genuine_pdf(pdf_path)

    def test_convert_scanned_pdf_to_images(self, pdf_processor, tmp_path):
        """Test conversion of scanned PDF to images."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4")

        # Create mock images
        mock_images = []
        for _ in range(2):
            mock_image = MagicMock(spec=Image.Image)
            # At 300 DPI: A4 is approximately 2480 x 3508 pixels
            mock_image.width = 2480
            mock_image.height = 3508
            mock_images.append(mock_image)

        # Mock both pypdf.PdfReader and convert_from_path
        with patch("pypdf.PdfReader") as mock_reader_class:
            # Setup mock reader for page count
            mock_reader = MagicMock()
            mock_reader.pages = [MagicMock(), MagicMock()]  # 2 pages
            mock_reader_class.return_value = mock_reader

            with patch("src.utils.pdf_processor.convert_from_path") as mock_convert:
                mock_convert.return_value = mock_images

                pages = pdf_processor.convert_scanned_pdf_to_images(pdf_path)

                assert len(pages) == 2
                assert pages[0].page_num == 1
                assert pages[0].image is not None
                assert pages[0].dimensions.width == pytest.approx(210, rel=1)  # A4 width
                assert pages[0].dimensions.height == pytest.approx(297, rel=1)  # A4 height

                # Verify convert was called with batch parameters
                mock_convert.assert_called_once_with(
                    str(pdf_path),
                    dpi=300,
                    first_page=1,
                    last_page=2
                )

    def test_convert_scanned_pdf_missing_poppler(self, pdf_processor, tmp_path):
        """Test conversion fails when poppler is missing."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4")

        with patch("pypdf.PdfReader") as mock_reader_class:
            # Setup mock reader for page count
            mock_reader = MagicMock()
            mock_reader.pages = [MagicMock()]
            mock_reader_class.return_value = mock_reader

            with patch("src.utils.pdf_processor.convert_from_path") as mock_convert:
                mock_convert.side_effect = ImportError("pdf2image not available")

                with pytest.raises(MissingDependencyError) as exc_info:
                    pdf_processor.convert_scanned_pdf_to_images(pdf_path)

                assert "poppler-utils" in str(exc_info.value)

    def test_convert_scanned_pdf_poppler_error(self, pdf_processor, tmp_path):
        """Test conversion fails with poppler error."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4")

        with patch("pypdf.PdfReader") as mock_reader_class:
            # Setup mock reader for page count
            mock_reader = MagicMock()
            mock_reader.pages = [MagicMock()]
            mock_reader_class.return_value = mock_reader

            with patch("src.utils.pdf_processor.convert_from_path") as mock_convert:
                mock_convert.side_effect = Exception("Unable to get page count. Is poppler installed?")

                with pytest.raises(MissingDependencyError) as exc_info:
                    pdf_processor.convert_scanned_pdf_to_images(pdf_path)

                assert "poppler-utils" in str(exc_info.value)

    def test_convert_scanned_pdf_batch_processing(self, pdf_processor, tmp_path):
        """Test batch processing for large PDFs."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4")
        
        # Create processor with small batch size
        small_batch_processor = PDFProcessor(dpi=300, max_pages_in_memory=2)
        
        # Create 5 mock pages (should process in 3 batches with batch size 2)
        mock_pages = [MagicMock() for _ in range(5)]
        
        with patch("pypdf.PdfReader") as mock_reader_class:
            mock_reader = MagicMock()
            mock_reader.pages = mock_pages
            mock_reader_class.return_value = mock_reader
            
            with patch("src.utils.pdf_processor.convert_from_path") as mock_convert:
                # Mock different batches
                def batch_side_effect(*args, **kwargs):
                    first_page = kwargs.get('first_page', 1)
                    last_page = kwargs.get('last_page', 1)
                    batch_size = last_page - first_page + 1
                    
                    images = []
                    for _ in range(batch_size):
                        img = MagicMock(spec=Image.Image)
                        img.width = 2480
                        img.height = 3508
                        images.append(img)
                    return images
                
                mock_convert.side_effect = batch_side_effect
                
                pages = small_batch_processor.convert_scanned_pdf_to_images(pdf_path)
                
                # Should have processed all 5 pages
                assert len(pages) == 5
                # Check batches were called correctly
                assert mock_convert.call_count == 3  # 3 batches: [1,2], [3,4], [5]

    def test_convert_scanned_pdf_general_error(self, pdf_processor, tmp_path):
        """Test conversion with general error (not poppler-related)."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4")

        with patch("pypdf.PdfReader") as mock_reader_class:
            mock_reader = MagicMock()
            mock_reader.pages = [MagicMock()]
            mock_reader_class.return_value = mock_reader

            with patch("src.utils.pdf_processor.convert_from_path") as mock_convert:
                mock_convert.side_effect = Exception("Some other error")

                with pytest.raises(PDFProcessingError) as exc_info:
                    pdf_processor.convert_scanned_pdf_to_images(pdf_path)

                assert "Failed to convert PDF" in str(exc_info.value)
                assert "poppler" not in str(exc_info.value)

    def test_extract_metadata(self, pdf_processor, tmp_path):
        """Test metadata extraction from PDF."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4")

        with patch.object(pdf_processor, "detect_pdf_type") as mock_detect:
            mock_detect.return_value = PDFType.GENUINE

            with patch("pypdf.PdfReader") as mock_reader_class:
                # Setup mock reader
                mock_reader = MagicMock()

                # Create mock pages with different dimensions
                mock_pages = []
                dimensions = [(595, 842), (842, 1191)]  # A4 and A3

                for width, height in dimensions:
                    mock_page = MagicMock()
                    mock_mediabox = MagicMock()
                    mock_mediabox.width = width
                    mock_mediabox.height = height
                    mock_page.mediabox = mock_mediabox
                    mock_pages.append(mock_page)

                mock_reader.pages = mock_pages
                mock_reader_class.return_value = mock_reader

                metadata = pdf_processor.extract_metadata(pdf_path)

                assert metadata.pdf_type == PDFType.GENUINE
                assert metadata.total_pages == 2
                assert len(metadata.dimensions) == 2
                assert metadata.dimensions[0].width == pytest.approx(210, rel=0.1)  # A4
                assert metadata.dimensions[1].width == pytest.approx(297, rel=0.1)  # A3

    def test_process_pdf_genuine(self, pdf_processor, tmp_path):
        """Test processing of genuine PDF."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4")

        mock_metadata = PDFMetadata(
            pdf_type=PDFType.GENUINE,
            total_pages=1,
            dimensions=[PageDimensions(210, 297)]
        )

        mock_pages = [
            PageContent(
                page_num=1,
                text="Test content",
                dimensions=PageDimensions(210, 297)
            )
        ]

        with patch.object(pdf_processor, "extract_metadata") as mock_extract_meta:
            mock_extract_meta.return_value = mock_metadata

            with patch.object(pdf_processor, "extract_text_from_genuine_pdf") as mock_extract_text:
                mock_extract_text.return_value = mock_pages

                pages, metadata = pdf_processor.process_pdf(pdf_path)

                assert len(pages) == 1
                assert pages[0].text == "Test content"
                assert metadata.pdf_type == PDFType.GENUINE

    def test_process_pdf_scanned(self, pdf_processor, tmp_path):
        """Test processing of scanned PDF."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4")

        mock_metadata = PDFMetadata(
            pdf_type=PDFType.SCANNED,
            total_pages=1,
            dimensions=[PageDimensions(210, 297)]
        )

        mock_image = MagicMock(spec=Image.Image)
        mock_pages = [
            PageContent(
                page_num=1,
                image=mock_image,
                dimensions=PageDimensions(210, 297)
            )
        ]

        with patch.object(pdf_processor, "extract_metadata") as mock_extract_meta:
            mock_extract_meta.return_value = mock_metadata

            with patch.object(pdf_processor, "convert_scanned_pdf_to_images") as mock_convert:
                mock_convert.return_value = mock_pages

                pages, metadata = pdf_processor.process_pdf(pdf_path)

                assert len(pages) == 1
                assert pages[0].image is not None
                assert metadata.pdf_type == PDFType.SCANNED


class TestPageDimensions:
    """Test cases for PageDimensions class."""

    def test_to_dict(self):
        """Test conversion to dictionary."""
        dimensions = PageDimensions(width=210.5, height=297.0)
        result = dimensions.to_dict()

        assert result == {"width": 210.5, "height": 297.0}
        assert isinstance(result, dict)


class TestPageContent:
    """Test cases for PageContent class."""

    def test_to_dict_with_text(self):
        """Test conversion to dictionary with text content."""
        content = PageContent(
            page_num=1,
            text="Sample text",
            dimensions=PageDimensions(210, 297)
        )
        result = content.to_dict()

        assert result["page"] == 1
        assert result["text"] == "Sample text"
        assert result["dimensions"] == {"width": 210, "height": 297}
        assert "image" not in result

    def test_to_dict_without_text(self):
        """Test conversion to dictionary without text (scanned page)."""
        content = PageContent(
            page_num=2,
            image=MagicMock(),
            dimensions=PageDimensions(420, 594)
        )
        result = content.to_dict()

        assert result["page"] == 2
        assert "text" not in result
        assert result["dimensions"] == {"width": 420, "height": 594}


class TestPDFMetadata:
    """Test cases for PDFMetadata class."""

    def test_to_dict(self):
        """Test conversion to dictionary."""
        metadata = PDFMetadata(
            pdf_type=PDFType.GENUINE,
            total_pages=3,
            dimensions=[
                PageDimensions(210, 297),
                PageDimensions(210, 297),
                PageDimensions(420, 594)
            ]
        )
        result = metadata.to_dict()

        assert result["type"] == "genuine"
        assert result["pages"] == 3
        assert len(result["dimensions"]) == 3
        assert result["dimensions"][0] == {"width": 210, "height": 297}
        assert result["dimensions"][2] == {"width": 420, "height": 594}


class TestPDFProcessorEdgeCases:
    """Additional edge case tests for PDFProcessor."""

    @pytest.fixture
    def pdf_processor(self):
        """Create PDFProcessor instance."""
        return PDFProcessor(dpi=300)

    def test_process_empty_pdf(self, pdf_processor, tmp_path):
        """Test processing PDF with no pages."""
        pdf_path = tmp_path / "empty.pdf"
        pdf_path.write_bytes(b"%PDF-1.4")

        with patch("pypdf.PdfReader") as mock_reader_class:
            mock_reader = MagicMock()
            mock_reader.is_encrypted = False
            mock_reader.pages = []  # Empty PDF
            mock_reader_class.return_value = mock_reader

            # Should still work but return empty metadata
            pdf_type = pdf_processor.detect_pdf_type(pdf_path)
            assert pdf_type == PDFType.SCANNED  # No text means scanned

    def test_process_single_page_pdf(self, pdf_processor, tmp_path):
        """Test processing single-page PDF."""
        pdf_path = tmp_path / "single.pdf"
        pdf_path.write_bytes(b"%PDF-1.4")

        with patch("pypdf.PdfReader") as mock_reader_class:
            mock_reader = MagicMock()
            mock_reader.is_encrypted = False
            
            mock_page = MagicMock()
            mock_page.extract_text.return_value = "Single page content with enough text"
            mock_reader.pages = [mock_page]  # Single page
            
            mock_reader_class.return_value = mock_reader
            
            pdf_type = pdf_processor.detect_pdf_type(pdf_path)
            assert pdf_type == PDFType.SCANNED  # Less than 50 chars total

    def test_extract_text_with_unicode(self, pdf_processor, tmp_path):
        """Test text extraction with Unicode characters."""
        pdf_path = tmp_path / "unicode.pdf"
        pdf_path.write_bytes(b"%PDF-1.4")

        with patch("pypdf.PdfReader") as mock_reader_class:
            mock_reader = MagicMock()
            
            mock_page = MagicMock()
            # Unicode text with various characters
            mock_page.extract_text.return_value = "Unicode test: 中文 العربية ñ € ® ™ 🚀"
            
            mock_mediabox = MagicMock()
            mock_mediabox.width = 595
            mock_mediabox.height = 842
            mock_page.mediabox = mock_mediabox
            
            mock_reader.pages = [mock_page]
            mock_reader_class.return_value = mock_reader
            
            pages = pdf_processor.extract_text_from_genuine_pdf(pdf_path)
            
            assert len(pages) == 1
            assert "中文" in pages[0].text
            assert "العربية" in pages[0].text
            assert "🚀" in pages[0].text

    def test_pathlib_path_handling(self, pdf_processor, tmp_path):
        """Test that Path objects are handled correctly."""
        from pathlib import Path
        
        pdf_path = Path(tmp_path) / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4")

        with patch("pypdf.PdfReader") as mock_reader_class:
            mock_reader = MagicMock()
            mock_reader.is_encrypted = False
            
            mock_page = MagicMock()
            mock_page.extract_text.return_value = "Test content " * 10
            mock_reader.pages = [mock_page]
            
            mock_reader_class.return_value = mock_reader
            
            # Pass as Path object (not string)
            pdf_type = pdf_processor.detect_pdf_type(pdf_path)
            assert pdf_type == PDFType.GENUINE

    def test_unexpected_error_handling(self, pdf_processor, tmp_path):
        """Test handling of unexpected errors during PDF processing."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4")

        with patch("pypdf.PdfReader") as mock_reader_class:
            # Simulate unexpected error
            mock_reader_class.side_effect = RuntimeError("Unexpected error")
            
            with pytest.raises(RuntimeError):
                pdf_processor.detect_pdf_type(pdf_path)
