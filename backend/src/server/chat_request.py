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


from pydantic import BaseModel, Field

from src.config.report_style import ReportStyle
from src.rag.retriever import Resource


class ContentItem(BaseModel):
    type: str = Field(..., description="The type of content (text, image, etc.)")
    text: str | None = Field(None, description="The text content if type is 'text'")
    image_url: str | None = Field(None, description="The image URL if type is 'image'")


class ChatMessage(BaseModel):
    role: str = Field(..., description="The role of the message sender (user or assistant)")
    content: str | list[ContentItem] = Field(
        ...,
        description="The content of the message, either a string or a list of content items",
    )


class ChatRequest(BaseModel):
    messages: list[ChatMessage] | None = Field([], description="History of messages between the user and the assistant")
    resources: list[Resource] | None = Field([], description="Resources to be used for the research")
    debug: bool | None = Field(False, description="Whether to enable debug logging")
    thread_id: str | None = Field("__default__", description="A specific conversation identifier")
    max_plan_iterations: int | None = Field(1, description="The maximum number of plan iterations")
    max_step_num: int | None = Field(3, description="The maximum number of steps in a plan")
    max_search_results: int | None = Field(3, description="The maximum number of search results")
    auto_accepted_plan: bool | None = Field(False, description="Whether to automatically accept the plan")
    interrupt_feedback: str | None = Field(None, description="Interrupt feedback from the user on the plan")
    mcp_settings: dict | None = Field(None, description="MCP settings for the chat request")
    snaptrade_settings: dict | None = Field(None, description="SnapTrade credentials for the scout tool")
    obsidian_settings: dict | None = Field(None, description="Obsidian vault and note settings for the journaler tool")
    enable_background_investigation: bool | None = Field(True, description="Whether to get background investigation before plan")
    report_style: ReportStyle | None = Field(ReportStyle.ACADEMIC, description="The style of the report")
    enable_deep_thinking: bool | None = Field(False, description="Whether to enable deep thinking")
    verbosity: int | None = Field(1, description="The verbosity level of the agent logs")
    is_test_mode: bool | None = Field(False, description="Whether the request is part of a test scenario")
    direct_mode: bool | None = Field(False, description="Whether to bypass the multi-agent pipeline and respond directly.")


class TTSRequest(BaseModel):
    text: str = Field(..., description="The text to convert to speech")
    voice_type: str | None = Field("BV700_V2_streaming", description="The voice type to use")
    encoding: str | None = Field("mp3", description="The audio encoding format")
    speed_ratio: float | None = Field(1.0, description="Speech speed ratio")
    volume_ratio: float | None = Field(1.0, description="Speech volume ratio")
    pitch_ratio: float | None = Field(1.0, description="Speech pitch ratio")
    text_type: str | None = Field("plain", description="Text type (plain or ssml)")
    with_frontend: int | None = Field(1, description="Whether to use frontend processing")
    frontend_type: str | None = Field("unitTson", description="Frontend type")


class GeneratePodcastRequest(BaseModel):
    content: str = Field(..., description="The content of the podcast")


class GeneratePPTRequest(BaseModel):
    content: str = Field(..., description="The content of the ppt")


class GenerateProseRequest(BaseModel):
    prompt: str = Field(..., description="The content of the prose")
    option: str = Field(..., description="The option of the prose writer")
    command: str | None = Field("", description="The user custom command of the prose writer")


class EnhancePromptRequest(BaseModel):
    prompt: str = Field(..., description="The original prompt to enhance")
    context: str | None = Field("", description="Additional context about the intended use")
    report_style: str | None = Field("academic", description="The style of the report")
