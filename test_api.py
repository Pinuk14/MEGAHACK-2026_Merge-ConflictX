"""
Example test script for Merge-ConflictX API.
Shows complete workflow: upload -> run -> stream -> download.
"""

import asyncio
import aiohttp
import json
from pathlib import Path


API_BASE = "http://localhost:8000"


async def test_complete_workflow():
    """Test the complete API workflow."""
    
    async with aiohttp.ClientSession() as session:
        print("=" * 70)
        print("MERGE-CONFLICTX API WORKFLOW TEST")
        print("=" * 70)
        
        # 1. Health check
        print("\n1. Health Check")
        print("-" * 70)
        async with session.get(f"{API_BASE}/health") as resp:
            health = await resp.json()
            print(f"Response: {json.dumps(health, indent=2)}")
        
        # 2. Upload a file
        print("\n2. Upload Document")
        print("-" * 70)
        
        # Create a test document
        test_doc = """
        MERGER AGREEMENT
        
        This Merger Agreement ("Agreement") is entered into as of March 13, 2026,
        between Company A ("Acquirer") and Company B ("Target").
        
        ARTICLE I: CONSIDERATION
        The Acquirer shall pay $500 million in cash for all outstanding shares.
        
        ARTICLE II: REPRESENTATIONS AND WARRANTIES
        Target represents that it has all necessary authority to execute this Agreement.
        
        ARTICLE III: INDEMNIFICATION
        Acquirer indemnifies Target against all third-party claims for 12 months.
        
        ARTICLE IV: INTELLECTUAL PROPERTY
        All existing IP rights remain with the original owner.
        Derivative works are jointly owned.
        
        ARTICLE V: REGULATORY COMPLIANCE
        Both parties shall comply with all applicable laws and regulations.
        This includes healthcare, securities, and environmental regulations.
        
        ARTICLE VI: CONFIDENTIALITY
        All confidential information must be protected for 5 years post-closing.
        """
        
        files = {"file": ("merger_agreement.txt", test_doc.encode())}
        async with session.post(f"{API_BASE}/upload", data=files) as resp:
            upload_result = await resp.json()
            print(f"Response: {json.dumps(upload_result, indent=2)}")
            file_id = upload_result["file_id"]
        
        # 3. Kickoff analysis job
        print("\n3. Kickoff Analysis Job")
        print("-" * 70)
        
        run_request = {
            "file_id": file_id,
        }
        
        async with session.post(
            f"{API_BASE}/run",
            json=run_request
        ) as resp:
            job_result = await resp.json()
            print(f"Response: {json.dumps(job_result, indent=2)}")
            job_id = job_result["job_id"]
        
        # 4. Check job status
        print("\n4. Job Status")
        print("-" * 70)
        
        async with session.get(f"{API_BASE}/jobs/{job_id}") as resp:
            job_status = await resp.json()
            print(f"Response: {json.dumps(job_status, indent=2, default=str)}")
        
        # 5. Stream events (partial - first 3 events)
        print("\n5. SSE Stream Preview (first 3 events)")
        print("-" * 70)
        
        event_count = 0
        async with session.get(f"{API_BASE}/jobs/{job_id}/stream") as resp:
            buffer = ""
            while True:
                try:
                    chunk = await asyncio.wait_for(resp.content.read(100), timeout=2.0)
                except asyncio.TimeoutError:
                    print("(Stream timeout - job processing...)")
                    break
                
                if not chunk:
                    break
                
                buffer += chunk.decode("utf-8", errors="ignore")
                
                # Parse SSE events
                while "\n\n" in buffer:
                    event_text, buffer = buffer.split("\n\n", 1)
                    
                    if event_text.strip():
                        lines = event_text.strip().split("\n")
                        event_type = None
                        event_data = None
                        
                        for line in lines:
                            if line.startswith("event: "):
                                event_type = line.replace("event: ", "")
                            elif line.startswith("data: "):
                                event_data = json.loads(line.replace("data: ", ""))
                        
                        if event_type:
                            event_count += 1
                            print(f"\nEvent {event_count}: {event_type}")
                            if event_type == "step_progress":
                                print(f"  Step: {event_data['short']} | Progress: {event_data['progress_pct']}%")
                            elif event_type == "step_complete":
                                print(f"  Step: {event_data['step_id']} | {event_data['verdict']['flash']}")
                            elif event_type == "pipeline_done":
                                print(f"  Confidence: {event_data['confidence']} | Runtime: {event_data['runtime_seconds']}s")
                            
                            if event_count >= 3:
                                print("\n(Stopping stream preview...)")
                                break
                
                if event_count >= 3:
                    break
        
        # 6. Fetch all panel data
        print("\n6. Panel Data Endpoints")
        print("-" * 70)
        
        endpoints = [
            ("stats", "Pit Stop Stats"),
            ("structure", "Aero Analysis"),
            ("radio", "Radio Comms"),
            ("topics", "Track Map Topics"),
            ("clauses", "Scrutineering"),
            ("recommendations", "Race Strategy"),
            ("insights", "Race Results"),
            ("stakeholders", "Constructors Standings"),
            ("risk", "Track Conditions"),
        ]
        
        for endpoint, label in endpoints:
            async with session.get(f"{API_BASE}/jobs/{job_id}/{endpoint}") as resp:
                data = await resp.json()
                print(f"\n{label} ({endpoint}):")
                print(f"  {json.dumps(data, indent=2)[:200]}...")
        
        # 7. Download JSON report
        print("\n7. Download JSON Report")
        print("-" * 70)
        
        async with session.get(f"{API_BASE}/jobs/{job_id}/report?format=json") as resp:
            report = await resp.json()
            print(f"Report keys: {list(report.keys())}")
            print(f"Job ID: {report.get('job_id')}")
            print(f"Status: {report.get('status')}")
        
        # 8. Abort job (try on a new job)
        print("\n8. Abort Job (demo)")
        print("-" * 70)
        
        # Create another job to abort
        async with session.post(
            f"{API_BASE}/run",
            json={"text": "Test document for abort"}
        ) as resp:
            abort_job = await resp.json()
            abort_job_id = abort_job["job_id"]
        
        async with session.delete(f"{API_BASE}/jobs/{abort_job_id}") as resp:
            abort_result = await resp.json()
            print(f"Response: {json.dumps(abort_result, indent=2)}")
        
        print("\n" + "=" * 70)
        print("TEST COMPLETE!")
        print("=" * 70)


