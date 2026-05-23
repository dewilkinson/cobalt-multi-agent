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

import asyncio
import logging

from langgraph.graph import END, START, StateGraph

from src.prose.graph.prose_continue_node import prose_continue_node
from src.prose.graph.prose_fix_node import prose_fix_node
from src.prose.graph.prose_improve_node import prose_improve_node
from src.prose.graph.prose_longer_node import prose_longer_node
from src.prose.graph.prose_shorter_node import prose_shorter_node
from src.prose.graph.prose_zap_node import prose_zap_node
from src.prose.graph.state import ProseState


def optional_node(state: ProseState):
    return state["option"]


def build_graph():
    """Build and return the ppt workflow graph."""
    # build state graph
    builder = StateGraph(ProseState)
    builder.add_node("prose_continue", prose_continue_node)
    builder.add_node("prose_improve", prose_improve_node)
    builder.add_node("prose_shorter", prose_shorter_node)
    builder.add_node("prose_longer", prose_longer_node)
    builder.add_node("prose_fix", prose_fix_node)
    builder.add_node("prose_zap", prose_zap_node)
    builder.add_conditional_edges(
        START,
        optional_node,
        {
            "continue": "prose_continue",
            "improve": "prose_improve",
            "shorter": "prose_shorter",
            "longer": "prose_longer",
            "fix": "prose_fix",
            "zap": "prose_zap",
        },
        END,
    )
    return builder.compile()


async def _test_workflow():
    workflow = build_graph()
    events = workflow.astream(
        {
            "content": "The weather in Beijing is sunny",
            "option": "continue",
        },
        stream_mode="messages",
        subgraphs=True,
    )
    async for node, event in events:
        e = event[0]
        print({"id": e.id, "object": "chat.completion.chunk", "content": e.content})


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    logging.basicConfig(level=logging.INFO)
    asyncio.run(_test_workflow())
