# Cobalt Multiagent - High-fidelity financial analysis platform
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
# License: PolyForm Noncommercial 1.0.0

# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class StepType(str, Enum):
    RESEARCHER = "researcher"
    CODER = "coder"
    SCOUT = "scout"
    JOURNALER = "journaler"

    ANALYST = "analyst"
    IMAGING = "imaging"
    SYSTEM = "system"
    PORTFOLIO_MANAGER = "portfolio_manager"
    RISK_MANAGER = "risk_manager"
    SESSION_MONITOR = "session_monitor"
    VISION_SPECIALIST = "vision_specialist"
    TERMINAL_SPECIALIST = "terminal_specialist"
    SMC_ANALYST = "smc_analyst"


class Step(BaseModel):
    need_search: bool = Field(..., description="Must be explicitly set for each step")
    title: str
    description: str = Field(..., description="Specify exactly what data to collect")
    step_type: StepType = Field(..., description="Indicates the nature of the step")
    execution_res: Optional[str] = Field(
        default=None, description="The Step execution result"
    )


from pydantic import BaseModel, Field, field_validator

class Plan(BaseModel):
    locale: str = Field(
        ..., description="e.g. 'en-US' or 'zh-CN', based on the user's language"
    )
    has_enough_context: bool
    thought: str
    title: str
    direct_response: Optional[str] = Field(
        default=None, description="The direct response content if enough context is available"
    )
    steps: List[Step] = Field(
        default_factory=list,
        description="Research & Processing steps to get more context",
    )
    gui_overrides: Optional[dict] = Field(
        default=None, description="Dynamic CSS/Style overrides for the dashboard (e.g. {'daily_action_plan': {'color': 'red'}})"
    )
    save_gui_vibe: bool = Field(
        default=False, description="Whether to persist the current GUI vibe settings as the dashboard default"
    )

    @field_validator("steps", mode="after")
    @classmethod
    def enforce_institutional_efficiency(cls, steps: List[Step]) -> List[Step]:
        """Hard constraint: Prevent the LLM from hallucinating >4 agents or duplicate specialized nodes."""
        seen_types = set()
        deduped = []
        for s in steps:
            # We allow multiple 'scout' steps if they have different targets, but usually we deduplicate specialist nodes
            if s.step_type in [StepType.SMC_ANALYST, StepType.ANALYST, StepType.VISION_SPECIALIST, StepType.SYSTEM]:
                if s.step_type in seen_types:
                    continue
                seen_types.add(s.step_type)
            deduped.append(s)
            
        # Hard truncate to prevent massive system resource exhaustion (agent bloat)
        return deduped[:4]


    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "has_enough_context": False,
                    "thought": (
                        "To understand the current market trends in AI, we need to gather comprehensive information."
                    ),
                    "title": "AI Market Research Plan",
                    "steps": [
                        {
                            "need_search": True,
                            "title": "Current AI Market Analysis",
                            "description": (
                                "Collect data on market size, growth rates, major players, and investment trends in AI sector."
                            ),
                            "step_type": "researcher",
                        }
                    ],
                },
                {
                    "has_enough_context": False,
                    "thought": (
                        "The user is requesting a high-fidelity VLI diagnostic stress test. This requires use of the privileged System node."
                    ),
                    "title": "VLI Diagnostic Stress Test",
                    "steps": [
                        {
                            "need_search": False,
                            "title": "Execute Autonomic Cache Simulation",
                            "description": (
                                "Execute the VLI cache logic, maintaining state and timers as instructed."
                            ),
                            "step_type": "system",
                        }
                    ],
                }
            ]
        }
