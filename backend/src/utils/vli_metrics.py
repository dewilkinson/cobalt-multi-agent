# VLI Performance Metrics Logger - Persistent Store for Auditing.
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# [PERSISTENT STORE] Absolute path for VLI Performance Audits to ensure reliability across contexts
_CURRENT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _CURRENT_DIR.parent.parent
_METRICS_PATH = _PROJECT_ROOT / "logs" / "vli_performance.jsonl"


def log_vli_metric(agent_type: str, latency: float, accuracy: float = 100.0, status: str = "pass", iteration: int = 1, metadata: dict = None, is_stress_test: bool = False):
    """Appends a performance metric entry to the persistent JSONL store."""
    try:
        # Create directory if needed
        _METRICS_PATH.parent.mkdir(parents=True, exist_ok=True)

        meta = metadata or {}
        if is_stress_test:
            meta["is_stress_test"] = True

        entry = {"timestamp": datetime.now().isoformat(), "agent": agent_type, "latency_sec": round(latency, 3), "accuracy_pct": round(accuracy, 2), "status": status, "iteration": iteration, "metadata": meta}

        with open(_METRICS_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

        logger.debug(f"VLI Metric Logged: {agent_type} in {latency:.2f}s")
    except Exception as e:
        logger.error(f"VLI metrics logging failed: {e}")


def get_recent_metrics(limit: int = 100):
    """Retrieves the last N metrics for dashboard rendering or auditing."""
    if not _METRICS_PATH.exists():
        return []

    metrics = []
    try:
        with open(_METRICS_PATH, encoding="utf-8") as f:
            lines = f.readlines()
            for line in lines[-limit:]:
                metrics.append(json.loads(line))
    except Exception as e:
        logger.error(f"Failed to read metrics: {e}")

    return metrics
