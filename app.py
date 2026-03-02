import streamlit as st
import pandas as pd
import streamlit_analytics2 as streamlit_analytics
import random
from datetime import datetime

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="DM Co-Pilot | Masterwork Edition", page_icon="🐉", layout="wide")

# --- 🏰 THEMED UI & HANDOUT POLISH ---
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

    /* THE "WotC" HANDOUT CARD */
    .handout-card {
        background-color: #fdf6e3;
        background-image: url("https://www.transparenttextures.com/patterns/parchment.png");
        border: 2px solid #5d4037;
        padding: 30px;
        margin: 20px 0;
        box-shadow: 10px 10px 20px rgba(0,0,0,0.2);
        position: relative;
        color: #2c1b0e !important;
        font-size: 1.2rem;
        line-height: 1.6;
        border-radius: 2px;
    }

    .stat-card {
        background-color: #ffffff;
        border: 2px solid #8b4513;
        padding: 20px;
        border-radius: 8px;
        border-left: 10px solid #b22222;
        color: #000000 !important;
        margin-bottom: 20px;
    }

    .stButton>button {
        background-color: #b22222 !important;
        color: #ffffff !important;
        border: 1px solid #d4af37 !important;
        font-family: 'MedievalSharp', cursive;
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
    st.sidebar.markdown("### 🎲 Dice Tray")
    cols = st.sidebar.columns(3)
    dice = [4, 6, 8, 10, 12, 20]
    for i, d in enumerate(dice):
        if cols[i % 3].button(f"d{d}"):
            st.session_state.last_roll = f"d{d}: {random.randint(1, d)}"
    st.sidebar.markdown(f"<div style='text-align:center; font-size:24px; color:#d4af37;'>{st.session_state.last_roll}</div>", unsafe_allow_html=True)
    
    st.sidebar.markdown("---")
    llm_provider = st.sidebar.radio("Engine", ["☁️ Groq (Cloud)", "💻 Ollama (Local)"])
    
    # API Key Input (Fixed Position)
    user_api_key = st.sidebar.text_input("Groq API Key", type="password") if llm_provider == "☁️ Groq (Cloud)" else ""
    local_model = st.sidebar.selectbox("Model", ["llama3.1", "llama3"]) if llm_provider == "💻 Ollama (Local)" else ""

    st.sidebar.markdown("---")
    page = st.sidebar.radio("Navigation", ["🤝 Matchmaker", "⚔️ Encounter Architect", "📜 Scribe's Handouts", "🌍 Worldbuilder", "🧠 Assistant"])
    
    st.sidebar.download_button("📥 Export Session Log", st.session_state.session_log, file_name="DM_Log.txt", use_container_width=True)

    # --- AI HELPER ---
    def get_ai_response(prompt):
        try:
            if llm_provider == "☁️ Groq (Cloud)":
                if not user_api_key: return "⚠️ Please enter your Groq API Key in the sidebar."
                from groq import Groq
                client = Groq(api_key=user_api_key)
                res = client.chat.completions.create(messages=[{"role": "user", "content": prompt}], model="llama-3.1-8b-instant").choices[0].message.content
            else:
                import ollama
                res = ollama.chat(model=local_model, messages=[{"role": "user", "content": prompt}])['message']['content']
            
            st.session_state.session_log += f"\n\n[TIME: {datetime.now().strftime('%H:%M')}]\n{res}\n"
            return res
        except Exception as e:
            return f"❌ Error: {str(e)}"

    # --- PAGE LOGIC ---
    if page == "🤝 Matchmaker":
        st.title("🤝 Campaign Matchmaker")
        st.info("Check player-DM compatibility.")
        pitch = st.text_area("DM's Pitch & Player Style")
        if st.button("Analyze Compatibility"):
            st.markdown(f"<div class='stat-card'>{get_ai_response(pitch)}</div>", unsafe_allow_html=True)

    elif page == "⚔️ Encounter Architect":
        st.title("⚔️ Encounter Architect")
        st.info("Forge custom monster stat blocks.")
        h_name = st.text_input("Monster Name")
        if st.button("Generate Stat Block"):
            res = get_ai_response(f"Generate 5e stats for {h_name}")
            st.markdown(f"<div class='stat-card'>{res.replace('\n', '<br>')}</div>", unsafe_allow_html=True)

    elif page == "📜 Scribe's Handouts":
        st.title("📜 Scribe's Handouts")
        st.info("Create immersive physical props for your players.")
        h_style = st.selectbox("Style", ["Bounty Poster", "King's Decree", "Torn Journal", "Mystic Prophecy"])
        msg = st.text_input("Core Hook")
        if st.button("Forge Document"):
            res = get_ai_response(f"Write a flavorful {h_style}: {msg}")
            st.markdown(f"""
                <div class='handout-card'>
                    <h3 style='text-align:center; color:#5d4037;'>{h_style.upper()}</h3>
                    <hr style='border-top: 1px solid #5d4037;'>
                    {res.replace('\n', '<br>')}
                </div>
            """, unsafe_allow_html=True)

    elif page == "🌍 Worldbuilder":
        st.title("🌍 Worldbuilder's Forge")
        w_type = st.selectbox("I need a...", ["City", "Deity", "Faction"])
        if st.button("Forge Lore"):
            st.markdown(f"<div class='stat-card'>{get_ai_response(f'Lore for {w_type}').replace('\n','<br>')}</div>", unsafe_allow_html=True)

    elif page == "🧠 Assistant":
        st.title("🧠 Digital DM Assistant")
        notes = st.text_area("Session Notes")
        if st.button("🔍 Find Plot Holes"):
            st.markdown(f"<div class='stat-card'>{get_ai_response(f'Analyze plot holes: {notes}')}</div>", unsafe_allow_html=True)