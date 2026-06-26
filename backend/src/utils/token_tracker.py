import os
import json
import threading
from datetime import datetime
import logging
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

logger = logging.getLogger(__name__)

class TokenTracker:
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(TokenTracker, cls).__new__(cls)
                cls._instance._init_tracker()
            return cls._instance
            
    def _init_tracker(self):
        # Enforce strict backend/data path regardless of caller's cwd
        data_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data"))
             
        self.data_dir = os.path.join(data_root, "telemetry")
        os.makedirs(self.data_dir, exist_ok=True)
        self.tracker_file = os.path.join(self.data_dir, "token_tally.json")
        self.file_lock = threading.Lock()
        self._cache = self._load()
        
    def _load(self):
        today = datetime.now().strftime("%Y-%m-%d")
        default_data = {
            "date": today, 
            "flash": {"input_tokens": 0, "output_tokens": 0},
            "pro": {"input_tokens": 0, "output_tokens": 0}
        }
        
        if not os.path.exists(self.tracker_file):
            return default_data
            
        try:
            with open(self.tracker_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if data.get("date") != today:
                    return default_data # Reset for new day
                # Handle migration from old flat schema to nested schema
                if "flash" not in data or "pro" not in data:
                    return default_data
                return data
        except Exception:
            return default_data
            
    def _save(self):
        try:
            with open(self.tracker_file, "w", encoding="utf-8") as f:
                json.dump(self._cache, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save token tally: {e}")

    def add_tokens(self, input_tokens: int, output_tokens: int, model_name: str = "gemini-3-flash"):
        if not input_tokens and not output_tokens:
            return
            
        today = datetime.now().strftime("%Y-%m-%d")
        
        tier = "pro" if "pro" in model_name.lower() else "flash"
        
        with self.file_lock:
            # Sync with disk first to handle multi-process safely
            current_cache = self._load()
            if current_cache.get("date") != today:
                current_cache = {
                    "date": today, 
                    "flash": {"input_tokens": 0, "output_tokens": 0},
                    "pro": {"input_tokens": 0, "output_tokens": 0}
                }
                
            current_cache[tier]["input_tokens"] += (input_tokens or 0)
            current_cache[tier]["output_tokens"] += (output_tokens or 0)
            self._cache = current_cache
            self._save()
        
    def get_tally(self):
        with self.file_lock:
            # Always sync with disk for accurate reads across processes
            self._cache = self._load()
            return dict(self._cache)

    def get_total_daily_tokens(self) -> int:
        tally = self.get_tally()
        total = 0
        for key, val in tally.items():
            if isinstance(val, dict):
                total += val.get("input_tokens", 0) + val.get("output_tokens", 0)
        return total

token_tracker = TokenTracker()

class TokenUsageCallbackHandler(BaseCallbackHandler):
    """Callback Handler that tracks LLM token usage globally."""
    
    def on_llm_end(self, response: LLMResult, **kwargs) -> None:
        """Collect token usage from the LLM response."""
        input_tokens = 0
        output_tokens = 0
        model_name = "gemini-3-flash" # Default assumption
        
        # Determine model name (deep inspection for LangChain 0.2+)
        if response.llm_output and response.llm_output.get("model_name"):
            model_name = response.llm_output.get("model_name")
        elif kwargs.get("invocation_params"):
            model_name = kwargs["invocation_params"].get("model") or kwargs["invocation_params"].get("model_name") or model_name
            
        if response.generations and len(response.generations) > 0 and len(response.generations[0]) > 0:
            gen = response.generations[0][0]
            if hasattr(gen, 'message') and hasattr(gen.message, 'response_metadata'):
                meta_model = gen.message.response_metadata.get('model_name') or gen.message.response_metadata.get('model')
                if meta_model:
                    model_name = meta_model
            if hasattr(gen, 'message') and hasattr(gen.message, 'usage_metadata'):
                usage = getattr(gen.message, 'usage_metadata', {})
                if usage:
                    input_tokens = usage.get('input_tokens', 0)
                    output_tokens = usage.get('output_tokens', 0)
        
        # Method 2: Check standard llm_output fallback
        if not input_tokens and not output_tokens and response.llm_output:
            token_usage = response.llm_output.get("token_usage", {})
            input_tokens = token_usage.get("prompt_tokens", token_usage.get("prompt_token_count", 0))
            output_tokens = token_usage.get("completion_tokens", token_usage.get("candidates_token_count", 0))
             
        if input_tokens > 0 or output_tokens > 0:
            token_tracker.add_tokens(input_tokens, output_tokens, model_name)
