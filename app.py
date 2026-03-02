import streamlit as st
import pandas as pd
import streamlit_analytics2 as streamlit_analytics
import random
from datetime import datetime

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="DM Co-Pilot | Masterwork Edition", page_icon="🐉", layout="wide")

# --- 🏰 THEMED UI & ACCESSIBILITY ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=MedievalSharp&family=Crimson+Text:ital,wght@0,400;0,700;1,400&display=swap');

    .stApp {
        background-image: url("https://www.transparenttextures.com/patterns/old-map.png");
        background-color: #ffffff;
        font-family: 'Crimson Text', serif;
        color: #1a1a1a !important;
    }

    [data-testid="stSidebar"] {
        background-image: url("https://www.transparenttextures.com/patterns/dark-leather.png");
        background-color: #252525;
        border-right: 3px solid #d4af37;
    }

    /* THEMED INSTRUCTION BOX */
    .instruction-box {
        background-color: #f0f4f8;
        border-left: 5px solid #2e5a88;
        padding: 15px;
        margin-bottom: 25px;
        border-radius: 5px;
        font-size: 1.1rem;
        color: #2c3e50;
    }

    .handout-card {
        background-color: #fdf6e3;
        background-image: url("https://www.transparenttextures.com/patterns/parchment.png");
        border: 2px solid #5d4037;
        padding: 30px;
        box-shadow: 10px 10px 20px rgba(0,0,0,0.1);
        color: #2c1b0e !important;
    }

    .stat-card {
        background-color: #ffffff;
        border: 1px solid #d1d1d1;
        padding: 20px;
        border-radius: 8px;
        border-left: 10px solid #b22222;
        margin-bottom: 20px;
    }

    .stButton>button {
        background-color: #b22222 !important;
        color: #ffffff !important;
        border: 1px solid #d4af37 !important;
        font-family: 'MedievalSharp', cursive;
        font-size: 1.1rem !important;
    }

    h1, h2, h3 {
        font-family: 'MedievalSharp', cursive;
        color: #800000 !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- INITIALIZE SESSION STATES ---
if 'session_log' not in st.session_state:
    st.session_state.session_log = f"--- DM Co-Pilot Session Log ({datetime.now().strftime('%Y-%m-%d')}) ---\n"
if 'last_roll' not in st.session_state:
    st.session_state.last_roll = "Roll the dice!"

# --- ANALYTICS ---
with streamlit_analytics.track(unsafe_password=st.secrets.get("analytics_password", "local_test_password")):

    # --- SIDEBAR ---
    st.sidebar.markdown(f"<h2 style='text-align: center; color: #d4af37;'>🐉 DM CO-PILOT</h2>", unsafe_allow_html=True)
    
    # Dice Tray
    st.sidebar.markdown("### 🎲 Quick-Roll Tray")
    cols = st.sidebar.columns(3)
    dice = [4, 6, 8, 10, 12, 20]
    for i, d in enumerate(dice):
        if cols[i % 3].button(f"d{d}"):
            st.session_state.last_roll = f"d{d}: {random.randint(1, d)}"
    st.sidebar.markdown(f"<div style='text-align:center; font-size:24px; color:#d4af37; background:rgba(0,0,0,0.3); padding:5px; border-radius:5px;'>{st.session_state.last_roll}</div>", unsafe_allow_html=True)
    
    st.sidebar.markdown("---")
    llm_provider = st.sidebar.radio("Engine", ["☁️ Groq (Cloud)", "💻 Ollama (Local)"])
    user_api_key = st.sidebar.text_input("Groq API Key", type="password") if llm_provider == "☁️ Groq (Cloud)" else ""
    
    st.sidebar.markdown("---")
    page = st.sidebar.radio("Navigation", ["🤝 Matchmaker", "⚔️ Encounter Architect", "📜 Scribe's Handouts", "🌍 Worldbuilder", "🧠 Assistant"])
    
    st.sidebar.download_button("📥 Export Session Log", st.session_state.session_log, file_name="DM_Log.txt", use_container_width=True)

    # --- AI HELPER ---
    def get_ai_response(prompt):
        try:
            if llm_provider == "☁️ Groq (Cloud)":
                if not user_api_key: return "⚠️ Please enter your API Key in the sidebar to begin."
                from groq import Groq
                client = Groq(api_key=user_api_key)
                res = client.chat.completions.create(messages=[{"role": "user", "content": prompt}], model="llama-3.1-8b-instant").choices[0].message.content
            else:
                import ollama
                res = ollama.chat(model="llama3.1", messages=[{"role": "user", "content": prompt}])['message']['content']
            st.session_state.session_log += f"\n\n[TIME: {datetime.now().strftime('%H:%M')}]\n{res}\n"
            return res
        except Exception as e: return f"❌ Error: {str(e)}"

    # --- PAGE LOGIC ---
    if page == "🤝 Matchmaker":
        st.title("🤝 Campaign Matchmaker")
        st.markdown("""<div class='instruction-box'><b>How to use:</b> Paste your campaign summary and what you're looking for in a player. The AI will evaluate the 'vibe' and help you decide if a player is a good fit for your table.</div>""", unsafe_allow_html=True)
        pitch = st.text_area("The DM's Pitch & Player Preferences", placeholder="e.g. A dark gothic horror game for 4 players...")
        if st.button("Analyze Compatibility"):
            st.markdown(f"<div class='stat-card'>{get_ai_response(f'Analyze: {pitch}')}</div>", unsafe_allow_html=True)

    elif page == "⚔️ Encounter Architect":
        st.title("⚔️ Encounter Architect")
        st.markdown("""<div class='instruction-box'><b>How to use:</b> Simply type the name of any creature—real or homebrew. The AI will forge a complete 5th Edition stat block including HP, AC, Traits, and Actions.</div>""", unsafe_allow_html=True)
        h_name = st.text_input("Monster Name", placeholder="e.g. Lava Drake")
        if st.button("Generate Stat Block"):
            res = get_ai_response(f"Generate a 5e stat block for {h_name}")
            st.markdown(f"<div class='stat-card'>{res.replace('\n', '<br>')}</div>", unsafe_allow_html=True)

    elif page == "📜 Scribe's Handouts":
        st.title("📜 Scribe's Handouts")
        st.markdown("""<div class='instruction-box'><b>How to use:</b> Choose a style of document (like a Bounty Poster) and give it a 'hook' or 'secret'. The AI will write a beautiful, in-character prop you can show your players.</div>""", unsafe_allow_html=True)
        h_style = st.selectbox("Style", ["Bounty Poster", "King's Decree", "Torn Journal", "Mystic Prophecy"])
        msg = st.text_input("Core Hook", placeholder="Wanted for stealing the Duke's ring...")
        if st.button("Forge Document"):
            res = get_ai_response(f"Write a flavorful {h_style}: {msg}")
            st.markdown(f"<div class='handout-card'><h3 style='text-align:center;'>{h_style.upper()}</h3><hr>{res.replace('\n', '<br>')}</div>", unsafe_allow_html=True)

    elif page == "🌍 Worldbuilder":
        st.title("🌍 Worldbuilder's Forge")
        st.markdown("""<div class='instruction-box'><b>How to use:</b> Need instant lore? Select what you need (City, God, or Faction) and the AI will generate deep, flavorful history to flesh out your world.</div>""", unsafe_allow_html=True)
        w_type = st.selectbox("I need a...", ["City", "Deity", "Faction"])
        if st.button("Forge Lore"):
            st.markdown(f"<div class='stat-card'>{get_ai_response(f'Deep lore for {w_type}').replace('\n','<br>')}</div>", unsafe_allow_html=True)

    elif page == "🧠 Assistant":
        st.title("🧠 Digital DM Assistant")
        st.markdown("""<div class='instruction-box'><b>How to use:</b> Paste your notes from your last session. The AI will act as your co-writer, identifying plot holes or suggesting wild dramatic twists for the next game.</div>""", unsafe_allow_html=True)
        notes = st.text_area("Session Notes", placeholder="The party found the map, but killed the NPC who could read it...")
        if st.button("🔍 Analyze Plot"):
            st.markdown(f"<div class='stat-card'>{get_ai_response(f'Analyze plot twists: {notes}')}</div>", unsafe_allow_html=True)