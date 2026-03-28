# 🐉 DM Co-Pilot | Community Edition

**The open-source workstation for Dungeons & Dragons 5e.**

[![Viberank Rank](https://img.shields.io/badge/Viberank-%231_Rated-00FF00)](https://viberank.dev/?category=AI)
[![Status](https://img.shields.io/badge/Status-Live_v8.6-blue)](https://dm-copilot-cloud.onrender.com/)

DM Co-Pilot is a community-driven AI toolkit designed to eliminate session prep friction. It provides modular tools for monster generation, VTT integration, and real-time rules assistance.

## ✨ Core Community Features

* **🐉 Monster Lab:** Live split-pane Markdown editor to draft custom creatures with real-time stat block rendering.
* **🔌 VTT Bridge:** Schema-ready JSON exports and live API webhooks for Foundry VTT and Roll20.
* **🛡️ Initiative Tracker:** Local-first combat manager with SQLite session recovery and 0.01s WebSocket player syncing.
* **🎲 Random Generators:** Deterministic SRD loot hoard rolling, NPC forging, and Tavern Rumors.

## 🏗️ Cloud Architecture (v8.6 Microservice)

To handle 450+ concurrent users and hold the #1 spot on Viberank, the production application utilizes a decoupled, dual-server microservice architecture:

1. **Frontend UI (Streamlit):** Handles the lightweight visual interface and real-time player WebSocket syncing.
2. **The Oracle Engine (FastAPI):** A dedicated headless backend that processes heavy LLM logic, rules arbitration, and Qdrant vector database math.
3. **Redis Edge-Cache:** A distributed cache pool that intercepts redundant API calls, slashing mean latency to ~0.75s and preventing LLM rate limits.
4. **The Failover Matrix:** Automated LLM routing that silently falls back from Groq to OpenAI if rate limits are hit, ensuring 100% uptime.

## 🛠️ Security & API Configuration (BYOK)

To keep this project free and accessible, users provide their own API keys:

1. **Groq API:** High-speed logic and 5e rules assistance.
2. **OpenAI API:** Advanced Vision (Dice/Map OCR) and Multi-modal fallback.
*Input your keys in the sidebar of the application to begin.*

## 🚀 Quick Start (Local Monolith)

*Note: The local development build runs as a monolith for ease of use.*

1. **Clone the Repo:** `git clone https://github.com/Cmccombs01/DM-Copilot-App.git`
2. **Install:** `pip install -r requirements.txt`
3. **Run:** `streamlit run app.py`

[Launch the Live Community Build](https://dm-copilot-cloud.onrender.com/)
