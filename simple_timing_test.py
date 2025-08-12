#!/usr/bin/env python3
"""
Simple timing test for the API.
"""

import requests
import time
import json

print("⏱️  Simple Timing Test")
print("=" * 50)

start_time = time.time()

# Submit a PDF
with open("tests/fixtures/pdfs/103P3-E34-QCI-40098_Ver1.pdf", "rb") as f:
    response = requests.post(
        "http://localhost:8000/process-drawing",
        files={"drawing_file": ("test.pdf", f, "application/pdf")},
        data={"client_name": "test", "project_name": "test"},
        timeout=60  # 60 second timeout
    )

end_time = time.time()
elapsed = end_time - start_time

print(f"Status Code: {response.status_code}")
print(f"Total Time: {elapsed:.2f} seconds")

if response.status_code in [200, 202]:
    result = response.json()
    print(f"\nJob ID: {result.get('job_id')}")
    print(f"Status: {result.get('status')}")
    
    # Get timing from metadata
    metadata = result.get("metadata", {})
    processing_time = metadata.get("processing_time_seconds", elapsed)
    
    print(f"\n⏱️  Timing Breakdown:")
    print(f"  Processing Time: {processing_time:.2f} seconds")
    print(f"  API Overhead: {elapsed - processing_time:.2f} seconds")
    
    # Component timing
    summary = result.get("summary", {})
    total_components = summary.get("total_components", 0)
    
    if total_components > 0:
        print(f"\n📊 Performance Metrics:")
        print(f"  Total Components: {total_components}")
        print(f"  Time per Component: {processing_time/total_components:.3f} seconds")
        print(f"  Component Processing Rate: {total_components/processing_time:.1f} components/second")
    
    # PDF metrics
    total_pages = metadata.get("total_pages", 1)
    pdf_size = metadata.get("file_size_mb", 0)
    
    print(f"\n📄 PDF Metrics:")
    print(f"  Pages: {total_pages}")
    print(f"  Size: {pdf_size:.2f} MB")
    print(f"  Processing Speed: {total_pages/processing_time:.2f} pages/second")
    
    if pdf_size > 0:
        print(f"  Throughput: {pdf_size/processing_time:.2f} MB/second")
else:
    print(f"Error: {response.text}")