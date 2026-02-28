# 🐉 DM Co-Pilot: AI-Powered Campaign Management Platform

## 📌 The Business Problem
Tabletop Game Masters frequently experience burnout due to the heavy administrative burden of running a campaign. Manually balancing game mechanics, filtering through hundreds of monster stats, managing player schedules, and writing weekly session summaries often takes 4+ hours of prep time per week. 

## 💡 The Solution
**DM Co-Pilot** is a workflow automation web application designed to reduce prep time by 80%. It serves as an end-to-end campaign management platform that blends structured data filtering with generative AI to handle scheduling compatibility, mathematical game balancing, unstructured text summarization, and on-the-fly asset generation.

## 🛠️ Tech Stack
* **Frontend:** Streamlit (Python)
* **Data Processing & Visualization:** Pandas, Streamlit Native Charting
* **AI Engine:** Groq API (Meta Llama 3.1)
* **Logic:** Python, File I/O (Exporting), & SQL-inspired matching algorithms

## 🚀 Core Features
* **🤝 Campaign Matchmaker:** Uses custom Python logic to filter players based on schedule/timezone constraints, then leverages **Llama 3.1** to analyze unstructured text bios to generate a "Compatibility Score" and campaign hook.
* **⚔️ Encounter Architect:** Replaces manual book-searching by using **Pandas** to load, filter, and display a Kaggle dataset of 400+ official 5.5e monsters based on dynamic Challenge Rating (CR) sliders. Features an **Interactive Scatter Plot** for CR vs. HP analysis, and a custom Python reverse-calculator for Homebrew CR estimation.
* **📜 Session Scribe:** An AI workflow automator that takes chaotic, unstructured session notes and uses prompt engineering to instantly generate a cohesive narrative journal entry. Includes **File I/O downloading** to save the text locally.
* **🎭 Quick Improv Tools:** Micro-AI generators designed to solve immediate game-design problems. Includes the **"Oh Crap" NPC Generator** and the **"Loot Anxiety" Curer**, which generates highly flavorful, mechanically balanced (non-game-breaking) magic items with 1-click text file exporting.

## 💻 How to Run Locally
1. Clone this repository to your local machine.
2. Ensure you have the required libraries installed:
   `pip install streamlit pandas groq`
3. Run the application via terminal:
   `streamlit run app.py`
4. Enter your personal Groq API key securely into the sidebar to unlock AI features!
