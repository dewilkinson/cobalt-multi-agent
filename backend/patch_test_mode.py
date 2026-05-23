import os

path = r'C:\Users\rende\.gemini\antigravity\worktrees\cobalt-multi-agent\backend\src\server\routes\scanner.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

target = """                try:
                    # Direct logic invocation to bypass StructuredTool wrapper
                    p2_res_str = await _run_activity_pulse_impl(strategy_config="{}", watchlist=json.dumps(p1_symbols, cls=NpEncoder))
                    p2_data = json.loads(p2_res_str)
                    p2_candidates = p2_data.get("candidates", [])
                    yield f"data: {json.dumps(sanitize_data({'type': 'telemetry', 'msg': f'Phase 2 complete. High-probability Candidates: {len(p2_candidates)}'}), cls=NpEncoder)}\\n\\n"
                except Exception as e:"""

repl = """                try:
                    # [TEST MODE] Direct logic invocation to bypass StructuredTool wrapper
                    # p2_res_str = await _run_activity_pulse_impl(strategy_config="{}", watchlist=json.dumps(p1_symbols, cls=NpEncoder))
                    # p2_data = json.loads(p2_res_str)
                    # p2_candidates = p2_data.get("candidates", [])
                    
                    # [TEST MODE] Inject Phase 1 straight into Phase 2 output
                    yield f"data: {json.dumps(sanitize_data({'type': 'telemetry', 'msg': 'TEST MODE ENGAGED. Bypassing Phase 2 Activity Pulse...'}), cls=NpEncoder)}\\n\\n"
                    p2_candidates = [{"symbol": d["symbol"], "sortino": d.get("sortino", 0.0), "heat_score": 100, "grade": d.get("grade", "A")} for d in p1_details]
                    yield f"data: {json.dumps(sanitize_data({'type': 'telemetry', 'msg': f'Phase 2 complete. Diagnostic Candidates Displayed: {len(p2_candidates)}'}), cls=NpEncoder)}\\n\\n"
                except Exception as e:"""

if target in content:
    content = content.replace(target, repl)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Injected test mode bypass.")
else:
    print("Target not found.")
