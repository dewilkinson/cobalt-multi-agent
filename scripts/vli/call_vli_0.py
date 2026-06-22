import sys
import json
import requests

URL = 'http://127.0.0.1:8000/api/vli/action-plan'
HEADERS = {'Content-Type': 'application/json'}

def main():
    if len(sys.argv) < 2:
        print("Usage: python call_vli.py <prompt>")
        sys.exit(1)
        
    prompt = " ".join(sys.argv[1:])
    
    # Determine raw vs direct overrides loosely from the prompt text
    # (The backend regex handles --RAW, but we want to mirror the frontend flags if necessary)
    raw_data_mode = "--RAW" in prompt.upper() or ("RAW" in prompt.upper() and ("SMC" in prompt.upper() or "DATA" in prompt.upper()))
    direct_mode = False
    
    # Send the raw request
    payload = {
        'text': prompt,
        'raw_data_mode': raw_data_mode,
        'direct_mode': direct_mode,
        'is_action_plan': False
    }
    
    try:
        response = requests.post(URL, headers=HEADERS, json=payload, timeout=120.0)
        try:
            data = response.json()
            if 'response' in data:
                resp = data['response']
                if raw_data_mode and (resp.startswith('[') or resp.startswith('{')):
                    import uuid, os
                    filename = f"vli_payload_{uuid.uuid4().hex[:6]}.json"
                    
                    # Ensure tmp directory exists
                    out_dir = os.path.abspath("tmp")
                    os.makedirs(out_dir, exist_ok=True)
                    
                    abs_path = os.path.join(out_dir, filename)
                    with open(abs_path, 'w', encoding='utf-8') as f:
                        f.write(resp)
                        
                    uri = abs_path.replace('\\', '/')
                    print(f"Returned [{filename}](file:///{uri})")
                else:
                    print(resp)
            else:
                print(json.dumps(data, indent=2))
        except BaseException:
            print(response.text)
            
    except requests.exceptions.ConnectionError:
        print("? Error: Could not connect to VLI Backend. Is the Uvicorn server running on port 8000?")
    except Exception as e:
        print(f"? Error: {e}")

if __name__ == '__main__':
    main()
