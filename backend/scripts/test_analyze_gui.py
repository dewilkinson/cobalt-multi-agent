import tkinter as tk
from tkinter import scrolledtext
import threading
import httpx
import os
import sys
import time

# Ensure src path for config access
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

SYMBOLS = ["APA", "ETHUSDT", "AAPL", "MSFT", "BTCUSDT"]
API_BASE = "http://127.0.0.1:8000/api/vli"

class VLITestGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("VLI Analyze Pipeline Test")
        self.root.geometry("1400x800")
        self.root.configure(bg="#0B0F19")
        
        self.running = True
        
        # Layout
        main_frame = tk.Frame(root, bg="#0B0F19")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Left Panel (Commands/Responses)
        left_frame = tk.Frame(main_frame, bg="#131A2A", bd=1, relief=tk.SUNKEN)
        left_frame.place(relx=0, rely=0, relwidth=0.6, relheight=1)
        
        tk.Label(left_frame, text="AGENT RESPONSES & STATUS", bg="#131A2A", fg="#2196F3", font=("Consolas", 12, "bold")).pack(anchor="w", padx=5, pady=5)
        
        self.log_text = scrolledtext.ScrolledText(left_frame, bg="#0B0F19", fg="#A0AABF", font=("Consolas", 10), insertbackground="white")
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Right Panel (Telemetry)
        right_frame = tk.Frame(main_frame, bg="#131A2A", bd=1, relief=tk.SUNKEN)
        right_frame.place(relx=0.61, rely=0, relwidth=0.39, relheight=1)
        
        tk.Label(right_frame, text="VLI TELEMETRY", bg="#131A2A", fg="#00E676", font=("Consolas", 12, "bold")).pack(anchor="w", padx=5, pady=5)
        
        self.telemetry_text = scrolledtext.ScrolledText(right_frame, bg="#000000", fg="#00E676", font=("Consolas", 9))
        self.telemetry_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        
        # Start background task
        threading.Thread(target=self.run_test_loop, daemon=True).start()
        threading.Thread(target=self.run_telemetry_loop, daemon=True).start()

    def on_close(self):
        self.running = False
        self.root.destroy()
        
    def log(self, msg, color="#A0AABF"):
        self.root.after(0, self._append_log, msg, color)
        
    def _append_log(self, msg, color):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, msg + "\n", color)
        self.log_text.tag_config(color, foreground=color)
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def update_telemetry(self, raw_text):
        self.root.after(0, self._set_telemetry, raw_text)
        
    def _set_telemetry(self, raw_text):
        self.telemetry_text.config(state=tk.NORMAL)
        self.telemetry_text.delete(1.0, tk.END)
        self.telemetry_text.insert(tk.END, raw_text)
        self.telemetry_text.see(tk.END)
        self.telemetry_text.config(state=tk.DISABLED)

    def run_telemetry_loop(self):
        while self.running:
            try:
                resp = httpx.get(f"{API_BASE}/active-state", timeout=2.0)
                if resp.status_code == 200:
                    data = resp.json()
                    self.update_telemetry(data.get("telemetry_tail", ""))
            except Exception:
                pass
            time.sleep(1.0)
            
    def run_test_loop(self):
        # Explicitly clear UI boxes at the start of a new harness execution
        self.root.after(0, lambda: self.log_text.config(state=tk.NORMAL))
        self.root.after(0, lambda: self.log_text.delete(1.0, tk.END))
        self.root.after(0, lambda: self.log_text.config(state=tk.DISABLED))

        for symbol in SYMBOLS:
            if not self.running: return
            
            self.log(f"\n[{time.strftime('%H:%M:%S')}] DIRECTIVE ISSUED: Analyze {symbol}", "#FFFFFF")
            self.log(f">> Awaiting intelligence report... (max 65s)", "#888888")
            
            # Clear Telemetry File before execution
            try:
                from src.config.vli import get_vli_path
                telemetry_file = get_vli_path("VLI_Raw_Telemetry.md")
                if os.path.exists(telemetry_file):
                    with open(telemetry_file, "w", encoding="utf-8") as f:
                        f.write(f"# VLI Session Telemetry Log\n### [{time.strftime('%H:%M:%S')}] TEST HARNESS: New Session Triggered for {symbol}\n---\n")
            except Exception as e:
                self.log(f"[WARNING] Could not clear telemetry: {e}", "#FFCA28")
                
            start = time.time()
            try:
                # Use a robust 125s timeout to allow Gemini rate limit `AsyncRetrying` (4s -> 8s -> 16s + 60s backend orchestrator limit)
                resp = httpx.post(f"{API_BASE}/action-plan", json={"text": f"Analyze {symbol}"}, timeout=125.0)
                elapsed = time.time() - start
                
                if resp.status_code == 200:
                    data = resp.json()
                    
                    if isinstance(data, dict):
                        report = data.get("response", data.get("report", str(data)))
                        status = data.get("status", "unknown")
                        error_details = data.get("error_details")
                    else:
                        report = str(data)
                        status = "unknown"
                        error_details = None
                        
                    self.log(f"[{elapsed:.1f}s] Response received.", "#FFCA28")
                    self.log("-" * 40)
                    self.log(report[:1000] + ("\n...[TRUNCATED FOR UI]" if len(report) > 1000 else ""))
                    self.log("-" * 40)
                    
                    # Write status code cleanly to telemetry window
                    self.update_telemetry(f"\n\n>>> API RESPONSE STATUS: [{status.upper()}] <<<\n")
                    
                    if status == "TIMEOUT":
                        self.log(f" TEST ABORTED (TIMEOUT): {error_details or 'Agent processing timed out.'}", "#FF3D00")
                        self.log("Pipeline evaluation stopped.", "#FF3D00")
                        return

                    if status == "FAILED":
                        self.log(f" TEST ABORTED: {error_details or 'Unknown API Error'}", "#FF3D00")
                        self.log("Pipeline evaluation stopped.", "#FF3D00")
                        return
                        
                    if len(report) > 150:
                        self.log(f" STAGE PASSED: {symbol}\n", "#00E676")
                    else:
                        self.log(f" TEST ABORTED: Invalid/short report for {symbol} (Length: {len(report)})", "#FF3D00")
                        self.log("Pipeline evaluation stopped.", "#FF3D00")
                        return
                else:
                    self.log(f" TEST ABORTED: Header/Network Error (HTTP {resp.status_code})", "#FF3D00")
                    return
            except httpx.ReadTimeout:
                self.log(f" TEST ABORTED: Agent execution timed out after {time.time() - start:.1f}s for {symbol}", "#FF3D00")
                return
            except Exception as e:
                self.log(f" TEST ABORTED: Exception raised: {e}", "#FF3D00")
                return
                
            time.sleep(2)
            
        self.log(f"\n ALL STAGES VERIFIED. PIPELINE SUCCESSFUL.", "#00E676")

if __name__ == "__main__":
    # Hide the default tk root window so we only see our styled one
    root = tk.Tk()
    app = VLITestGUI(root)
    root.mainloop()
