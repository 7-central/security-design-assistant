"""Generate 10 drawing variations for integration testing."""
import io
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.lib.colors import black, red, blue
from pypdf import PdfWriter, PdfReader, Transformation
import math


def create_base_drawing(c, page_width, page_height):
    """Create base drawing with doors and access control components."""
    # Title
    c.setFont("Helvetica-Bold", 16)
    c.drawString(inch, page_height - inch, "Security Access Control Drawing")
    
    # Legend
    c.setFont("Helvetica", 10)
    legend_y = page_height - 2*inch
    c.drawString(inch, legend_y, "Legend:")
    c.drawString(inch + 0.5*inch, legend_y - 15, "D = Door")
    c.drawString(inch + 0.5*inch, legend_y - 30, "R = Card Reader")
    c.drawString(inch + 0.5*inch, legend_y - 45, "B = Request to Exit Button")
    c.drawString(inch + 0.5*inch, legend_y - 60, "K = Keypad")
    
    # Draw doors with labels
    doors = [
        ("A-101", 2*inch, 5*inch, "Main Entry"),
        ("A-102", 4*inch, 5*inch, "Office 1"),
        ("A-103", 6*inch, 5*inch, "Office 2"),
        ("A-104", 2*inch, 3*inch, "Storage"),
        ("A-105", 4*inch, 3*inch, "Conference"),
    ]
    
    for door_id, x, y, desc in doors:
        # Door rectangle
        c.rect(x, y, 50, 80)
        c.drawString(x + 5, y + 40, "D")
        c.drawString(x, y - 15, door_id)
        c.setFont("Helvetica", 8)
        c.drawString(x, y - 25, desc)
        c.setFont("Helvetica", 10)
        
        # Card reader
        c.rect(x - 20, y + 30, 15, 20)
        c.drawString(x - 17, y + 37, "R")
        
        # Exit button
        c.circle(x + 55, y + 40, 8)
        c.drawString(x + 52, y + 37, "B")


def variation_1_different_text_sizes():
    """Variation 1: Different text sizes (8pt, 12pt, 18pt)."""
    pdf_path = Path("tests/fixtures/drawings/variations/01_different_text_sizes.pdf")
    
    c = canvas.Canvas(str(pdf_path), pagesize=letter)
    width, height = letter
    
    # Title in 18pt
    c.setFont("Helvetica-Bold", 18)
    c.drawString(inch, height - inch, "SECURITY SYSTEM - VARIABLE TEXT SIZES")
    
    # Components in different sizes
    sizes = [8, 10, 12, 14, 16]
    y_pos = height - 2*inch
    
    for i, size in enumerate(sizes):
        c.setFont("Helvetica", size)
        door_id = f"A-{200 + i}"
        c.drawString(2*inch, y_pos, f"{door_id}: Door with {size}pt text")
        
        # Draw door symbol
        c.rect(4*inch, y_pos - 5, 30, 40)
        c.drawString(4*inch + 5, y_pos + 10, "D")
        
        # Reader and button with same size text
        c.rect(4.5*inch, y_pos, 15, 20)
        c.drawString(4.5*inch + 2, y_pos + 5, "R")
        
        y_pos -= inch
    
    c.save()
    return pdf_path


