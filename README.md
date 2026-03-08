# 🐉 DM Co-Pilot: Masterwork Edition
**An AI-powered web application designed to automate D&D 5e session prep, featuring live telemetry, VTT integration, and a cloud-based community vault.**

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)
![Google Cloud Firestore](https://img.shields.io/badge/Google_Cloud-4285F4?style=for-the-badge&logo=google-cloud&logoColor=white)
![OpenAI](https://img.shields.io/badge/OpenAI-412991?style=for-the-badge&logo=openai&logoColor=white)

## 🚀 The Project
I built **DM Co-Pilot** to solve a real-world problem: Dungeon Master burnout. This tool bridges the gap between raw data and legendary storytelling, cutting session prep time by 80%. 

Recently, the app experienced a viral traffic surge across multiple TTRPG communities, logging over 4.5 hours of continuous user engagement in a single afternoon. I live-patched the servers, deployed backend analytics, and shipped user-requested features mid-surge.

## 🛠️ Key Features
* **⚔️ Encounter Architect & VTT Export:** Generates perfectly balanced D&D 5e encounters using AI, and instantly exports them as `.json` files for seamless integration into Foundry VTT.
* **📊 Live Product Analytics:** Integrated `streamlit-analytics2` to track granular widget interactions and pageviews, allowing for data-driven feature development.
* **🏛️ Community Vault:** A live Google Cloud Firestore database where users can permanently publish and download generated monsters, encounters, and items.
* **🧠 "Bring Your Own Key" (BYOK) Architecture:** Integrated Groq (Llama 3) for lightning-fast free generation, while allowing premium users to plug in their own OpenAI API keys for DALL-E 3 image generation.

## 📈 The Data Science Case Study
This repository is more than just an app; it is a live data engineering project. You can view the full Jupyter Notebook case study [Link to your notebook or portfolio here] detailing how I:
1. Extracted NoSQL document data from Google Cloud Firestore using Python.
2. Cleaned and parsed nested dictionary telemetry logs using `pandas`.
3. Visualized user navigation trends with `matplotlib` to identify the most popular AI tools.
