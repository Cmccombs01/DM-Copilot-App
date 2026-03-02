# 🐉 DM Co-Pilot: AI-Powered Campaign Management Platform
[🔴 Play with the Live App Here!](https://dm-copilot-app.streamlit.app/)

## 📌 The Business Problem
Tabletop Game Masters frequently experience burnout due to the heavy administrative burden of running a campaign. Manually balancing game mechanics, filtering through hundreds of monster stats, managing player schedules, and writing weekly session summaries often takes 4+ hours of prep time per week.

## 💡 The Solution
*DM Co-Pilot* is a workflow automation web application designed to reduce prep time by 80%. It serves as an end-to-end campaign management platform that blends structured data filtering with generative AI to handle scheduling compatibility, mathematical game balancing, unstructured text summarization, and on-the-fly asset generation.

## 🛠️ Tech Stack
- **Frontend:** Streamlit (Python)
- **Data Processing & Visualization:** Pandas, Streamlit Native Charting
- **AI Engine:** Groq API (Meta Llama 3.1)
- **Logic:** Python, File I/O (Exporting), & SQL-inspired matching algorithms

Added a new tab to the Session Scribe page featuring an audio file uploader. Implemented logic to send audio bytes to the whisper-large-v3 model for transcription, then pass the output to Llama 3.1 for narrative summarization.

## 💻 How to Run Locally
1. Clone this repository to your local machine.
2. Ensure you have the required libraries installed: `pip install streamlit pandas groq`
3. Run the application via terminal: `streamlit run app.py`
4. Enter your personal Groq API key securely into the sidebar to unlock AI features!
