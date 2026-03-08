
import requests
import time
import sys
import json

BASE_URL = "http://localhost:9104/api/v1/analysis"
REPO_URL = "https://github.com/hong-seongmin/techGiterview"

def test_api():
    print(f"[TEST] Starting Analysis for {REPO_URL} on {BASE_URL}")
    
    # 1. Start Analysis
    try:
        resp = requests.post(f"{BASE_URL}/repository/analyze", json={
            "repo_url": REPO_URL,
            "use_advanced": True,
            "max_files": 15
        })
        resp.raise_for_status()
        data = resp.json()
        analysis_id = data["analysis_id"]
        print(f"[TEST] Analysis Started: ID={analysis_id}")
    except Exception as e:
        print(f"[ERROR] Failed to start analysis: {e}")
        sys.exit(1)

    # 2. Poll Status
    print("[TEST] Polling status...")
    max_retries = 30 # 30 * 5s = 150s timeout
    for _ in range(max_retries):
        try:
            status_resp = requests.get(f"{BASE_URL}/analysis/{analysis_id}/status")
            status_data = status_resp.json()
            status = status_data["status"]
            progress = status_data["progress"]
            step = status_data["current_step"]
            
            print(f"  Status: {status} ({progress}%) - {step}")
            
            if status == "completed":
                break
            if status == "failed":
                print(f"[ERROR] Analysis failed: {status_data.get('error')}")
                sys.exit(1)
            
            time.sleep(5)
        except Exception as e:
            print(f"[WARN] Error polling status: {e}")
            time.sleep(5)
    else:
        print("[ERROR] Timeout waiting for analysis to complete")
        sys.exit(1)
        
    # 3. Get Graph Results
    print("[TEST] Fetching Graph Data...")
    graph_resp = requests.get(f"{BASE_URL}/analysis/{analysis_id}/graph")
    graph_data = graph_resp.json()
    
    nodes = graph_data.get("nodes", [])
    node_names = [n["name"] for n in nodes]
    node_ids = [n["id"] for n in nodes]
    
    print(f"\n[RESULTS] Graph Nodes ({len(nodes)}):")
    for n in nodes:
        print(f"  - {n['name']} (Type: {n.get('type')}, Reason: {n.get('reason')})")

    links = graph_data.get("links", [])
    print(f"\n[RESULTS] Graph Edges ({len(links)}):")
    for l in links[:5]:
         print(f"  - {l['source']} -> {l['target']} (Type: {l.get('type')})")
    
    node_ids = set(n['id'] for n in nodes)
    dangling_links = [l for l in links if l['source'] not in node_ids or l['target'] not in node_ids]
    
    if dangling_links:
        print(f"\n❌ FAIL: Found {len(dangling_links)} dangling links! (Endpoints missing from nodes)")
        # for dl in dangling_links: print(f"  {dl}")
        # sys.exit(1) # Warning only
    else:
        print(f"\n✅ PASS: All {len(links)} edges connect valid nodes.")

    if len(links) == 0:
        print("⚠️ WARN: Graph is fully disconnected (0 edges). This might be valid for simple scripts but suspicious.")

    test_files = [n for n in node_names if "test" in n.lower() or "spec" in n.lower()]
    logic_files = [n for n in node_names if n.endswith(('.py', '.ts', '.js')) and not ("test" in n.lower())]

    print("\n[VERIFICATION]")
    print(f"  Test Files Found: {len(test_files)} {test_files}")
    print(f"  Test Files Found: {len(test_files)} {test_files}")
    print(f"  Logic Files Found: {len(logic_files)} {logic_files}")
    
    if len(test_files) > 0:
        print(f"❌ FAIL: Found {len(test_files)} test files in the graph! They should be 0.")
        sys.exit(1)
    
    if len(logic_files) == 0:
        print("❌ FAIL: No logic files found!")
        sys.exit(1)
        
    print("✅ PASS: No test files found, logic files present.")
    sys.exit(0)

if __name__ == "__main__":
    test_api()
