# 🐉 DM Co-Pilot: The Agentic Edition (v4.0)
[![Viberank Rank](https://img.shields.io/badge/Viberank-Rank_%233-00FF00)](https://viberank.dev/?category=AI&page=2)

**DM Co-Pilot** is a production-grade AI ecosystem for D&D 5e, moving beyond simple prompts into **Multi-Agent Orchestration**.

## ⚖️ Featured: The Real-Time Rules Lawyer (v4.0)
Unlike standard LLMs that hallucinate mechanics, v4.0 implements a **Researcher/Auditor loop**:
- **Agent A (Researcher):** Extracts raw 5e SRD facts via a semantic router.
- **Agent B (Auditor):** Verifies the facts against the live table dispute for a 100% authoritative ruling.

## 🛠️ Tech Stack & Architecture
- **Backend:** [FastAPI](https://dashboard.render.com/web/srv-d6r606450q8c73bspg8g/events) deployed on Render.
- **Intelligence:** Groq-powered Llama 3.1 (8B/70B) for sub-second reasoning.
- **Memory:** [Upstash Redis](https://dm-copilot-cloud.onrender.com/) for global prompt caching (The Oracle Engine).
- **Telemetry:** [Google Cloud Firestore](https://console.cloud.google.com/firestore/databases/-default-/data/panel/dm_copilot_traffic/counts?project=dm-copilot-analytics) for live traffic and community data.

---
*Currently #3 Monthly on [Viberank](https://viberank.dev/?category=AI&page=2) with 4,372+ successful runs.*