def variation_2_rotated_pages():
    """Variation 2: Pages with different rotations."""
    pdf_path = Path("tests/fixtures/drawings/variations/02_rotated_pages.pdf")
    
    # Create initial PDF
    temp_pdf = io.BytesIO()
    c = canvas.Canvas(temp_pdf, pagesize=letter)
    width, height = letter
    
    # Page 1 - Normal
    create_base_drawing(c, width, height)
    c.showPage()
    
    # Page 2 - Will be rotated 90°
    c.setFont("Helvetica-Bold", 14)
    c.drawString(inch, height - inch, "Page to be rotated 90 degrees")
    create_base_drawing(c, width, height)
    c.showPage()
    
    # Page 3 - Will be rotated 180°
    c.drawString(inch, height - inch, "Page to be rotated 180 degrees")
    create_base_drawing(c, width, height)
    c.showPage()
    
    # Page 4 - Will be rotated 270°
    c.drawString(inch, height - inch, "Page to be rotated 270 degrees")
    create_base_drawing(c, width, height)
    c.save()
    
    # Apply rotations
    temp_pdf.seek(0)
    reader = PdfReader(temp_pdf)
    writer = PdfWriter()
    
    # Page 1 - no rotation
    writer.add_page(reader.pages[0])
    
    # Page 2 - 90° rotation
    page2 = reader.pages[1]
    page2.rotate(90)
    writer.add_page(page2)
    
    # Page 3 - 180° rotation
    page3 = reader.pages[2]
    page3.rotate(180)
    writer.add_page(page3)
    
    # Page 4 - 270° rotation
    page4 = reader.pages[3]
    page4.rotate(270)
    writer.add_page(page4)
    
    with open(pdf_path, 'wb') as f:
        writer.write(f)
    
    return pdf_path


def variation_3_additional_annotations():
    """Variation 3: 20+ extra text overlays on doors."""
    pdf_path = Path("tests/fixtures/drawings/variations/03_additional_annotations.pdf")
    
    c = canvas.Canvas(str(pdf_path), pagesize=letter)
    width, height = letter
    
    create_base_drawing(c, width, height)
    
    # Add many annotations
    c.setFont("Helvetica", 8)
    c.setFillColor(red)
    
    annotations = [
        "Install by 3/15", "Verify wiring", "Check voltage", "Test card reader",
        "Update firmware", "Schedule maintenance", "Replace battery", "Clean sensor",
        "Calibrate lock", "Test emergency release", "Check alignment", "Verify access list",
        "Update schedule", "Test backup power", "Check logs", "Verify compliance",
        "Test alarm", "Check tamper switch", "Verify REX", "Test fail-secure",
        "Check strike plate", "Test monitoring"
    ]
    
    # Scatter annotations around door locations
    random.seed(42)  # For reproducibility
    for i, annotation in enumerate(annotations):
        x = random.randint(int(1.5*inch), int(7*inch))
        y = random.randint(int(2*inch), int(8*inch))
        c.drawString(x, y, annotation)
    
    c.setFillColor(black)
    c.save()
    return pdf_path


def variation_4_removed_components():
    """Variation 4: 30% of doors missing readers/buttons."""
    pdf_path = Path("tests/fixtures/drawings/variations/04_removed_components.pdf")
    
    c = canvas.Canvas(str(pdf_path), pagesize=letter)
    width, height = letter
    
    c.setFont("Helvetica-Bold", 16)
    c.drawString(inch, height - inch, "Partial System - Some Components Missing")
    
    # Draw 10 doors, 3 will have missing components
    doors_total = 10
    missing_indices = [2, 5, 8]  # 30% missing
    
    c.setFont("Helvetica", 10)
    for i in range(doors_total):
        x = 2*inch + (i % 5) * 1.2*inch
        y = 5*inch if i < 5 else 3*inch
        door_id = f"A-{301 + i}"
        
        # Always draw door
        c.rect(x, y, 40, 60)
        c.drawString(x + 10, y + 30, "D")
        c.drawString(x, y - 15, door_id)
        
        # Conditionally draw components
        if i not in missing_indices:
            # Card reader
            c.rect(x - 15, y + 20, 12, 15)
            c.drawString(x - 12, y + 25, "R")
            
            # Exit button
            c.circle(x + 45, y + 30, 6)
            c.drawString(x + 43, y + 28, "B")
        else:
            c.setFont("Helvetica", 8)
            c.drawString(x, y - 25, "(incomplete)")
            c.setFont("Helvetica", 10)
    
    c.save()
    return pdf_path


