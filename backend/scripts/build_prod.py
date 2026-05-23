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

"""
Build script to prepare the backend for production deployment.
This script physically removes any code blocks enclosed between
# TEST_ONLY_START and # TEST_ONLY_END to ensure test logic
does not leak into the production environment.
"""

import os
import sys


def strip_test_blocks(filepath):
    try:
        with open(filepath, encoding="utf-8") as f:
            lines = f.readlines()
    except UnicodeDecodeError:
        return False

    new_lines = []
    in_test_block = False
    modified = False

    for line in lines:
        stripped_line = line.strip()
        if stripped_line == "# TEST_ONLY_START":
            in_test_block = True
            modified = True
            continue
        elif stripped_line == "# TEST_ONLY_END":
            in_test_block = False
            continue

        if not in_test_block:
            new_lines.append(line)

    if modified:
        with open(filepath, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
        print(f"Stripped test blocks from: {filepath}")
        return True
    return False


def main():
    backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    src_dir = os.path.join(backend_dir, "src")

    if not os.path.exists(src_dir):
        print(f"Error: Could not find src directory at {src_dir}")
        sys.exit(1)

    print("=========================================")
    print("Cobalt Multiagent - Production Build Prep")
    print("=========================================")
    print("Scanning for test-only code blocks...")

    files_modified = 0
    for root, _, files in os.walk(src_dir):
        for file in files:
            if file.endswith(".py"):
                filepath = os.path.join(root, file)
                if strip_test_blocks(filepath):
                    files_modified += 1

    print(f"\nBuild prep complete. Modified {files_modified} files.")
    print("Zero test code leak policy enforced.")


if __name__ == "__main__":
    main()
