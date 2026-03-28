# Cobalt Multiagent - High-fidelity financial analysis platform
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
# License: PolyForm Noncommercial 1.0.0

# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class StepType(str, Enum):
    RESEARCH = "research"
    PROCESSING = "processing"
    SCOUT = "scout"
    JOURNALER = "journaler"

    ANALYST = "analyst"
    IMAGING = "imaging"
    SYSTEM = "system"


class Step(BaseModel):
    need_search: bool = Field(..., description="Must be explicitly set for each step")
    title: str
    description: str = Field(..., description="Specify exactly what data to collect")
    step_type: StepType = Field(..., description="Indicates the nature of the step")
    execution_res: Optional[str] = Field(
        default=None, description="The Step execution result"
    )


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
                            "step_type": "research",
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
