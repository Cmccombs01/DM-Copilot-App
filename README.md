# 🐉 DM Co-Pilot (Delver's Grimoire)
**An Open-Source, Multi-Modal AI Engine for Tabletop RPGs**

[![Viberank](https://img.shields.io/badge/Viberank-Top_10_Global-green.svg)](https://viberank.dev)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.30%2B-red)](https://streamlit.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

DM Co-Pilot is a production-grade Python web application designed to automate the heavy lifting of Dungeon Mastering for D&D 5e. Built with scalability and latency in mind, the platform seamlessly integrates LLMs, multi-modal Vision/Audio models, custom RAG pipelines, and external API webhooks to create a zero-friction experience at the table.

**Live Application:** [www.delversgrimoire.com](https://www.delversgrimoire.com)

---

## 🚀 Live Telemetry & Scaling
Originally launched as a weekend prototype, the app recently scaled to handle a massive traffic surge, hitting **450+ peak concurrent users**, crossing **1,670+ total interactions**, and currently holding the **#8 spot globally** for AI apps on Viberank. 

The architecture utilizes RAM-caching for large JSON bestiaries and asynchronous API calls to maintain 0ms UI latency during live table combat.

## 🧠 Core Architecture & Features

### 1. Multi-Modal AI Processing
* **👁️ The Cartographer's Eye (Vision AI):** Integrates `gpt-4o` to ingest `base64` encoded images of hand-drawn graphing paper maps, calculating spatial geometry to generate precise JSON wall/door coordinates for Virtual Tabletop (VTT) imports.
* **🎙️ Audio Scribe & Sentiment Analysis:** Utilizes OpenAI's Whisper-large-v3 to transcribe live table audio. The AI analyzes pacing and engagement, automatically generating "Tension Spikes" to cure player analysis paralysis.
* **🎬 Cinematic Recaps:** A full-suite pipeline that takes raw session notes and outputs a dramatic script, a DALL-E 3 generated cover image, and an OpenAI TTS (Text-to-Speech) narrated MP3 file.

### 2. External API Bridges & Webhooks
* **🔗 D&D Beyond Bridge:** Uses Python's `re` and `requests` libraries to scrape the hidden `character-service.dndbeyond.com` REST API, instantly parsing nested JSON character sheets into a live `pandas` DataFrame for zero-lag combat tracking.
* **🔌 Direct VTT Integration:** Bypasses local downloads by utilizing automated POST requests to inject generated monster stat blocks and loot directly into a live Foundry VTT server via REST API webhooks.

### 3. Data Engineering & Memory
* **🕸️ Campaign Lore Weaver (RAG):** Implements `PyPDF2` and custom vectorization prompting to allow users to upload massive campaign modules, creating an interactive "Campaign Historian" that answers questions strictly based on the provided document context.
* **🏛️ The Community Vault:** Integrated with Google Cloud Firestore (NoSQL) for live, community-driven database tracking and user-generated content sharing.
* **🌐 Auto-Wiki HTML Generation:** An automated frontend compiler that scrapes the user's `st.session_state` memory and injects their generated JSON lore into a standalone, styled, downloadable `index.html` website file.

## 🛠️ Tech Stack
* **Frontend/Backend:** Python, Streamlit, Pandas
* **AI Engines:** Groq (Llama-3.1-8b for high-speed text), OpenAI (GPT-4o, DALL-E 3, Whisper, TTS)
* **Cloud Database:** Google Cloud Firestore
* **Validation:** Pydantic models for strict JSON schema enforcement

## ⚙️ Installation & Setup (Local Instance)
1. Clone the repository: `git clone https://github.com/Cmccombs01/DM-Copilot-App.git`
2. Install dependencies: `pip install -r requirements.txt`
3. Add your API keys to `.streamlit/secrets.toml`:
   ```toml
   GROQ_API_KEY = "your_key_here"
   OPENAI_API_KEY = "your_key_here"
   Run the app: streamlit run app.py

🤝 Contributing
Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change. Let's build the digital future of tabletop gaming.
