# 🐉 DM Co-Pilot: Masterwork Edition

## AI-Powered Campaign Management & Data Analytics Workflow

[🔴 Launch the Live App](https://dm-copilot-app.streamlit.app/)

## 📌 The Mission
DM Co-Pilot was engineered to solve "Dungeon Master Burnout." By automating high-friction administrative tasks—such as math-heavy encounter balancing, procedural data generation, and session logging—this tool allows Game Masters to focus entirely on storytelling. 

This project also serves as a technical portfolio piece demonstrating the integration of Generative AI (LLMs) with traditional Data Engineering and visual analytics.

## 🚀 Key Features (Portfolio Highlights)

* **📊 Data Analytics & Engineering (Kaggle Integrations):** * Utilizes `Pandas` and `Altair` to parse through a Kaggle dataset of 5e spells (`dnd-spells.csv`), rendering visual breakdowns of magic distribution.
  * Optimized "Instant City Generator" that parses through a TSV of fantasy names (`dnd_chars_unique.tsv`) in milliseconds to generate NPC crowds, demonstrating an understanding of local data optimization vs. API reliance.
* **⚙️ VTT Data Exporting:** Generates monster stat blocks and instantly formats the data into downloadable `JSON` payloads directly compatible with Foundry Virtual Tabletop.
* **🏰 Procedural Dungeon Map Generator:** Uses Python matrices and randomized geometry to procedurally generate 2D grid maps for spontaneous dungeon crawls.
* **📈 Total Event Tracker:** Features a silent background logger that tracks user interactions, page navigation, and dice rolls, piping the data directly into a Google Sheets database for behavioral analysis.
* **🖼️ AI Image & Prop Forge:** Uses the Pollinations API to generate immersive, in-universe image props (like Wanted Posters and Mystic Prophecies) alongside contextual text.
* **💀 Advanced TTRPG Generators:** Features a suite of custom-prompted LLM tools including a Cursed Item Creator, a Tavern Rumor Mill, Dynamic Shops, and a Dragon's Hoard treasure calculator.
* **💾 Session Ledger & Export:** A persistent global memory system using Streamlit Session State that tracks every AI interaction, allowing DMs to download their entire session history as a `.txt` file.

## 🛠️ Technical Architecture
* **Frontend:** Streamlit (Python) with custom CSS injection for "Parchment & Crimson" branding.
* **AI Orchestration:** Dual-engine support for *Groq (Meta Llama 3.1)* for cloud speed and *Ollama* for local privacy.
* **Data Layer:** `Pandas` and `Altair` for local dataset manipulation, JSON handling for VTT payloads, and Google Sheets API for cloud data logging.

## 📈 Impact & Analytics
This project is built with user-retention in mind, featuring an integrated Data Dashboard via *Streamlit Analytics* to track feature engagement and user flow, ensuring the tool evolves based on actual DM needs and data-driven insights.
