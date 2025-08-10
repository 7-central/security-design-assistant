# Test PDF Fixtures

This directory contains test PDF files for unit testing the PDF processor.

## Files

Due to the nature of PDF files, actual test PDFs should be added manually:

1. `genuine_text.pdf` - A PDF with extractable text content
2. `scanned_image.pdf` - A scanned PDF with no text layer
3. `password_protected.pdf` - A password-protected PDF
4. `corrupted.pdf` - A corrupted/invalid PDF file
5. `multi_page.pdf` - A multi-page PDF with mixed content
6. `large_drawing.pdf` - A large format drawing (A0/A1 size)

## Creating Test PDFs

For testing purposes, you can create simple PDFs using various tools:

### Genuine Text PDF
```python
from reportlab.pdfgen import canvas
c = canvas.Canvas("genuine_text.pdf")
c.drawString(100, 750, "This is a test PDF with text content")
c.save()
```

### Scanned Image PDF
Convert any image to PDF without OCR layer.

### Password Protected PDF
Use any PDF tool to add password protection to an existing PDF.

### Corrupted PDF
Create a file with PDF header but invalid content:
```bash
echo "%PDF-1.4 invalid content" > corrupted.pdf
```