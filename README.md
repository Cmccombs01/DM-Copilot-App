# 🐉 Delver's Grimoire (Formerly DM Co-Pilot)

[![Live App](https://img.shields.io/badge/Live_App-delversgrimoire.com-blue?style=for-the-badge)](https://www.delversgrimoire.com/)
[![PyPI Package](https://img.shields.io/badge/PyPI-dnd--5e--validator-yellow?style=for-the-badge)](https://pypi.org/project/dnd-5e-validator/)

**An open-source, AI-powered JSON data pipeline, VTT automation tool, and combat analytics engine for Dungeons & Dragons 5e.**

Built to remove friction from live tabletop sessions, Delver's Grimoire scales generative AI to handle everything from balancing mathematical encounter tension to bridging the gap between legacy 2014 D&D rules and the modern WotC 2024 design philosophy.

---

### 🛠️ Tech Stack & Architecture
* **Frontend/Framework:** Python, Streamlit
* **AI Engine:** Groq (Llama-3), OpenAI (DALL-E 3), Custom Prompt Engineering
* **Data Validation:** Pydantic (Open-sourced custom validation models to PyPI: `dnd-5e-validator`)
* **Database & Telemetry:** Google Cloud Firestore, Custom Analytics Pipelines
* **VTT Integration:** Native REST API Webhooks & structured JSON (Foundry VTT / Roll20)

---

## 📈 Technical Case Study: Scaling to 1,200+ Weekly Pageviews

**The Catalyst:** Following a viral community post, the application experienced a massive traffic surge, resulting in over 1,290+ pageviews and 27+ hours of active compute time in a 4-day window.

**The Bottleneck:** The initial architecture relied on continuous read/writes to Google Cloud Firestore for every UI interaction. During peak load, the database throttled, causing unacceptable latency for live DMs using the combat tracker.

**The Pivot & Solution:**
1. **State Management:** Refactored live combat tools (Initiative Tracker, Player Cheat Sheet) to execute entirely inside Streamlit's `st.session_state` (browser memory) for 0ms latency during live combat.
2. **Custom Telemetry:** Replaced third-party analytics with a custom data pipeline querying raw Firestore arrays directly, rendering instant, crash-proof native charts.
3. **Automated Testing:** Implemented a robust `pytest` suite to ensure Pydantic JSON validation never fails during live VTT exports.

---

## 🚀 Key Features

* **⚖️ Action Economy Analyzer:** An algorithmic combat calculator that determines true difficulty outside of the standard CR system, using AI to suggest tactical, non-HP-based balancing strategies based on action-ratios.
* **🔌 Direct Foundry VTT Webhooks:** Bypasses local file downloads by POSTing generated JSON statblocks directly to a live Foundry VTT server via REST API.
* **📜 Foundry Macro Coder:** An AI code-generation module specifically tuned to the Foundry VTT JavaScript API, allowing non-coding DMs to build complex combat automations.
* **🔄 2014 -> 2024 Rule Converter:** Uses highly tuned LLMs to translate legacy 5e homebrew into the new WotC 2024 formatting standards (e.g., weapon masteries, updated action economy).
* **🧠 PyPI Package Publication:** Abstracted the core JSON validation logic into a standalone, published Python package (`pip install dnd-5e-validator`).
* **🗣️ Audio Scribe:** Native Voice-to-Text integration that transforms chaotic, spoken brainstorming sessions into perfectly formatted, structured campaign notes.

---

## 💻 Local Development Setup

To run this application locally:

1. **Clone the repository:**
   ```bash
   git clone [https://github.com/yourusername/DM-Copilot-Web-App.git](https://github.com/yourusername/DM-Copilot-Web-App.git)
   cd DM-Copilot-Web-App,
