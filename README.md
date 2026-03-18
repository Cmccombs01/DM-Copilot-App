# 🐉 DM Co-Pilot: Masterwork Edition (v5.0)

*Current Status:* STABLE & LIVE | *Rank:* 🏆 #1 AI App on Viberank (March 2026)

DM Co-Pilot is a production-grade, twin-engine AI toolkit designed to automate Dungeons & Dragons 5e session prep, provide real-time rulings, and generate sub-second voice-to-voice NPC interactions at the table.

## 🚀 The v5.0 Masterwork Upgrades

* 👻 **Ghost NPC (Voice-to-Voice Engine):** A low-latency conversational agent. Users speak directly into their microphone, and the AI responds out loud, in character, using OpenAI's cinematic Onyx voice. 
* 🔐 **Zero-Config BYOK Architecture:** Implemented a secure "Bring Your Own Key" environment for Groq logic routing, paired with an OS-level Render Vault handshake to provide users with a 5-turn premium voice trial.
* 🗺️ **Predictive World Heatmaps (GraphRAG):** A deterministic data visualization tool that maps the "butterfly effects" of chaotic player actions into interactive faction knowledge graphs.
* 🎲 **The Fate-Threader (v4.1):** A client-side Monte Carlo combat simulator. Runs 1,000 parallel encounter timelines in milliseconds to calculate precise TPK probabilities with zero backend latency.

## 🏗️ Architecture & Tech Stack
Built to handle high-traffic weekend gaming bursts without rate-limit freezing.
* **Frontend (Client):** *Streamlit* — Handles UI, Session State, and local deterministic math (like the Fate-Threader) to bypass CORS overhead.
* **Backend (API):** *FastAPI* hosted on *Render* — Manages secure Vault handshakes and REST endpoints.
* **Agentic Brain:** *Groq* (Llama 3.1) + *OpenAI* (Whisper Large V3 & TTS-1).
