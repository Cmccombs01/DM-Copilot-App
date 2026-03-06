import streamlit as st
import pandas as pd
import streamlit_analytics2 as streamlit_analytics
import random
from datetime import datetime
import os
import json

# --- 🚑 TRAFFIC SURGE PATCH FOR ANALYTICS ---
import streamlit_analytics2.display as sa2_display
if not hasattr(sa2_display, "original_show_results"):
    sa2_display.original_show_results = sa2_display.show_results

def safe_show_results(data, reset_data, unsafe_password):
    safe_data = data.copy()
    safe_data["widgets"] = data.get("widgets", {}).copy()
    return sa2_display.original_show_results(safe_data, reset_data, unsafe_password)

sa2_display.show_results = safe_show_results
# --------------------------------------------

# --- 🐛 LOGGING & CONFIG ---
st.set_page_config(page_title="DM Co-Pilot | Masterwork Edition", page_icon="🐉", layout="wide")

# --- 🚦 ROUTING: DETECT ANALYTICS MODE ---
is_analytics = st.query_params.get("analytics") == "on"

if is_analytics:
    # --- 🟢 HIGH-CONTRAST ANALYST MODE (BRIGHT GREEN) ---
    st.markdown("""
        <style>
        [data-testid="stAppViewContainer"] { background-color: #0e1117 !important; }
        html, body, [class*="st-"], p, span, label, li, h1, h2, h3, div {
            color: #00FF00 !important; font-family: monospace !important;
        }
        .stButton>button { 
            background-color: #000000 !important; color: #00FF00 !important; 
            border: 2px solid #00FF00 !important; width: 100%; 
        }
        </style>
        """, unsafe_allow_html=True)
