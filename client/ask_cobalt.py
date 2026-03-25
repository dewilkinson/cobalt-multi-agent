# ---------------------------------------------------------------------------
# IMPLEMENTATION NOTE: Bridge Architecture
# ---------------------------------------------------------------------------
# We are currently using an HTTP bridge (REST API) to communicate between 
# the local environment (Gemini/Obsidian) and the remote multi-agent backend.
# This choice provides immediate responsiveness and a simpler initial setup.
# 
# However, for enhanced security, auditability, and offline persistence,
# a move to a private GitHub bridge (Asynchronous Git Bridge) may be
# appropriate in the future to align with our security-first philosophy.
# ---------------------------------------------------------------------------
import sys
import os
import httpx
import json
import re
import uuid
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
API_URL = os.getenv("COBALT_API_URL", "https://bluesec-multiagent-backend.up.railway.app/api/chat/stream")
API_KEY = os.getenv("COBALT_API_KEY", "")
OBSIDIAN_VAULT_PATH = os.getenv("OBSIDIAN_VAULT_PATH", "")
OBSIDIAN_NOTE_NAME = os.getenv("OBSIDIAN_NOTE_NAME", "Cobalt Multiagent_Log.md")

# SnapTrade Settings (Client-Side)
SNAPTRADE_SETTINGS = {
    "SNAPTRADE_CLIENT_ID": os.getenv("SNAPTRADE_CLIENT_ID", ""),
    "SNAPTRADE_CONSUMER_KEY": os.getenv("SNAPTRADE_CONSUMER_KEY", ""),
    "SNAPTRADE_USER_ID": os.getenv("SNAPTRADE_USER_ID", ""),
    "SNAPTRADE_USER_SECRET": os.getenv("SNAPTRADE_USER_SECRET", ""),
    "MOCK_BROKER": os.getenv("MOCK_BROKER", "false")
}

# Obsidian Settings (Client-Side)
OBSIDIAN_SETTINGS = {
    "OBSIDIAN_VAULT_PATH": os.getenv("OBSIDIAN_VAULT_PATH", ""),
    "OBSIDIAN_NOTE_NAME": os.getenv("OBSIDIAN_NOTE_NAME", "Cobalt Multiagent_Log.md"),
    "OBSIDIAN_JOURNAL_DIR": os.getenv("OBSIDIAN_JOURNAL_DIR", "Journals")
}

def _write_prepend_to_obsidian(entry: str):
    """Internal helper to prepend an entry to the Obsidian log note."""
    if not OBSIDIAN_VAULT_PATH:
        return
        
    note_path = os.path.join(OBSIDIAN_VAULT_PATH, OBSIDIAN_NOTE_NAME)
    
    if not os.path.exists(OBSIDIAN_VAULT_PATH):
        print(f"\n[WARNING] Obsidian vault path '{OBSIDIAN_VAULT_PATH}' does not exist.")
        return
        
    try:
        content = ""
        if os.path.exists(note_path):
            with open(note_path, 'r', encoding='utf-8') as f:
                content = f.read()
        
        with open(note_path, 'w', encoding='utf-8') as f:
            f.write(entry + content)
    except Exception as e:
        print(f"\n[ERROR] Failed to write to Obsidian note: {e}")

def log_user_request(prompt: str, placeholder_id: str):
    timestamp_time = datetime.now().strftime("%H:%M:%S")
    header = f"<strong>User</strong> <span style=\"font-size: 64%; font-weight: normal; font-style: italic;\">{timestamp_time}</span>:"
    entry = f"<div style=\"font-size: 65%;\">\n\n{header}\n<div style=\"color: #999; font-size: 80%;\">\n{prompt}\n</div>\n\n<span id=\"{placeholder_id}\" style=\"color: #00ffff; font-size: 80%;\"><strong>Awaiting response...</strong></span>\n\n---\n\n</div>\n\n"
    _write_prepend_to_obsidian(entry)
    print(f"\n[INFO] User request logged to Obsidian. (ID: {placeholder_id})")