def variation_5_different_symbols():
    """Variation 5: Non-standard door/reader symbols."""
    pdf_path = Path("tests/fixtures/drawings/variations/05_different_symbols.pdf")
    
    c = canvas.Canvas(str(pdf_path), pagesize=letter)
    width, height = letter
    
    c.setFont("Helvetica-Bold", 16)
    c.drawString(inch, height - inch, "Non-Standard Symbol Representation")
    
    # Different symbol styles
    c.setFont("Helvetica", 10)
    
    doors = [
        ("A-401", 2*inch, 5*inch, "◊"),  # Diamond for door
        ("A-402", 3.5*inch, 5*inch, "▢"),  # Square for door
        ("A-403", 5*inch, 5*inch, "⬟"),  # Pentagon
        ("A-404", 2*inch, 3*inch, "○"),  # Circle for door
        ("A-405", 3.5*inch, 3*inch, "△"),  # Triangle
    ]
    
    for door_id, x, y, symbol in doors:
        # Draw non-standard door symbol
        c.setFont("Helvetica", 20)
        c.drawString(x, y, symbol)
        c.setFont("Helvetica", 10)
        c.drawString(x - 10, y - 20, door_id)
        
        # Non-standard reader symbols
        c.setFont("Helvetica", 12)
        c.drawString(x - 30, y, "◉")  # Different reader symbol
        c.drawString(x + 40, y, "★")  # Different button symbol
        c.setFont("Helvetica", 8)
        c.drawString(x - 35, y - 15, "CR")
        c.drawString(x + 35, y - 15, "REX")
    
    c.save()
    return pdf_path


def variation_6_multiple_pages():
    """Variation 6: 4-page drawing with components on each."""
    pdf_path = Path("tests/fixtures/drawings/variations/06_multiple_pages.pdf")
    
    c = canvas.Canvas(str(pdf_path), pagesize=letter)
    width, height = letter
    
    floors = ["First Floor", "Second Floor", "Third Floor", "Basement"]
    
    for floor_idx, floor_name in enumerate(floors):
        c.setFont("Helvetica-Bold", 16)
        c.drawString(inch, height - inch, f"Security System - {floor_name}")
        
        # Draw doors for this floor
        c.setFont("Helvetica", 10)
        for i in range(5):
            x = 2*inch + i * inch
            y = 5*inch
            door_id = f"A-{(floor_idx+1)*100 + i + 1}"
            
            # Door
            c.rect(x, y, 40, 60)
            c.drawString(x + 10, y + 30, "D")
            c.drawString(x, y - 15, door_id)
            
            # Reader
            c.rect(x - 15, y + 20, 12, 15)
            c.drawString(x - 12, y + 25, "R")
            
            # Button
            c.circle(x + 45, y + 30, 6)
            c.drawString(x + 43, y + 28, "B")
        
        if floor_idx < len(floors) - 1:
            c.showPage()
    
    c.save()
    return pdf_path


def variation_7_overlapping_elements():
    """Variation 7: 5+ components within 50px radius."""
    pdf_path = Path("tests/fixtures/drawings/variations/07_overlapping_elements.pdf")
    
    c = canvas.Canvas(str(pdf_path), pagesize=letter)
    width, height = letter
    
    c.setFont("Helvetica-Bold", 16)
    c.drawString(inch, height - inch, "High Density Component Layout")
    
    # Create clusters of overlapping components
    clusters = [
        (3*inch, 5*inch),
        (5*inch, 5*inch),
        (4*inch, 3*inch),
    ]
    
    c.setFont("Helvetica", 9)
    for cluster_idx, (cx, cy) in enumerate(clusters):
        # Draw 5-6 components in tight proximity
        for i in range(6):
            angle = (2 * math.pi * i) / 6
            x = cx + 30 * math.cos(angle)
            y = cy + 30 * math.sin(angle)
            
            door_id = f"A-{701 + cluster_idx*10 + i}"
            
            # Overlapping doors
            c.setStrokeColor(black)
            c.setFillColor(black)
            c.rect(x, y, 35, 50, fill=0)
            c.drawString(x + 8, y + 25, "D")
            c.drawString(x - 5, y - 10, door_id)
            
            # Overlapping readers
            c.rect(x - 10, y + 15, 10, 12, fill=0)
            c.drawString(x - 8, y + 19, "R")
    
    c.save()
    return pdf_path


