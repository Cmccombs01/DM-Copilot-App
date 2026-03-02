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
        background-color: #ffffff; /* Brightened for readability */
        font-family: 'Crimson Text', serif;
        color: #1a1a1a !important;
    }

    [data-testid="stSidebar"] {
        background-image: url("https://www.transparenttextures.com/patterns/dark-leather.png");
        background-color: #252525;
        border-right: 3px solid #d4af37;
    }

    .stat-card {
        background-color: #ffffff;
        border: 2px solid #8b4513;
        padding: 25px;
        border-radius: 8px;
        box-shadow: 4px 4px 12px rgba(0,0,0,0.1);
        margin-bottom: 25px;
        border-left: 10px solid #b22222;
        color: #000000 !important;
    }

    .guide-text {
        font-style: italic;
        color: #555;
        margin-bottom: 20px;
        font-size: 1.1rem;
    }

    .stButton>button {
        background-color: #b22222 !important;
        color: #ffffff !important;
        border: 1px solid #d4af37 !important;
        font-family: 'MedievalSharp', cursive;
        font-size: 18px !important;
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
    
    st.sidebar.markdown("### 🎲 Dice Tray")
    cols = st.sidebar.columns(3)
    dice = [4, 6, 8, 10, 12, 20]
    for i, d in enumerate(dice):
        if cols[i % 3].button(f"d{d}"):
            st.session_state.last_roll = f"d{d}: {random.randint(1, d)}"
    st.sidebar.markdown(f"<div style='text-align:center; font-size:24px; color:#d4af37; background:rgba(0,0,0,0.3); border-radius:5px;'>{st.session_state.last_roll}</div>", unsafe_allow_html=True)
    
    st.sidebar.markdown("---")
    llm_provider = st.sidebar.radio("Engine", ["☁️ Groq (Cloud)", "💻 Ollama (Local)"])
    groq_api_key = st.sidebar.text_input("Groq API Key:", type="password") if llm_provider == "☁️ Groq (Cloud)" else ""
    local_model = st.sidebar.selectbox("Model", ["llama3.1", "llama3"]) if llm_provider == "💻 Ollama (Local)" else ""

    st.sidebar.markdown("---")
    page = st.sidebar.radio("Navigation", ["🤝 Matchmaker", "⚔️ Encounter Architect", "🎭 Improv Tools", "📜 Scribe's Handouts", "🌍 Worldbuilder", "🧠 Assistant"])
    
    st.sidebar.download_button("📥 Export Session Log", st.session_state.session_log, file_name="DM_Log.txt", use_container_width=True)

    # --- AI HELPER ---
    def get_ai_response(prompt):
        try:
            if llm_provider == "☁️ Groq (Cloud)":
                if not groq_api_key: return "Enter API Key in Sidebar."
                from groq import Groq
                client = Groq(api_key=groq_api_key)
                res = client.chat.completions.create(messages=[{"role": "user", "content": prompt}], model="llama-3.1-8b-instant").choices[0].message.content
            else:
                import ollama
                res = ollama.chat(model=local_model, messages=[{"role": "user", "content": prompt}])['message']['content']
            st.session_state.session_log += f"\n\n[TIME: {datetime.now().strftime('%H:%M')}]\n{res}\n"
            return res
        except Exception as e: return f"Connection Error: {str(e)}"

    # --- PAGE LOGIC ---
    if page == "🤝 Matchmaker":
        st.title("🤝 Campaign Matchmaker")
        st.markdown("<p class='guide-text'><b>Instructions:</b> Enter your campaign pitch and a player's bio to see if they are a good fit for your table. Great for vetting new recruits!</p>", unsafe_allow_html=True)
        pitch = st.text_area("The DM's Pitch")
        if st.button("Analyze Compatibility"):
            st.markdown(f"<div class='stat-card'>{get_ai_response(f'Analyze compatibility: {pitch}')}</div>", unsafe_allow_html=True)

    elif page == "⚔️ Encounter Architect":
        st.title("⚔️ Encounter Architect")
        st.markdown("<p class='guide-text'><b>Instructions:</b> Enter a name for a custom monster. The AI will generate a 5e-compatible stat block including actions and traits.</p>", unsafe_allow_html=True)
        h_name = st.text_input("Monster Name")
        if st.button("Forge Pro Stat Block"):
            st.markdown(f"<div class='stat-card'>{get_ai_response(f'Create a 5e stat block for {h_name}').replace('\n','<br>')}</div>", unsafe_allow_html=True)

    elif page == "📜 Scribe's Handouts":
        st.title("📜 Scribe's Handouts")
        st.markdown("<p class='guide-text'><b>Instructions:</b> Select a document type and enter the 'secret message'. The AI will write a flavorful, in-universe prop you can show your players.</p>", unsafe_allow_html=True)
        h_style = st.selectbox("Style", ["Bounty Poster", "King's Decree", "Torn Journal"])
        msg = st.text_input("Message Hook")
        if st.button("Forge Document"):
            st.markdown(f"<div class='stat-card' style='font-style:italic;'>{get_ai_response(f'Write a {h_style}: {msg}').replace('\n','<br>')}</div>", unsafe_allow_html=True)

    elif page == "🎭 Improv Tools":
        st.title("🎭 Improv Tools")
        st.markdown("<p class='guide-text'><b>Instructions:</b> Use these buttons for instant inspiration during a live session. Need a magic item or a weird landmark? Just click!</p>", unsafe_allow_html=True)
        if st.button("💰 Generate Loot"):
            st.markdown(f"<div class='stat-card'>{get_ai_response('Generate a unique magic item.')}</div>", unsafe_allow_html=True)
        if st.button("🗺️ Generate Landmark"):
            res = get_ai_response("Generate a landmark with a vibe.")
            st.markdown(f"<div class='stat-card'>{res}</div>", unsafe_allow_html=True)
            # 🎶 VIBE CHECK (Soundboard Integration)
            st.markdown("---")
            st.subheader("🎵 Suggested Atmosphere")
            st.write("To set the mood for this landmark, search for this on YouTube/Spotify:")
            st.code(f"RPG Ambiance: {res.split('.')[0]}")

    elif page == "🌍 Worldbuilder":
        st.title("🌍 Worldbuilder's Forge")
        st.markdown("<p class='guide-text'><b>Instructions:</b> Flesh out your world by generating lore for cities, gods, or ancient factions.</p>", unsafe_allow_html=True)
        w_type = st.selectbox("I need a...", ["Metropolis", "Deity", "Faction"])
        if st.button("Forge Lore"):
            st.markdown(f"<div class='stat-card'>{get_ai_response(f'D&D Lore for {w_type}').replace('\n','<br>')}</div>", unsafe_allow_html=True)

    elif page == "🧠 Assistant":
        st.title("🧠 Digital DM Assistant")
        st.markdown("<p class='guide-text'><b>Instructions:</b> Paste your session notes here. The AI will look for plot holes you might have missed or suggest dramatic twists for your next game.</p>", unsafe_allow_html=True)
        notes = st.text_area("Session Notes")
        if st.button("🔍 Find Plot Holes"):
            st.markdown(f"<div class='stat-card'>{get_ai_response(f'Find plot holes: {notes}')}</div>", unsafe_allow_html=True)