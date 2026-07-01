# Vision Module Hardening: The "Data-Blind" Interpolator

This is the architectural draft to harden the Vision Specialist node, shifting it entirely away from qualitative y-axis visual guessing to strict mathematical pixel interpolation using a hybrid OCR extraction pipeline.

## Proposed Changes

### 1. Hybrid OCR Architecture (Local + Cloud Fallback)
To ensure cross-platform compatibility across both desktop clients and mobile deployment, we will build a resilient OCR loader that prefers local execution but seamlessly fails over to cloud compute.

#### [MODIFY] [backend/src/tools/vision.py](file:///C:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent/backend/src/tools/vision.py)
* Add `extract_axis_ratio(image_b64: str) -> dict`.
* **Logic Flow**:
  1. Detect platform/environment via `os.name` and configuration flags.
  2. **Tier 1 (Desktop Local)**: Attempt to load `pytesseract`. If Tesseract-OCR binaries are found, perform the optical extraction entirely locally to save API costs and latency.
  3. **Tier 2 (Cloud Fallback)**: If running on a mobile environment, or if local Tesseract execution throws an exception, dynamically route the image slice to a strict JSON-structured Cloud Vision API payload (e.g., Gemini 1.5 Pro Vision or Google Cloud Vision API) asking purely for OCR bounding boxes.
  4. Parse the topmost price and bottommost price, calculate $\Delta$Price and $\Delta$Pixel.
  5. Return standard Dictionary: `{'ratio': 0.05, 'ymin_price': 100.0, 'ymin_pixel': 800}`.

### 2. Environment & Configuration
We must introduce the image manipulation libraries and update configuration variables to allow override controls.

#### [MODIFY] [requirements.txt](file:///C:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent/backend/requirements.txt)
* Add `opencv-python>=4.8.0` for image numpy slicing.
* Add `pytesseract>=0.3.10` for local OCR attempts.

#### [MODIFY] [backend/.env] / Config
* Ensure we check for `VLI_FORCE_CLOUD_OCR=True/False` or dynamically infer from the UI environment.

### 3. Agent Instruction Overhaul
We need to remove the LLM's permission to guess axis values globally.

#### [MODIFY] [backend/src/prompts/vision_specialist.md](file:///C:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent/backend/src/prompts/vision_specialist.md) (or node equivalent)
* **Instruction Additions**:
  1. "You are forbidden from visually estimating prices from the axis."
  2. "When evaluating a chart, first call `extract_axis_ratio` to fetch the mathematical pixel scale."
  3. "Use your visual perception solely to locate the [Y, X] pixel coordinates of structural chart patterns, then mathematically interpolate the exact price using the interpolated ratio."

### 4. Bounding Box Interpolator Tool
We will provide a pure mathematical tool to the LLM so it doesn't try to interpolate the float decimals itself.

#### [MODIFY] [backend/src/tools/vision.py](file:///C:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent/backend/src/tools/vision.py)
* Add `interpolate_price_from_pixel(pixel_y: int, ratio_data: dict) -> float`.
* The LLM passes its visually identified pixel coordinate to the tool, and the backend handles the rigid arithmetic to return the exact price.

## Verification Plan
### Automated Tests
* **Fallback Validation**: Intentionally temporarily break the local `tesseract` path (e.g., rename the binary) to ensure the system successfully catches the error and executes the Cloud Vision fallback without crashing.
* **Accuracy Validation**: Feed the system a screenshot of a known asset without providing the ticker. 
* We will verify `extract_axis_ratio` successfully reads the high/low axis labels.
* We will ask the LLM to identify the "price of the lowest wick in the consolidation block" and verify the interpolated output matches the actual print exactly, proving the hallucination is resolved.