def variation_8_poor_scan_quality():
    """Variation 8: Simulated poor scan quality (blur effect)."""
    # First create a clear PDF
    temp_pdf_path = Path("tests/fixtures/drawings/variations/temp_clear.pdf")
    c = canvas.Canvas(str(temp_pdf_path), pagesize=letter)
    width, height = letter
    
    create_base_drawing(c, width, height)
    c.save()
    
    # Convert to image and apply blur
    from pdf2image import convert_from_path
    images = convert_from_path(str(temp_pdf_path), dpi=150)
    
    # Apply gaussian blur to simulate poor scan
    blurred_image = images[0].filter(ImageFilter.GaussianBlur(radius=2))
    
    # Add noise
    pixels = blurred_image.load()
    width_px, height_px = blurred_image.size
    for _ in range(1000):  # Add random noise pixels
        x = random.randint(0, width_px - 1)
        y = random.randint(0, height_px - 1)
        pixels[x, y] = (
            random.randint(200, 255),
            random.randint(200, 255),
            random.randint(200, 255)
        )
    
    # Save as PDF
    pdf_path = Path("tests/fixtures/drawings/variations/08_poor_scan_quality.pdf")
    blurred_image.save(str(pdf_path), "PDF", resolution=150)
    
    # Clean up temp file
    temp_pdf_path.unlink()
    
    return pdf_path


def variation_9_different_legends():
    """Variation 9: Alternative symbol key definitions."""
    pdf_path = Path("tests/fixtures/drawings/variations/09_different_legends.pdf")
    
    c = canvas.Canvas(str(pdf_path), pagesize=letter)
    width, height = letter
    
    c.setFont("Helvetica-Bold", 16)
    c.drawString(inch, height - inch, "Alternative Symbol Legend System")
    
    # Alternative legend
    c.setFont("Helvetica-Bold", 12)
    c.drawString(inch, height - 2*inch, "Symbol Key:")
    c.setFont("Helvetica", 10)
    legend_items = [
        ("DR", "Secured Door"),
        ("CR", "Credential Reader"),
        ("EX", "Exit Device"),
        ("KP", "Keypad Entry"),
        ("MS", "Motion Sensor"),
        ("AL", "Alarm Point"),
    ]
    
    y_pos = height - 2.5*inch
    for symbol, description in legend_items:
        c.drawString(1.5*inch, y_pos, f"{symbol} = {description}")
        y_pos -= 20
    
    # Draw components using alternative symbols
    doors = [
        ("A-901", 4*inch, 5*inch),
        ("A-902", 5.5*inch, 5*inch),
        ("A-903", 4*inch, 3*inch),
        ("A-904", 5.5*inch, 3*inch),
    ]
    
    for door_id, x, y in doors:
        # Door with alternative symbol
        c.rect(x, y, 45, 70)
        c.drawString(x + 10, y + 35, "DR")
        c.drawString(x, y - 15, door_id)
        
        # Alternative reader symbol
        c.rect(x - 20, y + 25, 18, 20)
        c.drawString(x - 16, y + 32, "CR")
        
        # Alternative exit symbol
        c.rect(x + 50, y + 30, 15, 15)
        c.drawString(x + 52, y + 35, "EX")
    
    c.save()
    return pdf_path


