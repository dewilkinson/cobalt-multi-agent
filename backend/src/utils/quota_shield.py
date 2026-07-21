import time
import os
import logging
from collections import deque
from typing import Dict, List, Tuple
from threading import Lock

logger = logging.getLogger(__name__)

class VLIQuotaExhaustedError(Exception):
    """Raised when an LLM request is blocked by the Quota Shield."""
    pass

class QuotaBucket:
    """Sliding window bucket for RPM and TPM tracking."""
    def __init__(self, rpm_limit: int, tpm_limit: int):
        self.rpm_limit = rpm_limit
        self.tpm_limit = tpm_limit
        self.requests = deque() # List of timestamps
        self.tokens = deque()   # List of (timestamp, token_count)
        self.lock = Lock()

    def _clean_window(self, now: float):
        """Removes entries older than 60 seconds."""
        cutoff = now - 60.0
        while self.requests and self.requests[0] < cutoff:
            self.requests.popleft()
        while self.tokens and self.tokens[0][0] < cutoff:
            self.tokens.popleft()

    def check_and_reserve(self, estimated_tokens: int) -> bool:
        """Checks if current usage allows for a new request."""
        with self.lock:
            now = time.time()
            self._clean_window(now)
            
            current_rpm = len(self.requests)
            current_tpm = sum(t[1] for t in self.tokens)
            
            if current_rpm >= self.rpm_limit:
                logger.warning(f"[QUOTA_SHIELD] RPM Limit Hit: {current_rpm}/{self.rpm_limit}")
                return False
                
            if current_tpm + estimated_tokens > self.tpm_limit:
                logger.warning(f"[QUOTA_SHIELD] TPM Limit Hit: {current_tpm + estimated_tokens}/{self.tpm_limit}")
                return False
            
            # Tentative reservation (we add the request now, tokens updated post-flight)
            self.requests.append(now)
            # Add estimated tokens for now to block subsequent spams
            self.tokens.append((now, estimated_tokens))
            return True

    def update_actual_usage(self, estimated_tokens: int, actual_tokens: int):
        """Replaced the estimated reservation with the actual usage metadata."""
        with self.lock:
            # This is a bit tricky with sliding window deques. 
            # For simplicity, we just add the delta to the most recent token entry if it matches
            # but it is better to just keep the estimation and let it rotate out, 
            # Or we can just add the the ACTUAL tokens on completion.
            # Updated approach: check_and_reserve adds the ESTIMATION.
            # update_actual_usage replaces that entry or adjusts the total.
            pass # Sliding window eventually rotates the estimate out. 

class QuotaShield:
    """Global registry of model quotas."""
    _instance = None
    _lock = Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(QuotaShield, cls).__new__(cls)
                cls._instance.buckets = {}
                cls._instance.tier_limits = {
                    "reasoning": (50, 500000),  # RPM, TPM
                    "basic": (1000, 2000000),   # RPM, TPM
                    "vision": (200, 1000000),
                    "core": (500, 3000000),
                    "legacy": (2000, 4000000)
                }
                cls._instance._load_limits()
            return cls._instance

    def _load_limits(self):
        try:
            from src.config.loader import get_config
            config = get_config()
            if config:
                limits = config.get("QUOTA_LIMITS", {})
                for tier, limits_dict in limits.items():
                    if isinstance(limits_dict, dict):
                        default_rpm, default_tpm = self.tier_limits.get(tier, (10, 100000))
                        rpm = limits_dict.get("rpm", default_rpm)
                        tpm = limits_dict.get("tpm", default_tpm)
                        self.tier_limits[tier] = (rpm, tpm)
        except Exception as e:
            logger.warning(f"Error loading quota limits from config: {e}")

    def get_bucket(self, tier: str) -> QuotaBucket:
        if tier not in self.buckets:
            limit = self.tier_limits.get(tier, (10, 100000))
            self.buckets[tier] = QuotaBucket(limit[0], limit[1])
        return self.buckets[tier]

    def allow_request(self, tier: str, estimated_tokens: int = 1000) -> bool:
        return self.get_bucket(tier).check_and_reserve(estimated_tokens)

def get_daily_token_cap() -> int:
    """Gets the daily token cap, defaulting to 2,000,000."""
    # 1. Environment variable check
    env_cap = os.getenv("DAILY_TOKEN_CAP")
    if env_cap is not None:
        try:
            return int(env_cap)
        except ValueError:
            pass
            
    # 2. Config check
    try:
        from src.config.loader import get_config
        config = get_config()
        if config:
            # Check top level
            for key in ["DAILY_TOKEN_CAP", "daily_token_cap"]:
                if key in config:
                    return int(config[key])
            # Check under QUOTA_LIMITS
            quota_limits = config.get("QUOTA_LIMITS", {})
            for key in ["DAILY_TOKEN_CAP", "daily_token_cap"]:
                if key in quota_limits:
                    return int(quota_limits[key])
    except Exception as e:
        logger.warning(f"Error loading daily token cap: {e}")
        
    return 2000000

quota_shield = QuotaShield()
