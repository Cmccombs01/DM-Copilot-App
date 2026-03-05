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

# --- 🐛 LOGGING & CONFIG ---
logging.basicConfig(level=logging.ERROR)
st.set_page_config(page_title="DM Co-Pilot | Masterwork Edition", page_icon="🐉", layout="wide")

# --- 🏰 THEMED UI (SOLID PAPER READABILITY FIX) ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=MedievalSharp&family=Crimson+Text:ital,wght@0,400;0,700;1,400&display=swap');
    
    /* 1. Main App Background */
    [data-testid="stAppViewContainer"] {
        background-color: #f4ecd8 !important;
        background-image: url("https://www.transparenttextures.com/patterns/old-map.png") !important;
    }

    /* 2. Global Text Visibility: Sharp black-maroon */
    html, body, [class*="st-"], p, span, label {
        color: #1a0000 !important; 
        font-family: 'Crimson Text', serif;
        font-weight: 600 !important;
    }

    /* 3. Header Contrast: Embossed look */
    h1, h2, h3 { 
        font-family: 'MedievalSharp', cursive; 
        color: #800000 !important;
        text-shadow: 2px 2px 2px rgba(255,255,255,1) !important; 
    }

    /* 4. THE FIX: Solid Paper Expander (No transparency) */
    .st-expanderContent {
        background-color: #fffdf5 !important; 
        border: 2px solid #800000 !important;
        padding: 20px !important;
        border-radius: 8px;
        box-shadow: 4px 4px 10px rgba(0,0,0,0.3);
    }
    
    .st-expanderContent p, .st-expanderContent li {
        color: #000000 !important; 
        text-shadow: none !important;
        font-size: 1.15rem !important;
    }

    /* 5. Dropdown/Select Box Contrast */
    div[data-baseweb="select"] > div {
        background-color: #ffffff !important;
        color: #000000 !important;
        border: 2px solid #800000 !important;
    }

    /* 6. Sidebar Contrast */
    [data-testid="stSidebar"] {
        background-color: #2e0808 !important;
        border-right: 3px solid #d4af37;
    }
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
        color: #ffffff !important;
    }

    .stat-card { background-color: #ffffff; border: 2px solid #800000; padding: 20px; border-radius: 8px; box-shadow: 3px 3px 10px rgba(0,0,0,0.1); }
    
    .stButton>button { 
        background-color: #b22222 !important; 
        color: white !important; 
        font-family: 'MedievalSharp', cursive; 
        width: 100%; 
        border-radius: 5px;
        border: 2px solid #ffd700 !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- ⚖️ RECHARGE TIER LOGIC ---
def get_item_balance_rules(rarity):
    tiers = {
        "Common": "1 charge, no recharge. Minor flavor effect only.",
        "Uncommon": "Max 3 charges. Regains 1d3 charges at dawn.",
        "Rare": "Max 7 charges. Regains 1d6+1 charges at dawn.",
        "Very Rare": "Max 10 charges. Regains 1d8+2 charges at dawn.",
        "Legendary": "Max 20 charges. Regains 2d6+4 charges at dawn."
    }
    return tiers.get(rarity, "Standard 5e balancing applies.")

# --- INITIALIZE SESSION STATES ---
if 'session_log' not in st.session_state:
    st.session_state.session_log = f"--- DM Co-Pilot Session Log ({datetime.now().strftime('%Y-%m-%d')}) ---\n"
if 'ai_outputs' not in st.session_state:
    st.session_state.ai_outputs = {}

# --- AI HELPER ---
def get_ai_response(prompt, llm_provider, user_api_key):
    try:
        if llm_provider == "☁️ Groq (Cloud)":
            api_key = st.secrets.get("GROQ_API_KEY", user_api_key)
            if not api_key: return "⚠️ Please enter your Groq API Key in the sidebar."
            from groq import Groq
            client = Groq(api_key=api_key)
            res = client.chat.completions.create(messages=[{"role": "user", "content": prompt}], model="llama-3.1-8b-instant").choices[0].message.content
        else:
            import ollama
            res = ollama.chat(model="llama3.1", messages=[{"role": "user", "content": prompt}])['message']['content']
        st.session_state.session_log += f"\n\n[TIME: {datetime.now().strftime('%H:%M')}]\n{res}\n"
        return res
    except Exception as e:
        return f"❌ Error: {str(e)}"

# --- MAIN APP ---
with streamlit_analytics.track():
    st.sidebar.markdown("<h2 style='text-align: center; color: #d4af37;'>🐉 DM CO-PILOT</h2>", unsafe_allow_html=True)
    
    llm_provider = st.sidebar.radio("Engine", ["☁️ Groq (Cloud)", "💻 Ollama (Local)"])
    user_api_key = st.sidebar.text_input("Groq API Key", type="password") if llm_provider == "☁️ Groq (Cloud)" else ""
    
    st.sidebar.markdown("---")
    
    page = st.sidebar.radio("Navigation", [
        "🤝 Matchmaker", "⚔️ Encounter Architect", "🏰 Dungeon Map Generator",
        "📖 Spellbook Analytics", "🏙️ Instant City Generator", "🧩 Trap Architect",
        "🎭 NPC Quick-Forge", "📜 Scribe's Handouts", "💎 Magic Item Artificer"
    ])

    # --- TOOLS WITH GUIDED INSTRUCTIONS ---
    if page == "🤝 Matchmaker":
        st.title("🤝 Campaign Matchmaker")
        with st.expander("📜 How to use (Click to expand)"):
            st.markdown("""
            * **Step 1:** Enter your world concept (e.g., 'A desert world where water is gold').
            * **Step 2:** List what your players like (e.g., 'Mystery and dungeon crawls').
            * **Step 3:** Click generate to get 3 unique campaign hooks tailored to your group.
            """)
        
        user_val = st.text_input("Pitch/Preferences", placeholder="e.g. High fantasy, political intrigue")
        if st.button("Generate Matchmaker"):
            st.session_state.ai_outputs["match"] = get_ai_response(f"Analyze D&D campaign compatibility for: {user_val}", llm_provider, user_api_key)
        if "match" in st.session_state.ai_outputs:
            st.markdown(f"<div class='stat-card'>{st.session_state.ai_outputs['match']}</div>", unsafe_allow_html=True)
    
    elif page == "⚔️ Encounter Architect":
        st.title("⚔️ Encounter Architect")
        with st.expander("📜 How to use"):
            st.write("Input party level and theme. AI provides monsters, terrain, and a 'Tactical Twist' for the DM.")
        
        user_val = st.text_input("Party Level/Theme")
        if st.button("Generate Encounter"):
            st.session_state.ai_outputs["encounter"] = get_ai_response(f"Create a balanced D&D 5e encounter for: {user_val}", llm_provider, user_api_key)
        if "encounter" in st.session_state.ai_outputs:
            st.markdown(f"<div class='stat-card'>{st.session_state.ai_outputs['encounter']}</div>", unsafe_allow_html=True)

    elif page == "💎 Magic Item Artificer":
        st.title("💎 Magic Item Artificer")
        with st.expander("📜 How to use"):
            st.write("Pick a theme and a rarity. The AI follows 5e standard recharge rules for balance.")
        
        item_theme = st.text_input("Item Name/Type", key="magic_item_theme")
        rarity_choice = st.selectbox("Select Rarity", ["Common", "Uncommon", "Rare", "Very Rare", "Legendary"], key="magic_item_rarity")
        
        if st.button("Forge Magic Item"):
            balance = get_item_balance_rules(rarity_choice)
            prompt = f"Design a {rarity_choice} D&D 5e magic item: {item_theme}. RULES: {balance}"
            st.session_state.ai_outputs["magic_item"] = get_ai_response(prompt, llm_provider, user_api_key)
        if "magic_item" in st.session_state.ai_outputs:
            st.markdown(f"<div class='stat-card'>{st.session_state.ai_outputs['magic_item']}</div>", unsafe_allow_html=True)

    else:
        st.title(f"{page}")
        with st.expander("📜 How to use"):
            st.write(f"Describe your concept for {page} and hit Generate. AI handles the mechanics and the lore.")
        
        user_val = st.text_input("Input concept...")
        if st.button("Generate"):
            st.session_state.ai_outputs[page] = get_ai_response(f"Generate {page} content for: {user_val}", llm_provider, user_api_key)
        if page in st.session_state.ai_outputs:
            st.markdown(f"<div class='stat-card'>{st.session_state.ai_outputs[page]}</div>", unsafe_allow_html=True)

    st.sidebar.markdown("---")
    st.sidebar.download_button("📥 Export Session Log", st.session_state.session_log, file_name="DM_Log.txt", use_container_width=True)