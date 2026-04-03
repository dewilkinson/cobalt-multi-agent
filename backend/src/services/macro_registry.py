# Cobalt Multiagent - Macro Symbol Registry Service
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>

import os
import json
import logging
from typing import Dict, Optional
from src.config.vli import get_vli_path

logger = logging.getLogger(__name__)

class MacroRegistry:
    """
    Centralized registry for 'macro' symbols, stored in the Obsidian vault.
    Allows for dynamic resolution of macro intent and user-editability.
    """
    
    # Default set to fall back on if file missing
    DEFAULT_MACROS = {
        "VIX": "^VIX",
        "DXY": "DX-Y.NYB",
        "TNX": "^TNX",
        "SPY": "SPY",
        "QQQ": "QQQ",
        "IWM": "IWM",
        "GLD": "GLD",
        "BTC": "BTC-USD",
        "USO": "USO",
        "CL": "CL=F",
        "GC": "GC=F",
        "SPX": "^GSPC",
        "NDX": "^IXIC",
        "TYX": "^TYX",
        "EUR/USD": "EURUSD=X"
    }

    def __init__(self):
        self.registry_file = get_vli_path("vli_macros.json")
        self._ensure_registry_exists()

    def _ensure_registry_exists(self):
        """Creates the initial JSON file if it doesn't exist."""
        if not os.path.exists(self.registry_file):
            logger.info("Macro Registry: Initializing default macro set in vault.")
            try:
                os.makedirs(os.path.dirname(self.registry_file), exist_ok=True)
                with open(self.registry_file, 'w', encoding='utf-8') as f:
                    json.dump(self.DEFAULT_MACROS, f, indent=4)
            except Exception as e:
                logger.error(f"Macro Registry: Failed to initialize registry file: {e}")

    def get_macros(self) -> Dict[str, str]:
        """Loads the current macro mappings from the JSON file."""
        try:
            if not os.path.exists(self.registry_file):
                return self.DEFAULT_MACROS
                
            with open(self.registry_file, 'r', encoding='utf-8') as f:
                macros = json.load(f)
                # Filter out garbage
                return {str(k).upper(): str(v).upper() for k, v in macros.items() if k and v}
        except Exception as e:
            logger.error(f"Macro Registry: Failed to load macros: {e}")
            return self.DEFAULT_MACROS

    def update_macro(self, label: str, ticker: str):
        """Adds or updates a macro mapping."""
        macros = self.get_macros()
        macros[label.upper()] = ticker.upper()
        self._save(macros)

    def remove_macro(self, label: str):
        """Removes a macro mapping."""
        macros = self.get_macros()
        label_upper = label.upper()
        if label_upper in macros:
            del macros[label_upper]
            self._save(macros)

    def _save(self, macros: Dict[str, str]):
        """Persists the macro set to the vault."""
        try:
            with open(self.registry_file, 'w', encoding='utf-8') as f:
                json.dump(macros, f, indent=4)
            logger.info(f"Macro Registry: Saved {len(macros)} symbols to {self.registry_file}")
        except Exception as e:
            logger.error(f"Macro Registry: Failed to save registry: {e}")

# Global singleton
macro_registry = MacroRegistry()
