import os
import yaml
import logging

logger = logging.getLogger(__name__)

DEFAULT_SMC_CONFIG = {
    "smc_strategy": {
        "macro_map": {
            "timeframes": ["1d", "4h"],
            "lookback_bars": 200
        },
        "tactical_map": {
            "timeframes": ["1h"],
            "lookback_bars": 100
        },
        "execution_trigger": {
            "timeframes": ["5m"],
            "lookback_bars": 50,
            "alignment_required": True
        }
    }
}

def load_smc_config() -> dict:
    """Loads the SMC configuration from the yaml file, falling back to defaults if not found."""
    config_path = os.path.join(os.path.dirname(__file__), "smc_config.yaml")
    
    if not os.path.exists(config_path):
        logger.warning(f"SMC config not found at {config_path}. Using default strategic mapping.")
        return DEFAULT_SMC_CONFIG

    try:
        with open(config_path, "r") as f:
            file_config = yaml.safe_load(f)
            
        if not file_config or "smc_strategy" not in file_config:
            logger.warning("smc_config.yaml is malformed. Using default strategic mapping.")
            return DEFAULT_SMC_CONFIG
            
        return file_config

    except Exception as e:
        logger.error(f"Error loading SMC config: {e}. Using default strategic mapping.")
        return DEFAULT_SMC_CONFIG
