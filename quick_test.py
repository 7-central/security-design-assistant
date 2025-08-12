#!/usr/bin/env python3
"""
Quick test to verify the API is working and show output location.
"""

import requests
import time
import json
from pathlib import Path

print("🧪 Quick API Test")
print("=" * 60)

# Test health first
try:
    health = requests.get("http://localhost:8000/health", timeout=2)
    if health.status_code == 200:
        print("✅ Server is running")
    else:
        print("❌ Server not healthy")
        exit(1)
except:
    print("❌ Server is not responding. Please restart it with:")
    print("   ./start_server_with_env.sh")
    exit(1)

# Submit a test PDF
print("\n📤 Submitting PDF for processing...")
start_time = time.time()

try:
    with open("tests/fixtures/pdfs/103P3-E34-QCI-40098_Ver1.pdf", "rb") as f:
        response = requests.post(
            "http://localhost:8000/process-drawing",
            files={"drawing_file": ("test.pdf", f, "application/pdf")},
            data={"client_name": "demo_client", "project_name": "demo_project"},
            timeout=30
        )
    
    elapsed = time.time() - start_time
    
    if response.status_code in [200, 202]:
        result = response.json()
        
        print(f"✅ Processing completed in {elapsed:.1f} seconds!")
        print(f"\n📊 Results:")
        print(f"  Job ID: {result.get('job_id')}")
        print(f"  Status: {result.get('status')}")
        
        # Show timing
        processing_time = result.get("metadata", {}).get("processing_time_seconds", elapsed)
        print(f"\n⏱️  Timing:")
        print(f"  Processing Time: {processing_time:.2f} seconds")
        
        # Show summary
        if "summary" in result:
            print(f"\n📋 Components Found:")
            for key, value in result["summary"].items():
                print(f"  {key}: {value}")
        
        # Show file location
        file_path = result.get("file_path")
        if file_path:
            full_path = Path("local_output") / file_path
            print(f"\n📁 Excel File Location:")
            print(f"  Relative: {file_path}")
            print(f"  Full Path: {full_path.absolute()}")
            
            if full_path.exists():
                size = full_path.stat().st_size / 1024
                print(f"  File Size: {size:.1f} KB")
                print(f"\n✅ File exists and is ready to open!")
                print(f"\nTo open in Excel:")
                print(f"  open '{full_path.absolute()}'")
            else:
                print(f"  ⚠️  File not found at expected location")
        else:
            print("\n❌ No Excel file generated")
    else:
        print(f"❌ Processing failed: {response.status_code}")
        print(f"Error: {response.text}")
        
except requests.exceptions.Timeout:
    print("❌ Request timed out after 30 seconds")
    print("The server might be stuck. Please restart it.")
except Exception as e:
    print(f"❌ Error: {e}")

print("\n" + "=" * 60)
print("📁 All output files are stored in:")
print(f"   {Path('local_output').absolute()}/")
print("\nDirectory structure:")
print("   local_output/{client_name}/{project_name}/job_{job_id}/schedule_{timestamp}.xlsx")