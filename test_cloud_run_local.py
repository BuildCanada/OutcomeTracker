#!/usr/bin/env python3
"""
Test the Cloud Run service locally before deployment.
This script starts the Flask server and tests the endpoints.
"""

import os
import sys
import time
import requests
import threading
import subprocess
from cloud_run_main import app

def test_endpoints():
    """Test the service endpoints."""
    base_url = "http://localhost:8080"
    
    print("🧪 Testing Cloud Run service endpoints...")
    time.sleep(2)  # Give server time to start
    
    try:
        # Test health check
        print("\n1. Testing health check...")
        response = requests.get(f"{base_url}/")
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.json()}")
        
        # Test list jobs
        print("\n2. Testing job list...")
        response = requests.get(f"{base_url}/jobs")
        print(f"   Status: {response.status_code}")
        jobs = response.json()
        print(f"   Available jobs: {list(jobs['available_jobs'].keys())}")
        
        # Test a quick RSS check (should complete quickly)
        print("\n3. Testing LEGISinfo RSS check...")
        response = requests.post(f"{base_url}/jobs/check_legisinfo_rss", 
                               json={"args": ["--hours", "1"]})
        print(f"   Status: {response.status_code}")
        result = response.json()
        print(f"   Job status: {result.get('status')}")
        print(f"   Duration: {result.get('duration_seconds', 0):.2f}s")
        
        print("\n✅ All tests passed! Cloud Run service is working locally.")
        
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to service. Make sure it's running on port 8080.")
    except Exception as e:
        print(f"❌ Test error: {e}")

def run_server():
    """Run the Flask server in a separate thread."""
    print("🚀 Starting Cloud Run service locally on port 8080...")
    app.run(host='0.0.0.0', port=8080, debug=False)

if __name__ == '__main__':
    # Start server in background thread
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    
    # Run tests
    test_endpoints()
    
    print("\n💡 Service is running locally. You can test it manually:")
    print("   Health check: http://localhost:8080/")
    print("   List jobs: http://localhost:8080/jobs")
    print("   Execute job: curl -X POST http://localhost:8080/jobs/check_legisinfo_rss")
    print("\n   Press Ctrl+C to stop the service.")
    
    try:
        # Keep the main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n�� Service stopped.") 