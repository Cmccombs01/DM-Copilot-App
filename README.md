# 🐉 DM-Copilot-Cloud (v5.0 Masterwork Edition)

**The Ultimate AI-Powered Toolkit for Dungeon Masters.**
DM-Copilot-Cloud is an enterprise-grade Streamlit web application designed to eliminate prep time and elevate live tabletop roleplaying games. By combining Retrieval-Augmented Generation (RAG) with strict formatting constraints, it acts as a trustworthy campaign historian, a tactical encounter builder, and an automatic VTT asset forge.

---

## ✨ Core Features

### 🧠 The Campaign Brain (Zero-Hallucination RAG)
Upload your campaign notes, world lore, and PDFs directly into the app.
* **Powered by FAISS:** Uses high-speed local vector databases to instantly retrieve relevant lore.
* **Strict Citations:** The AI is strictly prompt-engineered to prevent hallucinations. It acts as a historian, providing exact citations (e.g., `[Source: Page 12]`) based *only* on the documents provided.

### 🐉 Tactical Bestiary & Auto-Forge
Generate completely custom 5e monsters formatted as structured JSON data for direct import into Foundry VTT and Roll20.
* **Veteran Combat Tactics:** Automatically generates brutal, round-by-round combat strategies (Openings, Reactions, Desperation moves) injected directly into the monster's JSON stat block.
* **Token Auto-Forge:** With a single click, the app reads the newly generated JSON data and uses **DALL-E 3** to automatically forge a custom, top-down VTT token perfectly matching the creature's description.

### 📊 Omniscient Admin Dashboard (Telemetry)
A password-protected developer portal to monitor live application usage.
* **Firestore Sync:** Reads live database traffic directly from Firebase.
* **Data Visualization:** Uses `Seaborn` and `Matplotlib` to render beautiful, clean charts showing exactly which tools and features DMs are utilizing the most in real-time.

---

## 🛠️ Tech Stack & Architecture

* **Frontend:** [Streamlit](https://streamlit.io/) (Python)
* **AI & LLMs:** OpenAI API (GPT-4o, DALL-E 3)
* **Vector Database:** `FAISS` (Facebook AI Similarity Search) & `NumPy`
* **Backend Database:** Firebase / Firestore (NoSQL)
* **Data Science:** `Pandas`, `Seaborn`, `Matplotlib`

---

## 🚀 Local Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone [https://github.com/YourUsername/DM-Copilot-Cloud.git](https://github.com/YourUsername/DM-Copilot-Cloud.git)
   cd DM-Copilot-Cloud