async def test_parallel_requests():
    """Test parallel requests to endpoints."""
    
    print("\n" + "=" * 70)
    print("PARALLEL REQUESTS TEST")
    print("=" * 70)
    
    async with aiohttp.ClientSession() as session:
        # First, create a job
        run_request = {"text": "Sample policy document for analysis."}
        
        async with session.post(
            f"{API_BASE}/run",
            json=run_request
        ) as resp:
            job_result = await resp.json()
            job_id = job_result["job_id"]
            print(f"\nCreated job: {job_id}")
        
        # Then fetch all panel data in parallel
        print("\nFetching all panel data in parallel...")
        
        endpoints = [
            "stats", "structure", "radio", "topics", "clauses",
            "recommendations", "insights", "stakeholders", "risk"
        ]
        
        tasks = [
            session.get(f"{API_BASE}/jobs/{job_id}/{endpoint}")
            for endpoint in endpoints
        ]
        
        results = await asyncio.gather(*tasks)
        
        for endpoint, response in zip(endpoints, results):
            data = await response.json()
            print(f"  {endpoint}: {response.status} - OK")


if __name__ == "__main__":
    print("\nMake sure the API is running first:")
    print("  python -m uvicorn backend.api.main:app --reload\n")
    
    try:
        asyncio.run(test_complete_workflow())
        asyncio.run(test_parallel_requests())
    except aiohttp.ClientConnectorError:
        print("\n❌ ERROR: Could not connect to API at http://localhost:8000")
        print("Make sure to start the API server first!")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
