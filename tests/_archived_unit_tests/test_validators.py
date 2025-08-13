


from src.utils.validators import (
    validate_file_extension,
    validate_file_path,
    validate_file_size,
    validate_path_is_absolute,
    validate_path_no_special_chars,
    validate_pdf_file,
)


class TestValidatePdfFile:
    def test_valid_pdf(self, sample_pdf_content: bytes) -> None:
        is_valid, error = validate_pdf_file(sample_pdf_content)
        assert is_valid is True
        assert error == ""

    def test_invalid_pdf(self, invalid_pdf_content: bytes) -> None:
        is_valid, error = validate_pdf_file(invalid_pdf_content)
        assert is_valid is False
        assert "Invalid PDF file" in error

    def test_empty_file(self) -> None:
        is_valid, error = validate_pdf_file(b"")
        assert is_valid is False
        assert error == "File is empty"

    def test_pdf_with_no_pages(self) -> None:
        # Minimal PDF with no pages
        no_pages_pdf = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [] /Count 0 >>
endobj
xref
0 3
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
trailer
<< /Size 3 /Root 1 0 R >>
startxref
115
%%EOF"""
        is_valid, error = validate_pdf_file(no_pages_pdf)
        assert is_valid is False
        assert "PDF has no pages" in error


class TestValidateFileSize:
    def test_valid_file_size(self) -> None:
        is_valid, error = validate_file_size(1024, 2048)
        assert is_valid is True
        assert error == ""

    def test_file_too_large(self) -> None:
        max_size = 100 * 1024 * 1024  # 100MB
        is_valid, error = validate_file_size(101 * 1024 * 1024, max_size)
        assert is_valid is False
        assert "File size exceeds 100MB limit" in error

    def test_empty_file(self) -> None:
        is_valid, error = validate_file_size(0, 1024)
        assert is_valid is False
        assert error == "File is empty"

    def test_negative_file_size(self) -> None:
        is_valid, error = validate_file_size(-1, 1024)
        assert is_valid is False
        assert error == "File is empty"

    def test_exact_max_size(self) -> None:
        max_size = 100 * 1024 * 1024
        is_valid, error = validate_file_size(max_size, max_size)
        assert is_valid is True
        assert error == ""


class TestValidateFilePath:
    """Test cases for file path validation."""

    def test_valid_absolute_path(self) -> None:
        """Test validation of valid absolute path."""
        is_valid, error = validate_file_path("/home/user/document.pdf")
        assert is_valid is True
        assert error == ""

    def test_valid_relative_path(self) -> None:
        """Test validation of valid relative path."""
        is_valid, error = validate_file_path("documents/file.pdf")
        assert is_valid is True
        assert error == ""

    def test_path_traversal_attack(self) -> None:
        """Test detection of path traversal attempts."""
        paths_with_traversal = [
            "../../../etc/passwd",
            "documents/../../../etc/passwd",
            "/home/../../../etc/passwd",
            "..\\..\\windows\\system32",
        ]

        for path in paths_with_traversal:
            is_valid, error = validate_file_path(path)
            assert is_valid is False
            assert "Path traversal detected" in error

    def test_null_byte_injection(self) -> None:
        """Test detection of null byte injection."""
        is_valid, error = validate_file_path("/home/user/file.pdf\x00.txt")
        assert is_valid is False
        assert "Null byte in path" in error

    def test_empty_path(self) -> None:
        """Test empty path validation."""
        is_valid, error = validate_file_path("")
        assert is_valid is False
        assert "File path is empty" in error

        is_valid, error = validate_file_path(None)
        assert is_valid is False
        assert "File path is empty" in error

    def test_existing_file_check(self, tmp_path) -> None:
        """Test validation with must_exist flag."""
        # Create a test file
        test_file = tmp_path / "test.pdf"
        test_file.write_text("test content")

        # Test with existing file
        is_valid, error = validate_file_path(str(test_file), must_exist=True)
        assert is_valid is True
        assert error == ""

        # Test with non-existing file
        non_existing = tmp_path / "nonexistent.pdf"
        is_valid, error = validate_file_path(str(non_existing), must_exist=True)
        assert is_valid is False
        assert "File does not exist" in error

    def test_directory_vs_file(self, tmp_path) -> None:
        """Test detection of directories vs files."""
        # Create a directory
        test_dir = tmp_path / "testdir"
        test_dir.mkdir()

        is_valid, error = validate_file_path(str(test_dir))
        assert is_valid is False
        assert "Path is a directory, not a file" in error

    def test_unicode_paths(self) -> None:
        """Test handling of Unicode characters in paths."""
        unicode_paths = [
            "/home/user/文档.pdf",
            "/home/user/документы.pdf",
            "/home/user/αρχείο.pdf",
        ]

        for path in unicode_paths:
            is_valid, error = validate_file_path(path)
            assert is_valid is True
            assert error == ""

    def test_path_with_spaces(self) -> None:
        """Test paths with spaces."""
        is_valid, error = validate_file_path("/home/user/my document.pdf")
        assert is_valid is True
        assert error == ""


class TestValidateFileExtension:
    """Test cases for file extension validation."""

    def test_valid_extensions(self) -> None:
        """Test validation with allowed extensions."""
        allowed = [".pdf", ".txt", ".docx"]

        test_cases = [
            ("document.pdf", True),
            ("file.txt", True),
            ("report.docx", True),
            ("image.jpg", False),
            ("script.py", False),
        ]

        for filename, should_be_valid in test_cases:
            is_valid, error = validate_file_extension(filename, allowed)
            assert is_valid == should_be_valid
            if not should_be_valid and filename != "":
                assert "Invalid file extension" in error or "File has no extension" in error

    def test_extensions_without_dots(self) -> None:
        """Test that extensions work with or without dots."""
        allowed = ["pdf", "txt"]  # Without dots

        is_valid, error = validate_file_extension("document.pdf", allowed)
        assert is_valid is True
        assert error == ""

    def test_case_insensitive(self) -> None:
        """Test case-insensitive extension matching."""
        allowed = [".PDF", ".TXT"]

        test_cases = [
            "document.pdf",
            "document.PDF",
            "document.Pdf",
            "file.txt",
            "file.TXT",
        ]

        for filename in test_cases:
            is_valid, error = validate_file_extension(filename, allowed)
            assert is_valid is True
            assert error == ""

    def test_no_extension(self) -> None:
        """Test files without extensions."""
        allowed = [".pdf"]

        is_valid, error = validate_file_extension("README", allowed)
        assert is_valid is False
        assert "File has no extension" in error

    def test_empty_allowed_list(self) -> None:
        """Test with empty allowed extensions list."""
        is_valid, error = validate_file_extension("file.pdf", [])
        assert is_valid is False
        assert "No allowed extensions specified" in error

    def test_empty_path(self) -> None:
        """Test with empty file path."""
        is_valid, error = validate_file_extension("", [".pdf"])
        assert is_valid is False
        assert "File path is empty" in error

    def test_multiple_dots(self) -> None:
        """Test files with multiple dots in name."""
        allowed = [".pdf"]

        is_valid, error = validate_file_extension("document.v2.final.pdf", allowed)
        assert is_valid is True
        assert error == ""

        is_valid, error = validate_file_extension("document.v2.final.txt", allowed)
        assert is_valid is False
        assert "Invalid file extension" in error


class TestValidatePathIsAbsolute:
    """Test cases for absolute path validation."""

    def test_absolute_paths(self) -> None:
        """Test recognition of absolute paths."""
        absolute_paths = [
            "/home/user/file.pdf",
            "/tmp/document.txt",
            "/",
        ]

        for path in absolute_paths:
            is_valid, error = validate_path_is_absolute(path)
            assert is_valid is True
            assert error == ""

    def test_relative_paths(self) -> None:
        """Test rejection of relative paths."""
        relative_paths = [
            "file.pdf",
            "./file.pdf",
            "../file.pdf",
            "documents/file.pdf",
        ]

        for path in relative_paths:
            is_valid, error = validate_path_is_absolute(path)
            assert is_valid is False
            assert "Path is not absolute" in error

    def test_windows_paths(self) -> None:
        """Test Windows-style paths."""
        # On Windows, these would be absolute
        # On Unix, they're relative
        import platform

        windows_paths = [
            "C:\\Users\\file.pdf",
            "D:\\Documents\\report.docx",
        ]

        for path in windows_paths:
            is_valid, error = validate_path_is_absolute(path)
            # On Windows these should be valid, on Unix they're invalid
            if platform.system() == "Windows":
                assert is_valid is True
            else:
                assert is_valid is False

    def test_empty_path(self) -> None:
        """Test with empty path."""
        is_valid, error = validate_path_is_absolute("")
        assert is_valid is False
        assert "File path is empty" in error


class TestValidatePathNoSpecialChars:
    """Test cases for special character validation."""

    def test_paths_with_dangerous_chars(self) -> None:
        """Test detection of dangerous characters."""
        dangerous_paths = [
            "/home/user/file<script>.pdf",
            "/home/user/file>output.txt",
            "/home/user/file|pipe.pdf",
            "/home/user/file&background.pdf",
            "/home/user/file;command.pdf",
            "/home/user/file$variable.pdf",
            "/home/user/file`exec`.pdf",
            "/home/user/file\nwithNewline.pdf",
            "/home/user/file\rwithReturn.pdf",
            "/home/user/file\x00withNull.pdf",
        ]

        for path in dangerous_paths:
            is_valid, error = validate_path_no_special_chars(path)
            assert is_valid is False
            assert "dangerous character" in error

    def test_safe_paths(self) -> None:
        """Test acceptance of safe paths."""
        safe_paths = [
            "/home/user/file.pdf",
            "/home/user/my-document_v2.pdf",
            "/home/user/report (2024).pdf",
            "/home/user/data[1].pdf",
            "/home/user/file@company.pdf",
        ]

        for path in safe_paths:
            is_valid, error = validate_path_no_special_chars(path)
            assert is_valid is True
            assert error == ""

    def test_empty_path(self) -> None:
        """Test with empty path."""
        is_valid, error = validate_path_no_special_chars("")
        assert is_valid is False
        assert "File path is empty" in error

    def test_unicode_safe_chars(self) -> None:
        """Test that Unicode characters are allowed."""
        unicode_paths = [
            "/home/user/文档.pdf",
            "/home/user/файл.pdf",
            "/home/user/αρχείο.pdf",
        ]

        for path in unicode_paths:
            is_valid, error = validate_path_no_special_chars(path)
            assert is_valid is True
            assert error == ""
