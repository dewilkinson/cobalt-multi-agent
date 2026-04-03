import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import re

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8089", "http://localhost:8089"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class VLIActionPlanRequest(BaseModel):
    text: str
    image: str | None = None
    is_action_plan: bool = False

@app.post("/api/vli/action-plan")
async def post_vli_action_plan(request: VLIActionPlanRequest):
    print("----------------------------------------")
    print(f"DEBUG INCOMING REQUEST: {request.text}")
    print(f"IS_ACTION_PLAN: {request.is_action_plan}")
    print("----------------------------------------")

    # Mock extract logic
    alerts = []
    text = request.text.lower()
    if "futures" in text and "watchlist" in text:
        print("[SUCCESS] CONDITION MET: Triggering 'Futures Watchlist' dynamic panel.")
    
    symbols = re.findall(r"\$([A-Z]{1,5})", request.text)
    print(f"[SUCCESS] TICKERS EXTRACTED: {set(symbols)}")
    
    return {"message": "Success", "response": "Visual directives received and processed in debug mode."}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8001)