def variation_10_mixed_systems():
    """Variation 10: Include C- and I- prefixes to test filtering."""
    pdf_path = Path("tests/fixtures/drawings/variations/10_mixed_system_components.pdf")
    
    c = canvas.Canvas(str(pdf_path), pagesize=letter)
    width, height = letter
    
    c.setFont("Helvetica-Bold", 16)
    c.drawString(inch, height - inch, "Mixed System Components (A-, C-, I- prefixes)")
    
    c.setFont("Helvetica", 10)
    
    # Mix of A-, C-, and I- prefixed components
    components = [
        # Access control (A-) - should be extracted
        ("A-001", 2*inch, 6*inch, "Access Door 1"),
        ("A-002", 3.5*inch, 6*inch, "Access Door 2"),
        ("A-003", 5*inch, 6*inch, "Access Door 3"),
        
        # CCTV (C-) - should be filtered out
        ("C-101", 2*inch, 4.5*inch, "Camera 1"),
        ("C-102", 3.5*inch, 4.5*inch, "Camera 2"),
        ("C-103", 5*inch, 4.5*inch, "Camera 3"),
        
        # Intrusion (I-) - should be filtered out
        ("I-201", 2*inch, 3*inch, "Motion Detector 1"),
        ("I-202", 3.5*inch, 3*inch, "Motion Detector 2"),
        ("I-203", 5*inch, 3*inch, "Glass Break 3"),
        
        # More A- components
        ("A-004", 6.5*inch, 6*inch, "Access Door 4"),
        ("A-005", 6.5*inch, 4.5*inch, "Access Door 5"),
    ]
    
    for comp_id, x, y, description in components:
        if comp_id.startswith("A-"):
            # Draw door
            c.rect(x, y, 40, 60)
            c.drawString(x + 10, y + 30, "D")
            c.drawString(x, y - 15, comp_id)
            c.setFont("Helvetica", 8)
            c.drawString(x, y - 25, description)
            c.setFont("Helvetica", 10)
            
            # Add reader and button
            c.rect(x - 15, y + 20, 12, 15)
            c.drawString(x - 12, y + 25, "R")
            c.circle(x + 45, y + 30, 6)
            c.drawString(x + 43, y + 28, "B")
            
        elif comp_id.startswith("C-"):
            # Draw camera symbol
            c.circle(x + 15, y + 15, 15)
            c.drawString(x + 10, y + 10, "CAM")
            c.drawString(x, y - 15, comp_id)
            c.setFont("Helvetica", 8)
            c.drawString(x, y - 25, description)
            c.setFont("Helvetica", 10)
            
        elif comp_id.startswith("I-"):
            # Draw intrusion sensor symbol
            c.rect(x, y, 30, 30)
            c.drawString(x + 5, y + 12, "PIR" if "Motion" in description else "GB")
            c.drawString(x, y - 15, comp_id)
            c.setFont("Helvetica", 8)
            c.drawString(x, y - 25, description)
            c.setFont("Helvetica", 10)
    
    c.save()
    return pdf_path


def main():
    """Generate all 10 variations."""
    print("Generating drawing variations for testing...")
    
    # Ensure directory exists
    variations_dir = Path("tests/fixtures/drawings/variations")
    variations_dir.mkdir(parents=True, exist_ok=True)
    
    variations = [
        ("1. Different text sizes", variation_1_different_text_sizes),
        ("2. Rotated pages", variation_2_rotated_pages),
        ("3. Additional annotations", variation_3_additional_annotations),
        ("4. Removed components", variation_4_removed_components),
        ("5. Different symbols", variation_5_different_symbols),
        ("6. Multiple pages", variation_6_multiple_pages),
        ("7. Overlapping elements", variation_7_overlapping_elements),
        ("8. Poor scan quality", variation_8_poor_scan_quality),
        ("9. Different legends", variation_9_different_legends),
        ("10. Mixed system components", variation_10_mixed_systems),
    ]
    
    generated_files = []
    for name, generator_func in variations:
        try:
            print(f"Generating: {name}")
            pdf_path = generator_func()
            generated_files.append(pdf_path)
            print(f"  ✓ Created: {pdf_path}")
        except Exception as e:
            print(f"  ✗ Error generating {name}: {e}")
    
    print(f"\nGenerated {len(generated_files)} variation files:")
    for f in generated_files:
        print(f"  - {f}")
    
    return generated_files


if __name__ == "__main__":
    main()