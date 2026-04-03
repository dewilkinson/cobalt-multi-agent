import sys
import os
import traceback
import asyncio

# Ensure project root is in path
sys.path.insert(0, os.getcwd())

print("--- VLI Diagnostic Start ---")
try:
    import src.tools.finance as finance
    print(f"Finance module file: {finance.__file__}")
    print(f"Attributes in finance: {[a for a in dir(finance) if not a.startswith('__')]}")
    print(f"Has 'yf': {'yf' in dir(finance)}")
    
    # Try to access it
    if 'yf' in dir(finance):
        import yfinance
        print(f"yf is yfinance: {finance.yf is yfinance}")
    
    # Check for circular deps
    print(f"Loaded modules in src.tools: {[m for m in sys.modules if m.startswith('src.tools')]}")

    from tests.unit.tools import test_scout_resonance as test_mod
    print("Test module imported successfully.")
    
except Exception as e:
    print(f"DIAGNOSTIC ERROR: {e}")
    traceback.print_exc()

print("--- VLI Diagnostic End ---")
