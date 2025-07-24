#!/usr/bin/env python
"""
Universal crew testing script for SparkJAR Crew API.
Handles starting the API, running tests, and cleanup.

Usage:
    ./test_crew.py memory_maker_crew --payload test_payloads/vervelyn_corporate_policy_payload.json
    ./test_crew.py entity_research_crew --entity "OpenAI" --domain "technology"
    ./test_crew.py --list-crews
"""
import os
import sys
import json
import time
import signal
import subprocess
import argparse
import requests
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any

# Configuration
API_URL = "http://localhost:8000"
API_STARTUP_TIMEOUT = 30  # seconds
POLL_INTERVAL = 2  # seconds
MAX_POLL_TIME = 300  # 5 minutes

class CrewTester:
    def __init__(self):
        self.api_process = None
        self.token = None
        
    def cleanup(self):
        """Clean up API process on exit."""
        if self.api_process:
            print("\n🛑 Stopping API server...")
            self.api_process.terminate()
            try:
                self.api_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.api_process.kill()
    
    def generate_token(self) -> str:
        """Generate a test JWT token."""
        # Import from crew-api
        sys.path.insert(0, str(Path(__file__).parent / "services" / "crew-api"))
        from src.api.auth import create_token
        
        return create_token(
            user_id="test-user",
            scopes=["sparkjar_internal"],
            expires_in_hours=1
        )
    
    def wait_for_api(self) -> bool:
        """Wait for API to become available."""
        print("⏳ Waiting for API to start...")
        start_time = time.time()
        
        while time.time() - start_time < API_STARTUP_TIMEOUT:
            try:
                response = requests.get(f"{API_URL}/health")
                if response.status_code == 200:
                    print("✅ API is ready!")
                    return True
            except requests.exceptions.ConnectionError:
                pass
            time.sleep(1)
            sys.stdout.write(".")
            sys.stdout.flush()
        
        return False
    
    def start_api(self) -> bool:
        """Start the API server in the background."""
        print("🚀 Starting Crew API server...")
        
        # Change to crew-api directory
        crew_api_dir = Path(__file__).parent / "services" / "crew-api"
        
        # Start the API process
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        
        # Use the crew-api's venv if it exists, otherwise use system python
        venv_python = crew_api_dir / ".venv" / "bin" / "python"
        if not venv_python.exists():
            # Try the root venv
            venv_python = Path(__file__).parent / ".venv" / "bin" / "python"
        
        if not venv_python.exists():
            print("❌ No virtual environment found!")
            return False
            
        # Run from repo root to handle imports properly
        repo_root = Path(__file__).parent
        
        self.api_process = subprocess.Popen(
            [str(venv_python), "run_crew_api.py"],
            cwd=repo_root,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        # Monitor startup
        if not self.wait_for_api():
            print("\n❌ API failed to start!")
            # Print last few lines of output
            if self.api_process.stdout:
                print("\nAPI Output:")
                for line in self.api_process.stdout:
                    print(f"  {line.rstrip()}")
            return False
        
        return True
    
    def create_job(self, payload: Dict[str, Any]) -> Optional[str]:
        """Create a crew job via API."""
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.post(
                f"{API_URL}/crew_job",
                headers=headers,
                json=payload
            )
            
            if response.status_code == 200:
                job_data = response.json()
                return job_data.get("job_id")
            else:
                print(f"❌ Failed to create job: {response.status_code}")
                print(f"Response: {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ Error creating job: {e}")
            return None
    
    def poll_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Poll for job completion."""
        headers = {
            "Authorization": f"Bearer {self.token}"
        }
        
        print(f"\n📊 Monitoring job {job_id}...")
        start_time = time.time()
        last_status = None
        
        while time.time() - start_time < MAX_POLL_TIME:
            try:
                response = requests.get(
                    f"{API_URL}/crew_job/{job_id}",
                    headers=headers
                )
                
                if response.status_code == 200:
                    job_data = response.json()
                    status = job_data.get("status", "unknown")
                    
                    # Show status change
                    if status != last_status:
                        print(f"\n🔄 Status: {status}")
                        last_status = status
                    else:
                        sys.stdout.write(".")
                        sys.stdout.flush()
                    
                    # Check if completed
                    if status in ["completed", "failed", "error"]:
                        return job_data
                
            except Exception as e:
                print(f"\n⚠️  Error polling job: {e}")
            
            time.sleep(POLL_INTERVAL)
        
        print(f"\n⏱️  Timeout: Job did not complete within {MAX_POLL_TIME} seconds")
        return None
    
    def test_crew(self, crew_name: str, payload: Dict[str, Any]) -> bool:
        """Test a specific crew."""
        print(f"\n🧪 Testing {crew_name}")
        print("=" * 60)
        
        # Ensure job_key matches crew name
        payload["job_key"] = crew_name
        
        # Generate token
        self.token = self.generate_token()
        
        # Create job
        job_id = self.create_job(payload)
        if not job_id:
            return False
        
        print(f"✅ Created job: {job_id}")
        
        # Poll for completion
        result = self.poll_job(job_id)
        if not result:
            return False
        
        # Display results
        print("\n📋 Results:")
        print("-" * 60)
        
        status = result.get("status")
        if status == "completed":
            print("✅ Job completed successfully!")
            
            # Show result summary
            job_result = result.get("result", {})
            if isinstance(job_result, dict):
                # Look for memories
                memories = (job_result.get("memories") or 
                           job_result.get("created_memories") or
                           job_result.get("data", {}).get("memories"))
                
                if memories:
                    print(f"\n💾 Created {len(memories)} memories:")
                    for i, memory in enumerate(memories[:5]):  # Show first 5
                        print(f"\n  Memory {i+1}:")
                        print(f"    Entity: {memory.get('entity_name', 'N/A')}")
                        print(f"    Type: {memory.get('entity_type', 'N/A')}")
                        if 'observations' in memory:
                            print(f"    Observations: {len(memory['observations'])}")
                else:
                    # Show whatever result we got
                    print(json.dumps(job_result, indent=2)[:500] + "...")
        else:
            print(f"❌ Job failed with status: {status}")
            if result.get("error"):
                print(f"Error: {result['error']}")
        
        return status == "completed"

def main():
    parser = argparse.ArgumentParser(
        description="Test CrewAI crews via API",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument("crew_name", nargs="?", help="Name of the crew to test")
    parser.add_argument("--payload", help="Path to JSON payload file")
    parser.add_argument("--list-crews", action="store_true", help="List available crews")
    parser.add_argument("--no-cleanup", action="store_true", help="Don't stop API on exit")
    
    # Quick payload builders
    parser.add_argument("--text", help="Text content for memory_maker_crew")
    parser.add_argument("--entity", help="Entity name for entity_research_crew")
    parser.add_argument("--domain", help="Entity domain for entity_research_crew")
    
    args = parser.parse_args()
    
    # List crews
    if args.list_crews:
        print("\n📋 Available crews:")
        print("  - memory_maker_crew")
        print("  - entity_research_crew")
        print("  - book_ingestion_crew")
        print("  - contact_form")
        print("\nExample: ./test_crew.py memory_maker_crew --text 'Test content'")
        return
    
    if not args.crew_name:
        parser.print_help()
        return
    
    # Build payload
    if args.payload:
        with open(args.payload, 'r') as f:
            payload = json.load(f)
    else:
        # Build payload from arguments
        payload = {
            "job_key": args.crew_name,
            "client_user_id": "11111111-1111-1111-1111-111111111111",
        }
        
        # Crew-specific payload building
        if args.crew_name == "memory_maker_crew" and args.text:
            payload.update({
                "actor_type": "client",
                "actor_id": "11111111-1111-1111-1111-111111111111",
                "data": {
                    "text_content": args.text,
                    "metadata": {
                        "source": "test_crew.py",
                        "timestamp": datetime.now().isoformat()
                    }
                }
            })
        elif args.crew_name == "entity_research_crew" and args.entity:
            payload["data"] = {
                "entity_name": args.entity,
                "entity_domain": args.domain or "technology"
            }
        else:
            print(f"❌ Need more arguments for {args.crew_name}")
            print(f"   Use --payload or crew-specific args")
            return
    
    # Run test
    tester = CrewTester()
    
    # Set up cleanup handler
    def signal_handler(sig, frame):
        print("\n\n🛑 Interrupted by user")
        tester.cleanup()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        # Start API
        if not tester.start_api():
            return
        
        # Run test
        success = tester.test_crew(args.crew_name, payload)
        
        if success:
            print("\n✅ Test completed successfully!")
        else:
            print("\n❌ Test failed!")
        
    finally:
        if not args.no_cleanup:
            tester.cleanup()

if __name__ == "__main__":
    main()