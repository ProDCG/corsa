import requests
import json
import time

def test_simhub():
    # Attempting to fetch from SimHub Web API
    props = [
        "DataCorePlugin.GameData.SpeedKmh",
        "DataCorePlugin.GameData.Rpms",
        "DataCorePlugin.GameData.Gear",
        "DataCorePlugin.GameData.Status"
    ]
    url = f"http://127.0.0.1:8888/api/getproperties?properties={','.join(props)}"
    
    print(f"--- SIMHUB DIAGNOSTIC ---")
    print(f"Targeting: {url}")
    
    try:
        start_time = time.time()
        r = requests.get(url, timeout=2.0)
        end_time = time.time()
        
        print(f"Status Code: {r.status_code}")
        print(f"Response Time: {round((end_time - start_time)*1000, 2)}ms")
        
        if r.status_code == 200:
            data = r.json()
            print("\nSUCCESS! Received Data:")
            print(json.dumps(data, indent=4))
            
            # Check for "null" values
            nulls = [k for k, v in data.items() if v is None]
            if nulls:
                print("\nWARNING: These properties returned null (check spelling):")
                for n in nulls: print(f" - {n}")
        else:
            print(f"\nERROR: Server returned {r.status_code}")
            print(r.text)
            
    except Exception as e:
        print(f"\nCRITICAL FAILURE: Could not connect to SimHub.")
        print(f"Error Detail: {e}")
        print("\nPossible fixes:")
        print("1. Check if SimHub 'Web Server' is enabled in Settings.")
        print("2. Ensure port 8888 is not blocked by Windows Firewall.")
        print("3. Try opening http://127.0.0.1:8888 in a browser manually.")

if __name__ == "__main__":
    test_simhub()
