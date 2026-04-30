import os
import sys

# Path setup
base_path = os.path.abspath(os.path.join(os.path.dirname(__file__)))
sys.path.append(base_path)

from src.config.analyst import get_analyst_keywords
from src.prompts.template import apply_prompt_template


def test_planner_render():
    print("--- Testing Planner Render with Keywords ---")

    # Mock state
    state = {"messages": [], "plan_iterations": 0}

    # Get keywords
    analyst_keywords = ", ".join(get_analyst_keywords())
    print(f"Keywords: {analyst_keywords}")

    # Add to state
    state_for_prompt = {**state, "ANALYST_KEYWORDS": analyst_keywords}

    # Render
    try:
        messages = apply_prompt_template("planner", state_for_prompt)
        print("\n--- RENDERED PLANNER PROMPT (First 500 chars) ---")
        print(messages[0]["content"][:500])

        # Check if keywords are there
        if analyst_keywords[:20] in messages[0]["content"]:
            print("\nSUCCESS: Keywords found in rendered prompt.")
        else:
            print("\nFAILURE: Keywords NOT found in rendered prompt.")

    except Exception as e:
        print(f"RENDER ERROR: {e}")


if __name__ == "__main__":
    test_planner_render()
