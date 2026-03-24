import sys
import os
import httpx
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
API_URL = os.getenv("COBALT_API_URL", "https://bluesec-multiagent-backend.up.railway.app/api/chat/stream")
API_KEY = os.getenv("COBALT_API_KEY", "")
OBSIDIAN_VAULT_PATH = os.getenv("OBSIDIAN_VAULT_PATH", "")
OBSIDIAN_NOTE_NAME = os.getenv("OBSIDIAN_NOTE_NAME", "Cobalt Multiagent_Log.md")

def append_to_obsidian(prompt: str, response: str):
    if not OBSIDIAN_VAULT_PATH:
        print("\n[INFO] OBSIDIAN_VAULT_PATH not configured. Skipping Obsidian logging.")
        return
        
    note_path = os.path.join(OBSIDIAN_VAULT_PATH, OBSIDIAN_NOTE_NAME)
    
    if not os.path.exists(OBSIDIAN_VAULT_PATH):
        print(f"\n[WARNING] Obsidian vault path '{OBSIDIAN_VAULT_PATH}' does not exist.")
        return
        
    try:
        with open(note_path, 'a', encoding='utf-8') as f:
            f.write(f"\n\n### User:\n{prompt}\n")
            f.write(f"\n### Cobalt Multiagent:\n{response}\n")
            f.write("---\n")
        print(f"\n[INFO] Successfully logged conversation to {note_path}")
    except Exception as e:
        print(f"\n[ERROR] Failed to write to Obsidian note: {e}")

def main():
    if len(sys.argv) < 2:
        print("Usage: python ask_cobaltmultiagent.py <prompt>")
        sys.exit(1)
        
    prompt = " ".join(sys.argv[1:])
    
    payload = {
        "messages": [{"role": "user", "content": prompt}],
        "auto_accepted_plan": True,  # Automatically proceed with the research plan
    }

    try:
        print(f"Sending request to Cobalt Multiagent API ({API_URL})...\n")
        full_response = []
        
        headers = {}
        if API_KEY:
            headers["X-API-Key"] = API_KEY
            
        with httpx.stream("POST", API_URL, json=payload, headers=headers, timeout=120.0) as r:
            if r.status_code == 401:
                print("\n[ERROR] Unauthorized: Invalid X-API-Key provided.")
                return
            r.raise_for_status()
            current_event = None
            for line in r.iter_lines():
                if line.startswith("event: "):
                    current_event = line[len("event: "):].strip()
                elif line.startswith("data: "):
                    data_str = line[len("data: "):]
                    if data_str and current_event == "message_chunk":
                        try:
                            data = json.loads(data_str)
                            content = data.get("content", "")
                            agent = data.get("agent", "")
                            # Only print the final response from the reporter agent
                            if content and agent == "reporter":
                                print(content, end="", flush=True)
                                full_response.append(content)
                        except json.JSONDecodeError:
                            pass
                            
        final_answer = "".join(full_response)
        
        print("\n\n----------------------------------------")
        
        # Save to obsidian
        if final_answer.strip():
            append_to_obsidian(prompt, final_answer)
        else:
            print("\n[WARNING] Received an empty response. Not logging to Obsidian.")

    except httpx.ReadTimeout:
        print(f"\n[ERROR] Request timed out. The Cobalt Multiagent server took too long to respond.")
    except Exception as e:
        print(f"\n[ERROR] Request failed: {e}")

if __name__ == "__main__":
    main()
