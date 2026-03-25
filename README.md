# 🐉 DM Co-Pilot | Masterwork Edition (v7.5)

![Viberank Status](https://img.shields.io/badge/Viberank-%231_Global_AI_App-FFD700?style=for-the-badge&logo=fire)
![Build Status](https://img.shields.io/badge/Render-Passing-00FF00?style=for-the-badge&logo=render)
![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python)

DM Co-Pilot is an enterprise-grade, AI-powered toolkit designed to automate the heavy lifting for Dungeons & Dragons 5e Dungeon Masters.

Currently actively handling **200+ concurrent DMs** with **sub-second latency**, powered by a distributed Redis edge-cache and the Groq (Llama-3) inference engine.

## 🚀 The v7.5 "Unbreakable Bridge" Update
* **Foundry VTT Strict Mode:** Implemented a custom Type-Safety Sanitizer for 100% flawless VTT JSON exports, surviving Foundry's strictest schema validations.
* **The Human-First Edit Loop:** All AI generators (Monster Lab, NPCs, Villain Architect) now output to editable Markdown stations before exporting.
* **Asynchronous Aegis:** Heavy multi-modal tasks (Cinematic Recaps, DALL-E 3 Token Art) are now threaded to background workers, preventing the main UI from ever freezing during live combat.
