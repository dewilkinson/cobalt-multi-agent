import sys
import os
# Adjust path to include the backend root
sys.path.append(r'c:\github\cobalt-multi-agent\backend')

from src.prompts.template import apply_prompt_template
from langchain_core.messages import HumanMessage

state = {
    "messages": [HumanMessage(content="test")], 
    "intent": "SENTIMENT_REPORT",
    "MACRO_INDICATORS": "TEST_MACRO" # Optional, should be handled by my fallback too
}

try:
    print("Starting test render...")
    msgs = apply_prompt_template("synthesizer", state)
    print("\n--- RENDER SUCCESS ---")
    content = msgs[0].content
    if "twitter.com" in content:
        print("SOCIAL_SOURCES detected in output.")
    if "TEST_MACRO" in content or "VIX" in content:
        print("MACRO_INDICATORS detected in output.")
    # print(content[:500])
except Exception as e:
    print(f"\n--- RENDER FAILED ---")
    print(e)
    import traceback
    traceback.print_exc()
