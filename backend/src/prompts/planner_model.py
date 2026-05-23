# Cobalt Multiagent - High-fidelity financial analysis platform
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

# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

from enum import Enum

from pydantic import BaseModel, Field


class StepType(str, Enum):
    SYNTHESIZER = "synthesizer"
    CODER = "coder"
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
    step_type: StepType = Field(..., description="Must be one of: synthesizer, analyst, smc_analyst, risk_manager, portfolio_manager, coder, journaler, imaging, system, session_monitor, vision_specialist, terminal_specialist")
    execution_res: str | None = Field(default=None, description="The Step execution result")


from pydantic import BaseModel, Field, field_validator


class Plan(BaseModel):
    locale: str = Field(..., description="e.g. 'en-US' or 'zh-CN', based on the user's language")
    has_enough_context: bool
    thought: str
    title: str
    intent: str | None = Field(default=None, description="The classified intent: MARKET_INSIGHT, TACTICAL_EXECUTION, or EXECUTE_DIRECT")
    direct_response: str | None = Field(default=None, description="The direct response content if enough context is available")
    steps: list[Step] = Field(
        default_factory=list,
        description="Research & Processing steps to get more context",
    )
    gui_overrides: dict | None = Field(default=None, description="Dynamic CSS/Style overrides for the dashboard (e.g. {'daily_action_plan': {'color': 'red'}})")
    save_gui_vibe: bool = Field(default=False, description="Whether to persist the current GUI vibe settings as the dashboard default")

    @field_validator("steps", mode="after")
    @classmethod
    def enforce_institutional_efficiency(cls, steps: list[Step]) -> list[Step]:
        """Hard constraint: Prevent the LLM from hallucinating >4 agents or duplicate specialized nodes."""
        seen_types = set()
        deduped = []
        for s in steps:
            # We allow multiple steps if they have different targets, but usually we deduplicate specialist nodes
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
                    "thought": ("To understand the current market trends in AI, we need to gather comprehensive information."),
                    "title": "AI Market Research Plan",
                    "steps": [
                        {
                            "need_search": True,
                            "title": "Current AI Market Analysis",
                            "description": ("Collect data on market size, growth rates, major players, and investment trends in AI sector."),
                            "step_type": "synthesizer",
                        }
                    ],
                },
                {
                    "has_enough_context": False,
                    "thought": ("The user is requesting a high-fidelity VLI diagnostic stress test. This requires use of the privileged System node."),
                    "title": "VLI Diagnostic Stress Test",
                    "steps": [
                        {
                            "need_search": False,
                            "title": "Execute Autonomic Cache Simulation",
                            "description": ("Execute the VLI cache logic, maintaining state and timers as instructed."),
                            "step_type": "system",
                        }
                    ],
                },
                {
                    "has_enough_context": False,
                    "thought": ("The user wants an institutional grade SMC analysis. I need to use the smc_analyst for high-fidelity extraction."),
                    "title": "Institutional SMC Extraction",
                    "steps": [
                        {
                            "need_search": False,
                            "title": "SMC Structural Analysis",
                            "description": ("Extract BOS, CHoCH, and FVG markers for the target symbol."),
                            "step_type": "smc_analyst",
                        }
                    ],
                },
            ]
        }
