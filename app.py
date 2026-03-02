import streamlit as st
import pandas as pd
import streamlit_analytics2 as streamlit_analytics
import random
from datetime import datetime

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="DM Co-Pilot | Portfolio Edition", page_icon="🐉", layout="wide")

# --- 🏰 HIGH-CONTRAST PROFESSIONAL UI ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=MedievalSharp&family=Crimson+Text:ital,wght@0,400;0,700;1,400&display=swap');

    /* Main App Background - Brightened Parchment */
    .stApp {
        background-image: url("https://www.transparenttextures.com/patterns/old-map.png");
        background-color: #fcfaf5; 
        font-family: 'Crimson Text', serif;
        color: #1a1a1a !important; /* Sharp Black for Readability */
    }

    /* Sidebar - Deep Leather */
    [data-testid="stSidebar"] {
        background-image: url("https://www.transparenttextures.com/patterns/dark-leather.png");
        background-color: #252525;
        border-right: 3px solid #d4af37;
    }

    /* Ornate Divider - Bright Crimson */
    .ornate-divider {
        height: 12px;
        background-color: #b22222;
        margin: 20px 0;
        border-top: 2px solid #d4af37;
        border-bottom: 2px solid #d4af37;
        border-radius: 5px;
    }

    /* Stat Card - Ivory High-Contrast */
    .stat-card {
        background-color: #ffffff;
        border: 2px solid #8b4513;
        padding: 25px;
        border-radius: 8px;
        box-shadow: 4px 4px 12px rgba(0,0,0,0.15);
        margin-bottom: 25px;
        border-left: 10px solid #b22222;
        color: #000000 !important; /* Absolute Black for AI Text */
        font-size: 1.1rem;
    }

    /* Professional Buttons */
    .stButton>button {
        background-color: #b22222 !important;
        color: #ffffff !important;
        border: 1px solid #d4af37 !important;
        font-family: 'MedievalSharp', cursive;
        font-size: 18px !important;
        padding: 10px 20px !important;
        transition: 0.3s;
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0px 4px 15px rgba(178, 34, 34, 0.4);
    }

    /* Accessible Headers */
    h1, h2, h3 {
        font-family: 'MedievalSharp', cursive;
        color: #800000 !important; /* Fire Red */
        text-shadow: 1px 1px 1px rgba(0,0,0,0.05);
    }
    
    /* Dice Tray Styling */
    .dice-result {
        font-family: 'MedievalSharp', cursive;
        font-size: 24px;
        color: #d4af37;
        text-align: center;
        background: rgba(0,0,0,0.3);
        padding: 10px;
        border-radius: 5px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- INITIALIZE SESSION STATES ---
if 'session_log' not in st.session_state:
    st.session_state.session_log = f"--- DM Co-Pilot Session Log ({datetime.now().strftime('%Y-%m-%d')}) ---\n"
if 'last_roll' not in st.session_state:
    st.session_state.last_roll = "Roll the dice!"

# --- ANALYTICS ---
try:
    ANALYTICS_PASSWORD = st.secrets["analytics_password"]
except:
    ANALYTICS_PASSWORD = "local_test_password"

with streamlit_analytics.track(unsafe_password=ANALYTICS_PASSWORD):

    # --- SIDEBAR: DICE TRAY & NAVIGATION ---
    st.sidebar.markdown(f"<h2 style='text-align: center; color: #d4af37;'>🐉 DM CO-PILOT</h2>", unsafe_allow_html=True)
    
    # 🎲 THE DICE TRAY
    st.sidebar.markdown("### 🎲 Dice Tray")
    col_d1, col_d2, col_d3 = st.sidebar.columns(3)
    if col_d1.button("d4"): st.session_state.last_roll = f"d4: {random.randint(1,4)}"
    if col_d2.button("d6"): st.session_state.last_roll = f"d6: {random.randint(1,6)}"
    if col_d3.button("d8"): st.session_state.last_roll = f"d8: {random.randint(1,8)}"
    
    col_d4, col_d5, col_d6 = st.sidebar.columns(3)
    if col_d4.button("d10"): st.session_state.last_roll = f"d10: {random.randint(1,10)}"
    if col_d5.button("d12"): st.session_state.last_roll = f"d12: {random.randint(1,12)}"
    if col_d6.button("d20"): st.session_state.last_roll = f"d20: {random.randint(1,20)}"
    
    st.sidebar.markdown(f"<div class='dice-result'>{st.session_state.last_roll}</div>", unsafe_allow_html=True)
    
    st.sidebar.markdown("---")
    llm_provider = st.sidebar.radio("Engine", ["☁️ Groq (Cloud)", "💻 Ollama (Local)"])
    groq_api_key = st.sidebar.text_input("Groq API Key:", type="password") if llm_provider == "☁️ Groq (Cloud)" else ""
    local_model = st.sidebar.selectbox("Model", ["llama3.1", "llama3"]) if llm_provider == "💻 Ollama (Local)" else ""

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
        pitch = st.text_area("The DM's Pitch (e.g., Campaign Tone, VTT, Schedule)")
        if st.button("Analyze Compatibility"):
            res = get_ai_response(f"Analyze this D&D campaign pitch: {pitch}")
            st.markdown(f"<div class='stat-card'>{res}</div>", unsafe_allow_html=True)

    elif page == "⚔️ Encounter Architect":
        st.title("⚔️ Encounter Architect")
        st.markdown("<div class='ornate-divider'></div>", unsafe_allow_html=True)
        h_name = st.text_input("Monster Name")
        if st.button("Forge Pro Stat Block"):
            res = get_ai_response(f"Generate a 5e stat block for {h_name}")
            st.markdown(f"<div class='stat-card'>{res.replace('\n', '<br>')}</div>", unsafe_allow_html=True)

    elif page == "📜 Scribe's Handouts":
        st.title("📜 Scribe's Handouts")
        st.markdown("<div class='ornate-divider'></div>", unsafe_allow_html=True)
        h_type = st.selectbox("Document Style", ["Bounty Poster", "King's Decree", "Torn Journal Page"])
        msg = st.text_input("The Secret Message / Hook")
        if st.button("Forge Document"):
            res = get_ai_response(f"Write a flavorful {h_type} containing: {msg}")
            st.markdown(f"<div class='stat-card' style='font-style: italic;'>{res.replace('\n', '<br>')}</div>", unsafe_allow_html=True)

    elif page == "🌍 Worldbuilder":
        st.title("🌍 Worldbuilder's Forge")
        st.markdown("<div class='ornate-divider'></div>", unsafe_allow_html=True)
        w_type = st.selectbox("I need a...", ["Metropolis", "Religious Faction", "Ancient Deity"])
        if st.button("Forge Lore"):
            res = get_ai_response(f"Generate deep D&D lore for a {w_type}.")
            st.markdown(f"<div class='stat-card'>{res.replace('\n', '<br>')}</div>", unsafe_allow_html=True)

    elif page == "🧠 Assistant":
        st.title("🧠 Digital DM Assistant")
        st.markdown("<div class='ornate-divider'></div>", unsafe_allow_html=True)
        notes = st.text_area("Paste Session Notes", height=250)
        c1, c2 = st.columns(2)
        if c1.button("🔍 Analyze Plot Holes"):
            res = get_ai_response(f"Analyze these notes for plot holes: {notes}")
            st.markdown(f"<div class='stat-card'>{res.replace('\n', '<br>')}</div>", unsafe_allow_html=True)
        if c2.button("✨ Suggest Plot Twists"):
            res = get_ai_response(f"Suggest 3 twists for: {notes}")
            st.markdown(f"<div class='stat-card'>{res.replace('\n', '<br>')}</div>", unsafe_allow_html=True)

    elif page == "🎭 Improv Tools":
        st.title("🎭 Improv Tools")
        st.markdown("<div class='ornate-divider'></div>", unsafe_allow_html=True)
        if st.button("💰 Generate Loot"):
            res = get_ai_response("Unique 5e magic item with stats.")
            st.markdown(f"<div class='stat-card'>{res}</div>", unsafe_allow_html=True)
        if st.button("🗺️ Generate Landmark"):
            res = get_ai_response("A unique D&D landmark with a secret.")
            st.markdown(f"<div class='stat-card'>{res}</div>", unsafe_allow_html=True)