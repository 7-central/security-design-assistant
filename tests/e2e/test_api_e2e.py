"""Simple E2E test of the full API endpoint."""
import time
from pathlib import Path
import httpx
import threading
import uvicorn


def test_api_endpoint():
    """Test the full API endpoint with all agents."""
    
    # Start FastAPI server in background
    from src.api.main import app
    
    config = uvicorn.Config(
        app=app,
        host="127.0.0.1",
        port=8002,  # Different port to avoid conflicts
        log_level="warning"
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    
    # Wait for server to start
    time.sleep(3)
    
    # Create client with 5-minute timeout
    client = httpx.Client(base_url="http://127.0.0.1:8002", timeout=300.0)
    
    # Verify server is running
    response = client.get("/health")
    assert response.status_code == 200
    print("✅ Server is running")
    
    # Use the actual client test PDF
    test_pdf_path = Path("tests/fixtures/pdfs/103P3-E34-QCI-40098_Ver1.pdf")
    
    print(f"📄 Testing with PDF: {test_pdf_path}")
    print(f"   Size: {test_pdf_path.stat().st_size / 1024:.1f} KB")
    
    # Context instructions (like a real user would provide)
    context_text = """Parse this drawing and extract all door access control components including:
- Door IDs and locations
- Card readers and their types
- Exit buttons (REX/RTE)
- Lock types and specifications
- Any biometric readers
Please list them with all their relevant information and attributes."""
    
    print(f"\n📝 Context provided:")
    print(f"   {context_text[:100]}...")
    
    # Upload and process
    start_time = time.time()
    
    with open(test_pdf_path, 'rb') as f:
        files = {'drawing_file': ('103P3-E34-QCI-40098_Ver1.pdf', f, 'application/pdf')}
        data = {
            'client_name': 'api_test_client',
            'project_name': 'api_e2e_test',
            'context_text': context_text  # Add context like production
        }
        
        print("\n🚀 Sending request to /process-drawing endpoint...")
        response = client.post(
            "/process-drawing",
            files=files,
            data=data
        )
    
    elapsed = time.time() - start_time
    
    # Check response
    print(f"\n📊 Response received in {elapsed:.1f} seconds")
    print(f"   Status code: {response.status_code}")
    
    if response.status_code in [200, 202]:  # 202 = Accepted (async processing)
        result = response.json()
        print(f"   Job ID: {result.get('job_id', 'N/A')}")
        print(f"   Status: {result.get('status', 'N/A')}")
        
        if 'file_path' in result:
            print(f"   Excel file: {result['file_path']}")
        
        if 'summary' in result:
            summary = result['summary']
            print(f"   Components found: {summary.get('doors_found', 0)} doors, "
                  f"{summary.get('readers_found', 0)} readers, "
                  f"{summary.get('exit_buttons_found', 0)} exit buttons")
        
        # Show context processing
        if 'metadata' in result and 'context_processing' in result['metadata']:
            context_info = result['metadata']['context_processing']
            print(f"\n📝 Context Processing:")
            print(f"   Type: {context_info.get('type', 'N/A')}")
            print(f"   Sections found: {context_info.get('sections_found', 'N/A')}")
            print(f"   Tokens used: {context_info.get('tokens_used', 'N/A')}")
        
        # Try to get Judge evaluation from job status endpoint
        job_id = result.get('job_id')
        if job_id:
            print(f"\n🔍 Fetching full job details including Judge evaluation...")
            status_response = client.get(f"/status/{job_id}")
            if status_response.status_code == 200:
                job_details = status_response.json()
                
                # Show evaluation if present
                if 'evaluation' in job_details:
                    eval_data = job_details['evaluation']
                    print(f"\n🎯 Judge Evaluation:")
                    print(f"   Overall: {eval_data.get('overall_assessment', 'N/A')}")
                    print(f"   Completeness: {eval_data.get('completeness', 'N/A')}")
                    print(f"   Correctness: {eval_data.get('correctness', 'N/A')}")
                    if 'improvement_suggestions' in eval_data:
                        suggestions = eval_data['improvement_suggestions']
                        if suggestions:
                            print(f"   Suggestions: {suggestions[:2] if isinstance(suggestions, list) else str(suggestions)[:100]}...")
                else:
                    print("   (Judge evaluation not included in status response)")
            else:
                print(f"   Could not fetch job status: {status_response.status_code}")
        
        # Show file location
        if 'file_path' in result:
            excel_path = f"local_output/{result['file_path']}"
            print(f"\n📄 Files created:")
            print(f"   Excel schedule: {excel_path}")
            print(f"   Use: open \"{excel_path}\" to view")
        
        print(f"\n✅ API test passed!")
        return True
    else:
        print(f"❌ API test failed!")
        print(f"   Error: {response.text}")
        return False


if __name__ == "__main__":
    success = test_api_endpoint()
    if success:
        print("\n" + "="*50)
        print("Full API E2E test completed successfully!")
    else:
        print("\n" + "="*50)
        print("API test failed - check error messages above")