#!/usr/bin/env python3
"""
Diagnose where the processing is getting stuck.
"""

import asyncio
import os
from pathlib import Path
from datetime import datetime
import sys
import time

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

# Ensure env vars are loaded
from dotenv import load_dotenv
load_dotenv()

from src.agents.excel_generation_agent import ExcelGenerationAgent
from src.agents.schedule_agent_v2 import ScheduleAgentV2
from src.storage.local_storage import LocalStorage
from src.models.job import Job, JobStatus
from src.utils.pdf_processor import PDFProcessor

async def diagnose():
    """Test each component separately to find where it hangs."""
    
    print("🔍 Diagnostic Test - Finding where processing hangs")
    print("=" * 60)
    
    # Test 1: PDF Processing
    print("\n1️⃣ Testing PDF Processing...")
    start = time.time()
    try:
        processor = PDFProcessor()
        pdf_path = "tests/fixtures/pdfs/103P3-E34-QCI-40098_Ver1.pdf"
        pages, metadata = processor.process_pdf(pdf_path)
        elapsed = time.time() - start
        print(f"   ✅ PDF processed in {elapsed:.2f}s - {len(pages)} pages")
        
        # Convert to format expected by Schedule Agent
        import base64
        from io import BytesIO
        
        pages_data = []
        for p in pages:
            if p.image:
                buffer = BytesIO()
                p.image.save(buffer, format="PNG")
                image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            else:
                image_base64 = None
            
            pages_data.append({
                "page_num": p.page_num,
                "image_base64": image_base64,
                "pdf_path": str(pdf_path)
            })
        
        result = {
            "pages": pages_data,
            "total_pages": len(pages)
        }
    except Exception as e:
        print(f"   ❌ PDF processing failed: {e}")
        return
    
    # Test 2: Schedule Agent
    print("\n2️⃣ Testing Schedule Agent...")
    start = time.time()
    try:
        job = Job(
            job_id="diagnostic_test",
            client_name="test",
            project_name="test",
            status=JobStatus.PROCESSING,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        storage = LocalStorage()
        
        schedule_agent = ScheduleAgentV2(storage=storage, job=job)
        print("   Calling Schedule Agent process()...")
        
        # Add timeout to see if it hangs here
        agent_result = await asyncio.wait_for(
            schedule_agent.process({"pages": result["pages"]}),
            timeout=30.0
        )
        
        elapsed = time.time() - start
        print(f"   ✅ Schedule Agent completed in {elapsed:.2f}s")
        
        # Check what was returned
        if isinstance(agent_result, dict) and "components" in agent_result:
            components_data = agent_result["components"]
            if isinstance(components_data, dict) and "pages" in components_data:
                total = sum(len(page["components"]) for page in components_data["pages"])
                print(f"   Found {total} components")
        
    except asyncio.TimeoutError:
        print(f"   ❌ Schedule Agent timed out after 30 seconds!")
        print("   This is where the hang is occurring.")
        return
    except Exception as e:
        print(f"   ❌ Schedule Agent failed: {e}")
        return
    
    # Test 3: Excel Generation
    print("\n3️⃣ Testing Excel Generation...")
    start = time.time()
    try:
        # Extract components
        flattened = []
        if isinstance(agent_result, dict) and "components" in agent_result:
            components_data = agent_result["components"]
            if isinstance(components_data, dict) and "pages" in components_data:
                for page in components_data["pages"]:
                    if isinstance(page, dict) and "components" in page:
                        flattened.extend(page["components"])
        
        excel_agent = ExcelGenerationAgent(storage=storage, job=job)
        excel_result = await excel_agent.process({"components": flattened})
        
        elapsed = time.time() - start
        if excel_result.get("status") == "completed":
            print(f"   ✅ Excel generated in {elapsed:.2f}s")
            print(f"   File: {excel_result.get('file_path')}")
        else:
            print(f"   ❌ Excel generation failed: {excel_result.get('message')}")
    except Exception as e:
        print(f"   ❌ Excel generation failed: {e}")
    
    print("\n" + "=" * 60)
    print("Diagnostic complete!")

if __name__ == "__main__":
    print("Running diagnostic...")
    print(f"GEMINI_API_KEY present: {bool(os.getenv('GEMINI_API_KEY'))}")
    
    try:
        asyncio.run(diagnose())
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")