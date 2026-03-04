import streamlit as st
import pandas as pd
import streamlit_analytics2 as streamlit_analytics
import random
from datetime import datetime
import streamlit.components.v1 as components
import logging
import altair as alt
import json
import urllib.parse
import os

# --- 🐛 ADVANCED ERROR LOGGING SETUP ---
logging.basicConfig(
    level=logging.ERROR,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="DM Co-Pilot | Masterwork Edition", page_icon="🐉", layout="wide")

# --- CSS STYLES ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=MedievalSharp&family=Crimson+Text:ital,wght@0,400;0,700;1,400&display=swap');
    .stApp { background-image: url("https://www.transparenttextures.com/patterns/old-map.png"); background-color: #ffffff; font-family: 'Crimson Text', serif; color: #1a1a1a !important; }
    [data-testid="stSidebar"] { background-image: url("https://www.transparenttextures.com/patterns/dark-leather.png"); background-color: #252525; border-right: 3px solid #d4af37; }
    .stat-card { background-color: #ffffff; border: 1px solid #d1d1d1; padding: 20px; border-radius: 8px; border-left: 10px solid #b22222; margin-bottom: 20px; color: #1a1a1a; }
    .handout-card { background-color: #fdf6e3; background-image: url("https://www.transparenttextures.com/patterns/parchment.png"); border: 2px solid #5d4037; padding: 30px; box-shadow: 10px 10px 20px rgba(0,0,0,0.1); color: #2c1b0e !important; }
    .stButton>button { background-color: #b22222 !important; color: white !important; font-family: 'MedievalSharp', cursive; }
    h1, h2, h3 { font-family: 'MedievalSharp', cursive; color: #800000 !important; }
    .dungeon-grid { font-size: 28px; line-height: 1.1; text-align: center; background-color: #2c3e50; padding: 20px; border-radius: 10px; border: 4px solid #b22222; }
    </style>
    """, unsafe_allow_html=True)

# --- INITIALIZE SESSION STATES ---
if 'session_log' not in st.session_state:
    st.session_state.session_log = f"--- DM Co-Pilot Session Log ({datetime.now().strftime('%Y-%m-%d')}) ---\n"
if 'ai_outputs' not in st.session_state:
    st.session_state.ai_outputs = {}

# --- AI HELPER ---
def get_ai_response(prompt, llm_provider, user_api_key):
    try:
        if llm_provider == "☁️ Groq (Cloud)":
            # Priority: 1. Streamlit Secrets, 2. Manual Sidebar Entry
            api_key = st.secrets.get("GROQ_API_KEY", user_api_key)
            if not api_key: 
                return "⚠️ Please enter your Groq API Key in the sidebar."
            from groq import Groq
            client = Groq(api_key=api_key)
            res = client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}], 
                model="llama-3.1-8b-instant"
            ).choices[0].message.content
        else:
            import ollama
            res = ollama.chat(model="llama3.1", messages=[{"role": "user", "content": prompt}])['message']['content']
        
        st.session_state.session_log += f"\n\n[TIME: {datetime.now().strftime('%H:%M')}]\n{res}\n"
        return res
    except Exception as e:
        logger.error(f"AI Error: {e}")
        return "❌ Connection error. Please check your API key or Local Ollama status."

# --- TAB FUNCTIONS ---
def show_matchmaker(llm, key):
    st.title("🤝 Campaign Matchmaker")
    pitch = st.text_area("DM's Pitch & Player Preferences", placeholder="e.g. Dark gothic horror for 4 players...", key="pitch_input")
    if st.button("Analyze Compatibility", key="match_btn"):
        with st.spinner("Analyzing..."):
            st.session_state.ai_outputs["Matchmaker"] = get_ai_response(f'Analyze compatibility for: {pitch}', llm, key)
    if "Matchmaker" in st.session_state.ai_outputs:
        st.markdown(f"<div class='stat-card'>{st.session_state.ai_outputs['Matchmaker']}</div>", unsafe_allow_html=True)

def show_npc_forge(llm, key):
    st.title("🎭 NPC Quick-Forge")
    concept = st.text_input("NPC Concept", placeholder="e.g. A thief with a heart of gold", key="npc_input")
    if st.button("Forge NPC", key="npc_btn"):
        with st.spinner("Forging..."):
            st.session_state.ai_outputs["NPC"] = get_ai_response(f"Generate a unique NPC: {concept}", llm, key)
    if "NPC" in st.session_state.ai_outputs:
        st.markdown(f"<div class='stat-card'>{st.session_state.ai_outputs['NPC']}</div>", unsafe_allow_html=True)

def show_handouts(llm, key):
    st.title("📜 Scribe's Handouts")
    h_style = st.selectbox("Style", ["Wanted Poster", "King's Decree", "Torn Journal Page"], key="h_style")
    msg = st.text_input("Core Hook", placeholder="Wanted for stealing...", key="h_hook")
    if st.button("Forge Document", key="h_btn"):
        with st.spinner("Writing..."):
            st.session_state.ai_outputs["Handout"] = get_ai_response(f"Write a {h_style}: {msg}", llm, key)
            safe_prompt = urllib.parse.quote(f"Fantasy {h_style} prop: {msg}")
            st.session_state.ai_outputs["Handout_Img"] = f"https://image.pollinations.ai/prompt/{safe_prompt}?width=512&height=512&nologo=true"
    
    if "Handout" in st.session_state.ai_outputs:
        st.markdown(f"<div class='handout-card'><h3>{h_style.upper()}</h3>", unsafe_allow_html=True)
        st.image(st.session_state.ai_outputs.get("Handout_Img", ""), use_container_width=True)
        st.write(st.session_state.ai_outputs["Handout"])
        st.markdown("</div>", unsafe_allow_html=True)

def show_dungeon_gen():
    st.title("🏰 Dungeon Map Generator")
    size = st.slider("Map Size", 5, 15, 8, key="map_slider")
    if st.button("Generate Matrix", key="map_btn"):
        grid = [["⬛" if random.random() < 0.3 else "⬜" for _ in range(size)] for _ in range(size)]
        grid[0][0], grid[size-1][size-1] = "🚪", "🐉"
        st.session_state.ai_outputs["Map"] = f"<div class='dungeon-grid'>{'<br>'.join([''.join(row) for row in grid])}</div>"
    if "Map" in st.session_state.ai_outputs:
        st.markdown(st.session_state.ai_outputs["Map"], unsafe_allow_html=True)

# --- MAIN APP ---
with streamlit_analytics.track():
    st.sidebar.markdown("<h2 style='text-align: center; color: #d4af37;'>🐉 DM CO-PILOT</h2>", unsafe_allow_html=True)
    
    # Engine Selection
    llm_provider = st.sidebar.radio("Engine", ["☁️ Groq (Cloud)", "💻 Ollama (Local)"], key="engine_choice")
    user_api_key = ""
    if llm_provider == "☁️ Groq (Cloud)":
        user_api_key = st.sidebar.text_input("Groq API Key", type="password", key="api_key_input")
    
    st.sidebar.markdown("---")
    
    # NAVIGATION MAPPING
    # To fix "Broken Tabs", we map labels to functions directly
    nav_map = {
        "🤝 Matchmaker": lambda: show_matchmaker(llm_provider, user_api_key),
        "🎭 NPC Quick-Forge": lambda: show_npc_forge(llm_provider, user_api_key),
        "📜 Scribe's Handouts": lambda: show_handouts(llm_provider, user_api_key),
        "🏰 Dungeon Map Generator": show_dungeon_gen,
        # Placeholders for other tabs
        "⚔️ Encounter Architect": lambda: st.title("⚔️ Encounter Architect (Coming Soon)"),
        "📖 Spellbook Analytics": lambda: st.title("📖 Spellbook Analytics (Coming Soon)"),
        "🏙️ Instant City Generator": lambda: st.title("🏙️ City Generator (Coming Soon)"),
        "🧩 Trap Architect": lambda: st.title("🧩 Trap Architect (Coming Soon)"),
        "💎 Magic Item Artificer": lambda: st.title("💎 Magic Item Artificer (Coming Soon)"),
        "💀 Cursed Item Creator": lambda: st.title("💀 Cursed Item Creator (Coming Soon)"),
        "💰 Dynamic Shop Generator": lambda: st.title("💰 Shop Generator (Coming Soon)"),
        "🎒 'Pocket Trash' Loot": lambda: st.title("🎒 Pocket Trash (Coming Soon)"),
        "🐉 The Dragon's Hoard": lambda: st.title("🐉 Dragon's Hoard (Coming Soon)"),
        "🍻 Tavern Rumor Mill": lambda: st.title("🍻 Rumor Mill (Coming Soon)"),
        "🌍 Worldbuilder": lambda: st.title("🌍 Worldbuilder (Coming Soon)"),
        "📖 Session Recap Scribe": lambda: st.title("📖 Session Recap (Coming Soon)"),
        "🧠 Assistant": lambda: st.title("🧠 Assistant (Coming Soon)"),
        "📫 Give Feedback": lambda: st.title("📫 Feedback (Coming Soon)")
    }

    selection = st.sidebar.radio("Navigation", list(nav_map.keys()))
    
    # Execute the selected function
    nav_map[selection]()

    st.sidebar.markdown("---")
    st.sidebar.download_button("📥 Export Session Log", st.session_state.session_log, file_name="DM_Log.txt", use_container_width=True)