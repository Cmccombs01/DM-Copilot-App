# 🐉 DM Co-Pilot: Masterwork Edition
## AI-Powered Campaign Management & Data Analytics Workflow

[🔴 Launch the Live App](https://dm-copilot-app.streamlit.app/)

## 📌 Project Overview
DM Co-Pilot is a high-performance toolkit designed to eliminate "Dungeon Master Burnout." By combining Generative AI with structured data engineering, this tool automates administrative friction—allowing GMs to focus on storytelling.

**Current Performance Metrics (March 4, 2026):**
* **Total Pageviews:** 380+ (First 12 hours)
* **Engagement:** 660+ Unique Widget Interactions
* **Retention:** 7:04 Average Session Duration (Top 5% for Streamlit utility apps)

---

## 🚀 Key Technical Features

### 1. Rarity-Based Balance Engine (New!)
To address user feedback regarding game balance, we implemented a **Dynamic Recharge Tier** system. The "Magic Item Artificer" now uses strict algorithmic constraints to ensure items align with D&D 5e power scales:
* **Rare:** 1d6+1 charges.
* **Very Rare:** 1d8+2 charges.
* **Legendary:** 2d6+4 charges.

### 2. Cross-Browser CSS Architecture
Developed a robust UI injection layer to solve rendering inconsistencies in **Firefox and Edge**. By utilizing specific `data-testid` selectors and high-priority `!important` flags, the "Parchment & Crimson" theme now renders consistently across all WebKit and non-WebKit browsers.

### 3. Dual-Inference Strategy
Supports a hybrid AI backend to balance speed and privacy:
* **Cloud (Groq):** Powered by Llama 3.1-8B for sub-second response times.
* **Local (Ollama):** Supports fully offline, privacy-focused generation for sensitive campaign data.

### 4. Behavioral Analytics
Integrated `streamlit-analytics2` to monitor user flow in real-time. This data-driven approach allowed us to identify the **Campaign Matchmaker** as the core value proposition (250+ uses) and prioritize its development.

---

## 🛠️ Tech Stack
* **Frontend:** [Streamlit](https://streamlit.io/) (Python) with Custom CSS Injection.
* **AI Engine:** [Groq](https://groq.com/) & [Ollama](https://ollama.com/) (Llama 3.1).
* **Data Science:** Pandas for dataset manipulation, Altair for visual analytics.
* **Telemetry:** Streamlit-Analytics for real-time engagement tracking.

---

## 📜 How to Run Locally
1. Clone the repo: `git clone https://github.com/Cmccombs01/DM-Copilot-App.git`
2. Install dependencies: `pip install -r requirements.txt`
3. Run the app: `streamlit run app.py`

---

## 📬 Feedback & Contributing
The "Tavern Suggestion Box" is always open. If you have feature requests or encounter a bug, please open an issue or submit a PR!