else:
    # --- 🌌 MASTERWORK HACKER THEME ---
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=MedievalSharp&display=swap');
        [data-testid="stAppViewContainer"] { background-color: #000000 !important; }
        [data-testid="stAppViewContainer"] p, span, label, li { color: #00FF00 !important; font-family: monospace !important; }
        h1, h2, h3 { font-family: 'MedievalSharp', cursive; color: #00FF00 !important; text-shadow: 0 0 10px #00FF00; }
        [data-testid="stSidebar"] { background-color: #000000 !important; border-right: 2px solid #00FF00 !important; }
        .stat-card {
            background-color: #0a0a0a !important; border: 1px solid #00FF00 !important;
            padding: 25px; border-radius: 8px; border-left: 10px solid #00FF00 !important;
            color: #00FF00 !important; margin-bottom: 20px;
        }
        .stButton>button {
            background-color: #000000 !important; color: #00FF00 !important;
            border: 2px solid #00FF00 !important; width: 100%;
        }
        input, select, textarea { background-color: #000000 !important; color: #00FF00 !important; border: 1px solid #00FF00 !important; }
        </style>
    """, unsafe_allow_html=True)

# --- ⚙️ HELPER LOGIC ---
def get_item_balance_rules(rarity):
    tiers = {
        "Common": "1 charge, no recharge.",
        "Uncommon": "Max 3 charges. Regains 1d3 at dawn.",
        "Rare": "Max 7 charges. Regains 1d6+1 at dawn.",
        "Very Rare": "Max 10 charges. Regains 1d8+2 at dawn.",
        "Legendary": "Max 20 charges. Regains 2d6+4 at dawn."
    }
    return tiers.get(rarity, "Standard 5e balancing.")

if 'session_log' not in st.session_state:
    st.session_state.session_log = f"--- DM Co-Pilot Session Log ({datetime.now().strftime('%Y-%m-%d')}) ---\n"
if 'ai_outputs' not in st.session_state:
    st.session_state.ai_outputs = {}

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

# --- 🚀 MAIN APP ---
firestore_key = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
with streamlit_analytics.track(firestore_key_file=firestore_key, firestore_collection_name="dm_copilot_traffic"):
    st.sidebar.markdown("<h2 style='text-align: center;'>🐉 DM CO-PILOT</h2>", unsafe_allow_html=True)
    llm_provider = st.sidebar.radio("Engine", ["☁️ Groq (Cloud)", "💻 Ollama (Local)"])
    user_api_key = st.sidebar.text_input("Groq API Key", type="password") if llm_provider == "☁️ Groq (Cloud)" else ""
    st.sidebar.markdown("---")
    
    page = st.sidebar.radio("Navigation", [
        "📜 DM's Guide", "🤝 Matchmaker", "⚔️ Encounter Architect", "🏰 Dungeon Map Generator",
        "🧩 Trap Architect", "🎭 NPC Quick-Forge", "💎 Magic Item Artificer", "📫 Give Feedback"
    ])

    if page == "📜 DM's Guide":
        st.title("📜 Welcome to the DM Co-Pilot")
        st.markdown("<div class='stat-card'><h3>Masterwork Instruction</h3>Select a tool from the sidebar. Use <b>🏰 Dungeon Map</b> for tactical layouts and <b>🧩 Trap Architect</b> for dangerous hazards.</div>", unsafe_allow_html=True)

    elif page == "🏰 Dungeon Map Generator":
        st.title("🏰 Tactical Dungeon Map Generator")
        col1, col2 = st.columns([1, 2])
        with col1:
            map_theme = st.selectbox("Theme", ["Stone Dungeon", "Overgrown Ruins", "Volcanic Cave", "Ice Vault"])
            map_size = st.slider("Map Scale", 5, 15, 10)
            if st.button("Generate Layout"):
                grid = []
                for r in range(map_size):
                    row = "".join(random.choices([".", ".", "#", "?"], weights=[60, 20, 15, 5], k=map_size))
                    grid.append(row)
                st.session_state.ai_outputs["map_grid"] = "\n".join(grid)
                prompt = f"Describe a tactical D&D battlemap with the theme '{map_theme}'. Include 3 environmental hazards and 1 hidden secret."
                st.session_state.ai_outputs["map_desc"] = get_ai_response(prompt, llm_provider, user_api_key)
        
        with col2:
            if "map_grid" in st.session_state.ai_outputs:
                st.markdown("### ASCII Tactical Grid")
                st.code(st.session_state.ai_outputs["map_grid"], language="text")
                st.markdown(f"<div class='stat-card'>{st.session_state.ai_outputs['map_desc']}</div>", unsafe_allow_html=True)

    elif page == "🧩 Trap Architect":
        st.title("🧩 Trap Architect")
        t_lvl = st.number_input("Average Party Level", 1, 20, 5)
        t_danger = st.select_slider("Danger Level", options=["Nasty", "Deadly", "Apocalyptic"])
        t_type = st.text_input("Trap Concept", placeholder="e.g. Swinging scythes with poison")
        
        if st.button("Construct Trap"):
            dc = 10 + (t_lvl // 2) + (2 if t_danger == "Deadly" else 5 if t_danger == "Apocalyptic" else 0)
            dmg_dice = f"{t_lvl}d10" if t_danger == "Apocalyptic" else f"{t_lvl // 2 + 1}d10"
            prompt = f"Design a D&D 5e trap: {t_type}. Danger: {t_danger}. Save DC: {dc}. Damage: {dmg_dice}. Include a 'Counter-Measure' for Rogues."
            st.session_state.ai_outputs["trap"] = get_ai_response(prompt, llm_provider, user_api_key)
            
        if "trap" in st.session_state.ai_outputs:
            st.markdown(f"<div class='stat-card'>{st.session_state.ai_outputs['trap']}</div>", unsafe_allow_html=True)

    elif page == "📫 Give Feedback":
        st.title("📫 Tavern Suggestion Box")
        with st.container():
            st.markdown("<div class='stat-card'>", unsafe_allow_html=True)
            star_rating = st.radio("### Rate your experience!", ["⭐", "⭐⭐", "⭐⭐⭐", "⭐⭐⭐⭐", "⭐⭐⭐⭐⭐"], index=4, horizontal=True)
            user_feedback = st.text_area("What features should we add next?", height=100)
            if st.button("Submit Feedback"):
                from streamlit_gsheets import GSheetsConnection
                conn = st.connection("gsheets", type=GSheetsConnection)
                new_data = pd.DataFrame({"Timestamp": [datetime.now().strftime("%Y-%m-%d %H:%M:%S")], "Stars": [star_rating], "Feedback": [user_feedback]})
                existing_data = conn.read(worksheet="Sheet1", usecols=list(range(3)), ttl=5).dropna(how="all")
                conn.update(worksheet="Sheet1", data=pd.concat([existing_data, new_data], ignore_index=True))
                st.success("Message recorded in your Grimoire.")
            st.markdown("</div>", unsafe_allow_html=True)

    elif page == "🤝 Matchmaker":
        st.title("🤝 Campaign Matchmaker")
        user_val = st.text_input("Preferences", placeholder="e.g. High magic, desert world")
        if st.button("Generate Matchmaker"):
            st.session_state.ai_outputs["match"] = get_ai_response(f"Campaign pitch for: {user_val}", llm_provider, user_api_key)
        if "match" in st.session_state.ai_outputs:
            st.markdown(f"<div class='stat-card'>{st.session_state.ai_outputs['match']}</div>", unsafe_allow_html=True)

    elif page == "💎 Magic Item Artificer":
        st.title("💎 Magic Item Artificer")
        item_theme = st.text_input("Item Name", placeholder="e.g. Cloak of Shadows")
        rarity_choice = st.selectbox("Rarity", ["Common", "Uncommon", "Rare", "Very Rare", "Legendary"])
        if st.button("Forge Item"):
            balance = get_item_balance_rules(rarity_choice)
            st.session_state.ai_outputs["magic_item"] = get_ai_response(f"Design a {rarity_choice} D&D item: {item_theme}. Rules: {balance}", llm_provider, user_api_key)
        if "magic_item" in st.session_state.ai_outputs:
            st.markdown(f"<div class='stat-card'>{st.session_state.ai_outputs['magic_item']}</div>", unsafe_allow_html=True)

    st.sidebar.markdown("---")
    st.sidebar.download_button("📥 Export Session Log", st.session_state.session_log, file_name="DM_Log.txt")