def log_cobalt_response(response: str, placeholder_id: str):
    if not OBSIDIAN_VAULT_PATH:
        return
        
    note_path = os.path.join(OBSIDIAN_VAULT_PATH, OBSIDIAN_NOTE_NAME)
    try:
        if os.path.exists(note_path):
            with open(note_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check for multi-paragraph response (extraction logic)
            payload = response.strip()
            # Detect multi-paragraph if there are double newlines OR multiple <p> tags
            has_double_newline = payload.count("\n\n") > 0
            has_multiple_paragraphs = payload.count("<p>") > 1 or (payload.count("<p>") == 1 and "</p>" in payload and len(payload.split("</p>")[1].strip()) > 0)
            
            if has_double_newline or has_multiple_paragraphs:
                res_timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
                filename = f"CMA_Response_{res_timestamp}.md"
                # Use the same folder as the log note
                rel_folder = os.path.dirname(OBSIDIAN_NOTE_NAME)
                abs_folder = os.path.join(OBSIDIAN_VAULT_PATH, rel_folder)
                res_path = os.path.join(abs_folder, filename)
                
                with open(res_path, 'w', encoding='utf-8') as f:
                    f.write(response)
                
                # Use first paragraph as summary (skipping headers)
                clean_payload = re.sub(r'^#+ .*?(\n+|$)', '', payload, flags=re.MULTILINE).strip()
                summary = clean_payload.split("\n\n")[0]
                if "<p>" in summary:
                    # If it uses <p> tags, try to extract the first one
                    match = re.search(r'<p>(.*?)</p>', summary, re.DOTALL)
                    if match:
                        summary = match.group(0) # Keep tags for rendering
                
                # If summary is still empty or too short, fallback to first block
                if not summary or len(summary) < 10:
                    summary = payload.split("\n\n")[0]
                
                # Use HTML link for absolute file URL to ensure it renders inside the div
                file_url = f"file:///{res_path.replace('\\', '/')}"
                payload = f"{summary}<br><br><a href=\"{file_url}\">Full Response</a>"
                print(f"[INFO] Long response extracted with summary. Linked via: {file_url}")

            timestamp_time = datetime.now().strftime("%H:%M:%S")
            ai_header = f"<strong>Agent</strong> <span style=\"font-size: 64%; font-weight: normal; font-style: italic;\">{timestamp_time}</span>:"
            ai_entry = f"{ai_header}\n<div style=\"color: #999; font-size: 80%;\">\n{payload}\n</div>"
            
            # Replace the unique placeholder
            placeholder = f"<span id=\"{placeholder_id}\" style=\"color: #00ffff; font-size: 80%;\"><strong>Awaiting response...</strong></span>"
            if placeholder in content:
                new_content = content.replace(placeholder, ai_entry)
                with open(note_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                print(f"\n[INFO] Cobalt Multiagent response logged to Obsidian.")
            else:
                print(f"\n[WARNING] Could not find placeholder {placeholder_id} in log. Appending instead.")
                _write_prepend_to_obsidian(f"<div style=\"font-size: 65%;\">\n\n{ai_entry}\n\n---\n\n</div>\n\n")

    except Exception as e:
        print(f"\n[ERROR] Failed to update Obsidian response: {e}")

def main():
    if len(sys.argv) < 2:
        print("Usage: python ask_cobaltmultiagent.py <prompt>")
        sys.exit(1)
        
    prompt = " ".join(sys.argv[1:])
    placeholder_id = f"cma-{uuid.uuid4().hex[:8]}"
    
    # Immediately log the user request
    log_user_request(prompt, placeholder_id)
    
    payload = {
        "messages": [{"role": "user", "content": prompt}],
        "auto_accepted_plan": True,  # Automatically proceed with the research plan
        "snaptrade_settings": SNAPTRADE_SETTINGS,
        "obsidian_settings": OBSIDIAN_SETTINGS,
    }

    try:
        print(f"Sending request to Cobalt Multiagent API ({API_URL})...\n")
        full_response_chunks = []
        seen_chunks = set() # To prevent duplicates if the stream repeats chunks
        
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
                            # Support both reporter (research) and coordinator (greetings/simple info)
                            if content and agent in ["reporter", "coordinator"]:
                                # Aggressive deduplication: skip if exactly seen, or if it repeats the end of our current buffer
                                current_full_text = "".join(full_response_chunks)
                                if content not in seen_chunks and not current_full_text.endswith(content):
                                    print(content, end="", flush=True)
                                    full_response_chunks.append(content)
                                    seen_chunks.add(content)
                        except json.JSONDecodeError:
                            pass
                            
        final_answer = "".join(full_response_chunks)
        
        print("\n\n----------------------------------------")
        
        # Save response to obsidian
        if final_answer.strip():
            log_cobalt_response(final_answer, placeholder_id)
        else:
            print("\n[WARNING] Received an empty response. Not logging response to Obsidian.")

    except httpx.ReadTimeout:
        print(f"\n[ERROR] Request timed out. The Cobalt Multiagent server took too long to respond.")
    except Exception as e:
        print(f"\n[ERROR] Request failed: {e}")

if __name__ == "__main__":
    main()
