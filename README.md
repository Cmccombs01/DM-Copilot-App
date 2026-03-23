# 🐉 DM Co-Pilot | Enterprise AI Tabletop Engine

![Viberank](https://img.shields.io/badge/Viberank-Top_3_Global-FFD700?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.11-blue?style=for-the-badge&logo=python)
![Redis](https://img.shields.io/badge/Redis-Edge_Cache-dc382d?style=for-the-badge&logo=redis)
![OpenAI/Groq](https://img.shields.io/badge/LLM-Groq_/_OpenAI-10a37f?style=for-the-badge)

**High-availability LLM orchestration for D&D 5e, featuring real-time state management, asynchronous UI threading, and automated VTT data pipelines.**

*(Note: Check out the [60-Second Architecture Demo Video Here] - Add your Loom/YouTube link here later)*

## ⚙️ Architecture at Scale
DM Co-Pilot was built to solve the infrastructure bottlenecks that plague modern Virtual Tabletops (VTTs): database locking, high-latency LLM inference, and rigid data entry. 

During a recent weekend traffic surge (450+ concurrent users), the application maintained a strict **0.81s average inference latency** with zero dropped connections.

### Core Infrastructure Pillars
* **The VTT Bridge (Strict Schema Validation):** A custom REST API pipeline that dynamically generates, validates, and injects strictly typed JSON payloads (e.g., `Actor5e`, `Item5e`) directly into local Foundry VTT and Roll20 environments. 
* **Real-Time UI Synchronization:** Built with a "Two-Way Player Portal" using React logic and asynchronous background polling. Mobile clients sync HP and trigger cinematic audio/visual cues instantly without lagging the primary browser thread.
* **The Failover Matrix:** Primary text generation is routed through Groq (Llama-3) for sub-second inference, with a silent, automated fallback to OpenAI (GPT-4o) for complex Vision AI tasks and API rate-limit handling.
* **Distributed Edge-Caching:** Implemented a Redis semantic cache and a background garbage-collection thread to successfully mitigate 2GB memory leaks during heavy 5e Bestiary JSON loads, preventing OOM crashes under load.

## 🛠️ The Tech Stack
* **Frontend/UI:** Python, Streamlit, React (Custom Components), HTML/CSS
* **Backend & Caching:** Redis, Qdrant (Vector DB), SQLite, Pandas
* **Cloud & Serverless:** Google Cloud Platform (Firestore for real-time multiplayer states), Render
* **AI & Orchestration:** OpenAI API (GPT-4o, DALL-E 3, Whisper), Groq API (Llama-3), GraphRAG (Network Visualization)

## 📄 Incident Post-Mortems
I believe in "Building in Public" and documenting failures just as rigorously as successes. 
* Read the [v6.9.1 OOM Crash Post-Mortem](.github/copilot-instructions.md) to see how we hot-swapped a bloated JSON cache for a distributed Redis cluster on the fly without dropping active player connections.

## 🤝 Connect
I am a Data/AI Engineer specializing in high-availability LLM orchestration and VTT data architecture. If your team is building the next generation of digital tabletop technology, let's connect.

* [LinkedIn Profile](https://www.linkedin.com/in/caleb-mccombs-850335237/)
