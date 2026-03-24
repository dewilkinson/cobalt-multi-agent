# Project Cobalt: CMA (Cobalt Multiagent)

A high-integrity, multi-agent intelligence system for individual SMC traders.

Project Cobalt is an agentic framework designed to bridge the gap between raw market data and high-conviction Smart Money Concepts (SMC) analysis. Built on a modular "Blackboard" architecture, Cobalt uses specialized AI agents to scout liquidity, analyze market structure, and deliver graded trade setups directly into your Obsidian vault.

---

*Acknowledgments: This project is a customized iteration built upon the excellent [DeerFlow Quickstart](https://github.com/bytedance/deer-flow) framework by ByteDance. We are deeply grateful to its original authors and the open-source community that made the underlying architecture possible.*

*Contact: D. Wilkinson ([dwilkins@bluesec.ai](mailto:dwilkins@bluesec.ai))*

---

## 🛠 Core Architecture: The CMA Framework

Cobalt operates through the CMA (Cobalt Multiagent) logic, which decentralizes the analytical process to ensure data integrity and prevent AI hallucination.
- **VLI (VibeLink Interface)**: The primary command layer. Interprets natural language "vibes" and context to coordinate agent workflows.
- **The Scout**: A hardened data retrieval agent. Connects to brokerage APIs (SnapTrade) to fetch high-fidelity OHLC and trade history.
- **The Analyst**: The logic engine. Scans for Liquidity Sweeps, Market Structure Shifts (MSS), and Fair Value Gaps (FVG).
- **The Hub (Obsidian)**: The local "Source of Truth" where all agent dispatches are stored, archived, and audited.

## 🛡 Security & Philosophy

Cobalt is built with a Security-First mindset:
- **Read-Only by Design**: This system has zero execution capability. It cannot place trades or move funds. You are the only "Human-in-the-Loop."
- **Asynchronous Git Bridge**: Data moves from the cloud to your local machine via a private Git buffer, allowing for full auditability and offline persistence.
- **Zero-Vault Secrets**: No API keys are ever stored in your Markdown files. All credentials reside in encrypted environment variables.

## ⚖️ License

Project Cobalt is released under the PolyForm Noncommercial License 1.0.0.
- **Individual Investors**: Free to use, modify, and study for personal trading activities.
- **Commercial Entities**: Institutional use, for-profit redistribution, or commercial integration is strictly prohibited.

## 🚀 Getting Started

1. **Clone the Repo**: Initialize your Obsidian vault as a Git repository.
2. **Configure Railway**: Deploy the Scout agent to Railway and input your SnapTrade credentials as environment variables.
3. **Define your SOP**: Set your SMC grading thresholds in the VLI configuration.
4. **Open Obsidian**: Use the Obsidian Git plugin to begin receiving Dispatches.
