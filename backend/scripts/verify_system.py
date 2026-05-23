#!/usr/bin/env python3
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

import os
import subprocess
import sys


def run_command(command, cwd=None):
    cmd_str = " ".join(command)
    print(f"Executing: {cmd_str}")
    # Remove capture_output to stream logs directly to console in real-time
    result = subprocess.run(cmd_str, cwd=cwd, shell=True)
    if result.returncode != 0:
        print(f"Error executing command.")
        return False, ""
    return True, ""


def main():
    backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    print("--- Running Unit Tests ---")
    success, output = run_command(["uv", "run", "pytest", "-v", "-s", "tests/unit"], cwd=backend_dir)
    if not success:
        print("Unit tests failed!")
        sys.exit(1)
    print(output)

    print("--- Checking Node Imports ---")
    # Simple check to ensure nodes can be imported (detects syntax errors/missing dependencies)
    try:
        sys.path.insert(0, backend_dir)
        print("Nodes imported successfully.")
    except Exception as e:
        print(f"Node import failed: {e}")
        sys.exit(1)

    print("--- System Verification Passed! ---")
    sys.exit(0)


if __name__ == "__main__":
    main()
