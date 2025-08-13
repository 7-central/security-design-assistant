"""Unit tests for context type classifier."""
import pytest

from src.utils.validators import classify_context


class TestContextClassifier:
    """Test cases for context type classification."""
    
    def test_no_context_provided(self):
        """Test classifier returns None when no context is provided."""
        result = classify_context()
        assert result is None
    
    def test_text_context_string(self):
        """Test classification of text provided as string."""
        result = classify_context(context_text="Some specification text")
        assert result == {"type": "text", "format": "string"}
    
    def test_pdf_by_mime_type(self):
        """Test PDF detection by MIME type."""
        result = classify_context(
            context_file_content=b"fake content",
            mime_type="application/pdf"
        )
        assert result == {"type": "pdf", "format": "file"}
    
    def test_docx_by_mime_type(self):
        """Test DOCX detection by MIME type."""
        result = classify_context(
            context_file_content=b"fake content",
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        assert result == {"type": "docx", "format": "file"}
        
        # Also test legacy MIME type
        result = classify_context(
            context_file_content=b"fake content",
            mime_type="application/msword"
        )
        assert result == {"type": "docx", "format": "file"}
    
    def test_text_file_by_mime_type(self):
        """Test text file detection by MIME type."""
        result = classify_context(
            context_file_content=b"fake content",
            mime_type="text/plain"
        )
        assert result == {"type": "text", "format": "file"}
    
    def test_pdf_by_filename(self):
        """Test PDF detection by filename extension."""
        result = classify_context(
            context_file_content=b"fake content",
            filename="specifications.pdf"
        )
        assert result == {"type": "pdf", "format": "file"}
        
        # Test case insensitive
        result = classify_context(
            context_file_content=b"fake content",
            filename="SPECS.PDF"
        )
        assert result == {"type": "pdf", "format": "file"}
    
    def test_docx_by_filename(self):
        """Test DOCX detection by filename extension."""
        result = classify_context(
            context_file_content=b"fake content",
            filename="requirements.docx"
        )
        assert result == {"type": "docx", "format": "file"}
    
    def test_text_file_by_filename(self):
        """Test text file detection by filename extension."""
        result = classify_context(
            context_file_content=b"fake content",
            filename="notes.txt"
        )
        assert result == {"type": "text", "format": "file"}
        
        # Also test .text extension
        result = classify_context(
            context_file_content=b"fake content",
            filename="readme.text"
        )
        assert result == {"type": "text", "format": "file"}
    
    def test_pdf_by_content_signature(self):
        """Test PDF detection by file content signature."""
        pdf_content = b"%PDF-1.4 rest of content"
        result = classify_context(context_file_content=pdf_content)
        assert result == {"type": "pdf", "format": "file"}
    
    def test_docx_by_content_signature(self):
        """Test DOCX detection by ZIP/PK signature."""
        # DOCX files start with PK (ZIP signature)
        docx_content = b"PK\x03\x04 rest of content"
        result = classify_context(context_file_content=docx_content)
        assert result == {"type": "docx", "format": "file"}
    
    def test_default_to_text_for_unknown(self):
        """Test that unknown file types default to text."""
        result = classify_context(
            context_file_content=b"unknown content",
            filename="unknown.xyz"
        )
        assert result == {"type": "text", "format": "file"}
    
    def test_mime_type_takes_precedence(self):
        """Test that MIME type takes precedence over filename."""
        result = classify_context(
            context_file_content=b"content",
            mime_type="application/pdf",
            filename="document.txt"  # Conflicting extension
        )
        assert result == {"type": "pdf", "format": "file"}
    
    def test_short_content_defaults_to_text(self):
        """Test that very short content defaults to text."""
        result = classify_context(context_file_content=b"hi")
        assert result == {"type": "text", "format": "file"}
    
    def test_edge_cases(self):
        """Test various edge cases."""
        # Empty file content
        result = classify_context(context_file_content=b"")
        assert result == {"type": "text", "format": "file"}
        
        # None values for optional params
        result = classify_context(
            context_file_content=b"content",
            mime_type=None,
            filename=None
        )
        assert result == {"type": "text", "format": "file"}
        
        # Both file and text provided (text takes precedence)
        result = classify_context(
            context_file_content=b"file content",
            context_text="text content"
        )
        assert result == {"type": "text", "format": "string"}
    
    def test_mixed_case_mime_types(self):
        """Test case-insensitive MIME type detection."""
        test_cases = [
            ("APPLICATION/PDF", "pdf"),
            ("Application/Pdf", "pdf"),
            ("TEXT/PLAIN", "text"),
            ("Text/Plain", "text"),
        ]
        
        for mime_type, expected_type in test_cases:
            result = classify_context(
                context_file_content=b"content",
                mime_type=mime_type
            )
            assert result == {"type": expected_type, "format": "file"}
    
    def test_partial_mime_type_matching(self):
        """Test that partial MIME type matching works."""
        # Test various PDF MIME type variations
        pdf_mime_types = [
            "application/pdf",
            "application/x-pdf",
            "application/acrobat",
        ]
        
        for mime_type in pdf_mime_types:
            if "pdf" in mime_type.lower():
                result = classify_context(
                    context_file_content=b"content",
                    mime_type=mime_type
                )
                assert result == {"type": "pdf", "format": "file"}
    
    def test_corrupted_pdf_signature(self):
        """Test handling of corrupted PDF signatures."""
        # Partial PDF signature
        partial_pdf = b"%PDF"  # Missing version
        result = classify_context(context_file_content=partial_pdf)
        assert result == {"type": "pdf", "format": "file"}
        
        # Almost PDF signature
        almost_pdf = b"%PD"  # Too short
        result = classify_context(context_file_content=almost_pdf)
        assert result == {"type": "text", "format": "file"}
    
    def test_filename_with_path(self):
        """Test filename extraction works with full paths."""
        test_cases = [
            ("/home/user/documents/spec.pdf", "pdf"),
            ("C:\\Users\\Documents\\requirements.docx", "docx"),
            ("../relative/path/notes.txt", "text"),
        ]
        
        for filepath, expected_type in test_cases:
            result = classify_context(
                context_file_content=b"content",
                filename=filepath
            )
            assert result == {"type": expected_type, "format": "file"}
    
    def test_unicode_filenames(self):
        """Test Unicode characters in filenames."""
        unicode_files = [
            ("文档.pdf", "pdf"),
            ("документ.docx", "docx"),
            ("αρχείο.txt", "text"),
        ]
        
        for filename, expected_type in unicode_files:
            result = classify_context(
                context_file_content=b"content",
                filename=filename
            )
            assert result == {"type": expected_type, "format": "file"}
    
    def test_binary_content_types(self):
        """Test various binary content signatures."""
        # ZIP file that's not DOCX
        plain_zip = b"PK\x03\x04\x14\x00"  # Standard ZIP
        result = classify_context(context_file_content=plain_zip)
        # Should still classify as DOCX since we can't distinguish
        assert result == {"type": "docx", "format": "file"}
        
        # Executable file signature
        exe_content = b"MZ\x90\x00"  # DOS/Windows executable
        result = classify_context(context_file_content=exe_content)
        assert result == {"type": "text", "format": "file"}  # Defaults to text
    
    def test_priority_order(self):
        """Test the priority order: text string > MIME type > filename > content."""
        # All provided, text string should win
        result = classify_context(
            context_text="text",
            context_file_content=b"%PDF-1.4",
            mime_type="application/msword",
            filename="file.txt"
        )
        assert result == {"type": "text", "format": "string"}
        
        # No text string, MIME type should win
        result = classify_context(
            context_file_content=b"%PDF-1.4",
            mime_type="application/msword",
            filename="file.txt"
        )
        assert result == {"type": "docx", "format": "file"}
        
        # No text or MIME, filename should win
        result = classify_context(
            context_file_content=b"%PDF-1.4",
            filename="file.txt"
        )
        assert result == {"type": "text", "format": "file"}
        
        # Only content signature
        result = classify_context(
            context_file_content=b"%PDF-1.4"
        )
        assert result == {"type": "pdf", "format": "file"}
    
    def test_empty_string_vs_none(self):
        """Test distinction between empty strings and None values."""
        # Empty text string should still return text type
        result = classify_context(context_text="")
        assert result is None  # Empty string is falsy
        
        # Empty filename should be ignored
        result = classify_context(
            context_file_content=b"content",
            filename=""
        )
        assert result == {"type": "text", "format": "file"}
        
        # Empty MIME type should be ignored
        result = classify_context(
            context_file_content=b"content",
            mime_type=""
        )
        assert result == {"type": "text", "format": "file"}