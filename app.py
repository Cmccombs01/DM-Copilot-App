import streamlit as st
import pandas as pd
import streamlit_analytics2 as streamlit_analytics
import json 
from datetime import datetime

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="DM Co-Pilot | Pro Edition", page_icon="🐉", layout="wide")

# --- 🏰 ADVANCED GRAPHICS & CSS ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=MedievalSharp&family=Crimson+Text:ital,wght@0,400;0,700;1,400&display=swap');

    .stApp {
        background-image: url("https://www.transparenttextures.com/patterns/old-map.png");
        background-color: #f4ece1;
        font-family: 'Crimson Text', serif;
    }

    [data-testid="stSidebar"] {
        background-image: url("https://www.transparenttextures.com/patterns/dark-leather.png");
        background-color: #1a1a1a;
        border-right: 2px solid #d4af37;
    }

    .ornate-divider {
        height: 10px;
        background-color: #8b0000;
        margin: 20px 0;
        border-top: 2px solid #d4af37;
        border-bottom: 2px solid #d4af37;
        border-radius: 5px;
    }

    .stat-card {
        background-color: #fffaf0;
        border: 2px solid #8b4513;
        padding: 20px;
        border-radius: 5px;
        box-shadow: 3px 3px 10px rgba(0,0,0,0.2);
        margin-bottom: 20px;
        border-left: 8px solid #8b0000;
        color: #2e2e2e;
    }

    .stButton>button {
        background-color: #8b0000 !important;
        color: #f4ece1 !important;
        border: 1px solid #d4af37 !important;
        font-family: 'MedievalSharp', cursive;
        transition: 0.3s;
    }
    
    h1, h2, h3 {
        font-family: 'MedievalSharp', cursive;
        color: #4a0404 !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- INITIALIZE GLOBAL STATES ---
if 'session_log' not in st.session_state:
    st.session_state.session_log = f"--- DM Co-Pilot Session Log ({datetime.now().strftime('%Y-%m-%d')}) ---\n"

# --- ANALYTICS ---
try:
    ANALYTICS_PASSWORD = st.secrets["analytics_password"]
except:
    ANALYTICS_PASSWORD = "local_test_password"

with streamlit_analytics.track(unsafe_password=ANALYTICS_PASSWORD):

    st.sidebar.markdown(f"<h2 style='text-align: center; color: #d4af37;'>🐉 DM CO-PILOT</h2>", unsafe_allow_html=True)
    st.sidebar.markdown("<div style='text-align: center; color: #aaa; font-style: italic;'>Senior Developer Portfolio Edition</div>", unsafe_allow_html=True)
    st.sidebar.markdown("---")
    
    llm_provider = st.sidebar.radio("Computing Engine", ["☁️ Groq (Cloud)", "💻 Ollama (Local)"])
    groq_api_key = st.sidebar.text_input("Groq API Key:", type="password") if llm_provider == "☁️ Groq (Cloud)" else ""
    local_model = st.sidebar.selectbox("Active Model", ["llama3.1", "llama3"]) if llm_provider == "💻 Ollama (Local)" else ""

    st.sidebar.markdown("---")
    page = st.sidebar.radio("Navigation", ["🤝 Matchmaker", "⚔️ Encounter Architect", "🎭 Improv Tools", "📜 Scribe's Handouts", "🌍 Worldbuilder", "🧠 Assistant"])

    st.sidebar.download_button(
        label="📥 Export Session Log",
        data=st.session_state.session_log,
        file_name=f"DM_Log_{datetime.now().strftime('%m_%d_%Y')}.txt",
        use_container_width=True
    )

    # --- AI HELPER ---
    def get_ai_response(prompt):
        try:
            if llm_provider == "☁️ Groq (Cloud)":
                if not groq_api_key: return "Please enter API Key."
                from groq import Groq
                client = Groq(api_key=groq_api_key)
                res = client.chat.completions.create(messages=[{"role": "user", "content": prompt}], model="llama-3.1-8b-instant").choices[0].message.content
            else:
                import ollama
                res = ollama.chat(model=local_model, messages=[{"role": "user", "content": prompt}])['message']['content']
            
            st.session_state.session_log += f"\n\n[TIME: {datetime.now().strftime('%H:%M')}]\n{res}\n"
            return res
        except Exception as e:
            return f"Error: {str(e)}"

    # --- PAGES ---
    if page == "🤝 Matchmaker":
        st.title("🤝 Campaign Matchmaker")
        st.markdown("<div class='ornate-divider'></div>", unsafe_allow_html=True)
        pitch = st.text_area("The DM's Pitch")
        if st.button("Analyze Compatibility"):
            res = get_ai_response(f"Analyze: {pitch}")
            st.markdown(f"<div class='stat-card'>{res}</div>", unsafe_allow_html=True)

    elif page == "⚔️ Encounter Architect":
        st.title("⚔️ Encounter Architect")
        st.markdown("<div class='ornate-divider'></div>", unsafe_allow_html=True)
        h_name = st.text_input("Monster Name")
        if st.button("Generate Pro Stat Block"):
            res = get_ai_response(f"Generate a 5e stat block for {h_name}")
            st.markdown(f"<div class='stat-card'>{res.replace('\n', '<br>')}</div>", unsafe_allow_html=True)

    elif page == "📜 Scribe's Handouts":
        st.title("📜 Scribe's Handouts")
        st.markdown("<div class='ornate-divider'></div>", unsafe_allow_html=True)
        h_type = st.selectbox("Type", ["Bounty Poster", "King's Decree", "Torn Letter"])
        msg = st.text_input("Secret Message")
        if st.button("Forge Document"):
            res = get_ai_response(f"Write a {h_type} containing: {msg}")
            st.markdown(f"<div class='stat-card' style='font-style: italic; border-left: 8px solid #d4af37;'>{res.replace('\n', '<br>')}</div>", unsafe_allow_html=True)

    elif page == "🌍 Worldbuilder":
        st.title("🌍 Worldbuilder's Forge")
        st.markdown("<div class='ornate-divider'></div>", unsafe_allow_html=True)
        w_type = st.selectbox("I need a...", ["City", "Faction", "Deity", "Historical Event"])
        if st.button("Forge Lore"):
            res = get_ai_response(f"Generate deep lore for a D&D {w_type}.")
            st.markdown(f"<div class='stat-card'>{res.replace('\n', '<br>')}</div>", unsafe_allow_html=True)

    elif page == "🧠 Assistant":
        st.title("🧠 Digital DM Assistant")
        st.markdown("<div class='ornate-divider'></div>", unsafe_allow_html=True)
        notes = st.text_area("Paste Session Notes", height=200)
        c1, c2 = st.columns(2)
        if c1.button("🔍 Find Plot Holes"):
            res = get_ai_response(f"Find plot holes in: {notes}")
            st.markdown(f"<div class='stat-card'>{res.replace('\n', '<br>')}</div>", unsafe_allow_html=True)
        if c2.button("✨ Suggest Twists"):
            res = get_ai_response(f"Suggest 3 twists for: {notes}")
            st.markdown(f"<div class='stat-card'>{res.replace('\n', '<br>')}</div>", unsafe_allow_html=True)

    elif page == "🎭 Improv Tools":
        st.title("🎭 Improv Tools")
        st.markdown("<div class='ornate-divider'></div>", unsafe_allow_html=True)
        if st.button("💰 Generate Loot"):
            res = get_ai_response("Unique 5e magic item")
            st.markdown(f"<div class='stat-card'>{res}</div>", unsafe_allow_html=True)