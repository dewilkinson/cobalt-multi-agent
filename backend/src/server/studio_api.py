import asyncio
import base64
import json
import logging
from pathlib import Path
from typing import Dict, Any

from fastapi import APIRouter, HTTPException
from langchain_core.messages import HumanMessage
from src.llms.llm import get_llm_by_type
from src.tools.playwright_capture import PlaywrightCapturer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/studio", tags=["studio"])

STUDIO_URL = "https://one.google.com/ai/activity?utm_source=antigravity&utm_medium=web&utm_campaign=argon_settings_page_ai_credits_activity_page&email=dewilkinson71%40gmail.com&pli=1&g1_landing_page=0"

capturer = PlaywrightCapturer()

@router.get("/login")
async def open_studio_login():
    """Opens the Google AI Studio login page in a headful browser for one-time setup."""
    try:
        # Launch headful Playwright instance for login
        # This will block until the browser is manually closed (using asyncio.Event)
        # We start it in a background task so we don't hang the FastAPI response
        asyncio.create_task(capturer.launch_headful_login(STUDIO_URL))
        return {"status": "success", "message": "Login browser launched. Please log in and close it manually."}
    except Exception as e:
        logger.error(f"Failed to launch login browser: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to launch login: {str(e)}")

@router.get("/credits")
async def get_credits():
    """Captures the screen headlessly and extracts credits using Gemini Vision."""
    try:
        # 1. Take a headless snapshot using the persistent session
        b64_image = await capturer.capture_screenshot_headless(STUDIO_URL, wait_seconds=10)
        
        # 2. Get the vision model
        vision_llm = get_llm_by_type("vision")
        
        # 3. Prepare the prompt
        prompt = (
            "Look at this screenshot of the Google AI Studio activity page. "
            "Extract the 'Monthly credits' and 'Additional credits' remaining. "
            "Return them as a JSON object: {'monthly': value, 'additional': value, 'total': value}. "
            "The values should be numbers (if '25.0', return 25.0). "
            "If the page shows a login button, return {'error': 'Authentication required. Please click Login to Studio.'}. "
            "Return ONLY the JSON. If nothing is found, return {'monthly': 'Unknown', 'additional': 'Unknown', 'total': 'Unknown'}."
        )
        
        # 4. Invoke the model
        message = HumanMessage(
            content=[
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": b64_image}}
            ]
        )
        
        response = await vision_llm.ainvoke([message])
        
        # 5. Parse the JSON result
        content = response.content.strip()
        # Remove markdown code blocks
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
            
        try:
            credits_info = json.loads(content)
            return credits_info
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse LLM response as JSON: {content}")
            return {"raw_response": content, "status": "partial_success"}
            
    except Exception as e:
        logger.error(f"Error extracting credits headlessly: {e}")
        raise HTTPException(status_code=500, detail=f"Headless extraction failed: {str(e)}")

@router.get("/context")
async def get_context_memory():
    """Reads the current conversation log and calculates the token usage against the 1M limit."""
    conversation_id = "7823826e-4104-4f94-9860-88a3bef2e8e5"
    log_path = Path(f"C:/Users/rende/.gemini/antigravity/brain/{conversation_id}/.system_generated/logs/overview.txt")
    
    if not log_path.exists():
        # Fallback search if the path structure is different
        logger.warning(f"Log path {log_path} not found. Returning estimate.")
        return {"used": 45000, "limit": 1000000, "percent": 4.5, "status": "estimated"}

    try:
        with open(log_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        # 2. Get the model to count tokens
        # We use the langchain get_num_tokens for speed and to avoid extra API calls
        from langchain_google_genai import ChatGoogleGenerativeAI
        import os
        
        model = ChatGoogleGenerativeAI(
            model="gemini-1.5-flash",
            google_api_key=os.environ.get("BASIC_MODEL__api_key")
        )
        
        token_count = model.get_num_tokens(content)
        limit = 1000000
        
        return {
            "used": token_count,
            "limit": limit,
            "percent": round((token_count / limit) * 100, 2),
            "status": "synchronized"
        }
    except Exception as e:
        logger.error(f"Error calculating context memory: {e}")
        return {"used": 0, "limit": 1000000, "percent": 0, "error": str(e)}
