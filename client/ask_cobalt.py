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
            
            timestamp_time = datetime.now().strftime("%H:%M:%S")
            ai_header = f"<strong>Agent</strong> <span style=\"font-size: 64%; font-weight: normal; font-style: italic;\">{timestamp_time}</span>:"

            if has_double_newline or has_multiple_paragraphs:
                # Use first paragraph as summary (skipping headers)
                clean_payload = re.sub(r'^#+ .*?(\n+|$)', '', payload, flags=re.MULTILINE).strip()
                summary_text = clean_payload.split("\n\n")[0]
                if "<p>" in summary_text:
                    match = re.search(r'<p>(.*?)</p>', summary_text, re.DOTALL)
                    if match:
                        summary_text = match.group(1)
                
                # Strip markdown-specific characters from the summary
                summary_text = re.sub(r'[*_#`\[\]]', '', summary_text).strip()
                summary_text = re.sub(r'^[ \t]*[-*+][ \t]+', '', summary_text)
                
                if not summary_text or len(summary_text) < 10:
                    summary_text = "Detailed Analysis"
                
                if len(summary_text) > 120:
                    summary_text = summary_text[:117] + "..."

                # Wrap in native Obsidian callout for perfect containment in all view modes
                # The "-" makes it collapsed by default. The type "INFO" is standard.
                # We still use the inner div for our custom typography.
                payload = f"> [!INFO]- Show Detail: {summary_text}\n> <div style=\"color: #999; font-size: 80%; border-left: 2px solid #333; padding-left: 10px;\">\n> \n{re.sub('(?m)^', '> ', response.strip())}\n> \n> </div>"
                ai_entry = f"{ai_header}\n{payload}"
                print(f"[INFO] Long response wrapped in native Obsidian callout toggle.")
            else:
                ai_entry = f"{ai_header}\n<div style=\"color: #999; font-size: 80%;\">\n{payload}\n</div>"
            
            # Replace the unique placeholder using Regex for robustness (handles potential line-wrapping)
            placeholder_pattern = rf'<span[^>]+?id\s*=\s*["\']{placeholder_id}["\'].*?</span>'
            if re.search(placeholder_pattern, content, re.DOTALL):
                new_content = re.sub(placeholder_pattern, ai_entry, content, count=1, flags=re.DOTALL)
                with open(note_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                print(f"\n[INFO] Cobalt Multiagent response logged to Obsidian (replaced {placeholder_id}).")
            else:
                print(f"\n[WARNING] Could not find placeholder {placeholder_id} in log. Prepending response.")
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
