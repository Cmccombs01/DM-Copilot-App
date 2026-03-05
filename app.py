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

# --- 🏰 THEMED UI (CROSS-BROWSER & CONTRAST FIX) ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=MedievalSharp&family=Crimson+Text:ital,wght@0,400;0,700;1,400&display=swap');
    
    [data-testid="stAppViewContainer"] {
        background-color: #f4ecd8 !important;
        background-image: url("https://www.transparenttextures.com/patterns/old-map.png") !important;
    }

    [data-testid="stHeader"], [data-testid="stToolbar"] {
        background-color: rgba(0,0,0,0) !important;
    }

    html, body, [class*="st-"] {
        color: #4a0404 !important;
        font-family: 'Crimson Text', serif;
    }

    [data-testid="stSidebar"] {
        background-image: url("https://www.transparenttextures.com/patterns/dark-leather.png") !important;
        background-color: #2e0808 !important;
        border-right: 3px solid #d4af37;
    }
    
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
        color: #ffffff !important;
    }

    /* Fix for "Select Rarity" box - High Contrast for Edge/Firefox */
    div[data-baseweb="select"] > div {
        background-color: #ffffff !important;
        color: #000000 !important;
        border: 1px solid #4a0404 !important;
    }

    div[role="listbox"] ul {
        background-color: #ffffff !important;
    }
    
    div[role="option"] {
        color: #000000 !important;
    }

    .stat-card { background-color: #ffffff; border: 1px solid #d1d1d1; padding: 20px; border-radius: 8px; border-left: 10px solid #b22222; margin-bottom: 20px; color: #1a1a1a; }
    .handout-card { background-color: #fdf6e3; background-image: url("https://www.transparenttextures.com/patterns/parchment.png"); border: 2px solid #5d4037; padding: 30px; box-shadow: 10px 10px 20px rgba(0,0,0,0.1); color: #2c1b0e !important; }
    
    .stButton>button { 
        background-color: #b22222 !important; 
        color: white !important; 
        font-family: 'MedievalSharp', cursive; 
        width: 100%; 
        border-radius: 5px;
        border: none !important;
    }
    
    h1, h2, h3 { font-family: 'MedievalSharp', cursive; color: #800000 !important; }
    .dungeon-grid { font-size: 24px; line-height: 1.1; text-align: center; background-color: #2c3e50; padding: 20px; border-radius: 10px; border: 4px solid #b22222; }
    </style>
    """, unsafe_allow_html=True)

# --- ⚖️ RECHARGE TIER LOGIC ---
def get_item_balance_rules(rarity):
    tiers = {
        "Common": "1 charge, no recharge. Minor flavor effect only.",
        "Uncommon": "Max 3 charges. Regains 1d3 charges at dawn. Level 1-2 spell power.",
        "Rare": "Max 7 charges. Regains 1d6+1 charges at dawn. Level 3-4 spell power.",
        "Very Rare": "Max 10 charges. Regains 1d8+2 charges at dawn. Level 5-6 spell power.",
        "Legendary": "Max 20 charges. Regains 2d6+4 charges at dawn. Level 7+ spell power."
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
        "🎭 NPC Quick-Forge", "📜 Scribe's Handouts", "💎 Magic Item Artificer", 
        "💀 Cursed Item Creator", "💰 Dynamic Shop Generator", "🎒 'Pocket Trash' Loot", 
        "🐉 The Dragon's Hoard", "🍻 Tavern Rumor Mill", "🌍 Worldbuilder", 
        "📖 Session Recap Scribe", "🧠 Assistant", "📫 Give Feedback"
    ])

    # --- ROUTING LOGIC WITH INSTRUCTIONS ---
    
    if page == "🤝 Matchmaker":
        st.title("🤝 Campaign Matchmaker")
        with st.expander("📜 How to use"):
            st.write("Enter your campaign pitch and player preferences. The AI will analyze compatibility and generate 3 custom 'Hooks' to get your group excited.")
        
        user_val = st.text_input("Pitch/Preferences", placeholder="e.g. High fantasy, political intrigue, players want to be pirates")
        if st.button("Generate Matchmaker"):
            st.session_state.ai_outputs["match"] = get_ai_response(f"Analyze D&D campaign compatibility for: {user_val}", llm_provider, user_api_key)
        if "match" in st.session_state.ai_outputs:
            st.markdown(f"<div class='stat-card'>{st.session_state.ai_outputs['match']}</div>", unsafe_allow_html=True)
    
    elif page == "⚔️ Encounter Architect":
        st.title("⚔️ Encounter Architect")
        with st.expander("📜 How to use"):
            st.write("Input the party's level and the encounter theme. The AI will build a balanced combat encounter with monsters, terrain hazards, and tactical advice.")
        
        user_val = st.text_input("Party Level/Theme")
        if st.button("Generate Encounter"):
            st.session_state.ai_outputs["encounter"] = get_ai_response(f"Create a balanced D&D 5e encounter for: {user_val}", llm_provider, user_api_key)
        if "encounter" in st.session_state.ai_outputs:
            st.markdown(f"<div class='stat-card'>{st.session_state.ai_outputs['encounter']}</div>", unsafe_allow_html=True)

    elif page == "🏰 Dungeon Map Generator":
        st.title("🏰 Procedural Map Generator")
        with st.expander("📜 How to use"):
            st.write("Choose your grid size and hit generate. This tool uses a random seed to create a tactical 'Dungeon Matrix'. ⬛ = Wall, ⬜ = Floor.")
        
        size = st.slider("Map Size", 5, 15, 8)
        if st.button("Generate Dungeon"):
            grid = [["⬛" if random.random() < 0.3 else "⬜" for _ in range(size)] for _ in range(size)]
            grid[0][0], grid[size-1][size-1] = "🚪", "🐉"
            st.session_state.ai_outputs["map_grid"] = f"<div class='dungeon-grid'>{'<br>'.join([''.join(row) for row in grid])}</div>"
        if "map_grid" in st.session_state.ai_outputs:
            st.markdown(st.session_state.ai_outputs["map_grid"], unsafe_allow_html=True)

    elif page == "📖 Spellbook Analytics":
        st.title("📖 Spellbook Analytics")
        with st.expander("📜 How to use"):
            st.write("Upload a CSV of your spells (Name, School, Level) to see a visual breakdown of your magic schools. If no file is uploaded, sample trends are shown.")
        
        uploaded_file = st.file_uploader("Upload a spell CSV", type="csv")
        df = pd.read_csv(uploaded_file) if uploaded_file else pd.DataFrame({"School": ["Evoc", "Necro", "Abjur"], "Count": [12, 5, 8]})
        
        chart = alt.Chart(df).mark_bar(color='#b22222').encode(x='School', y='Count', tooltip=['School', 'Count']).properties(height=400)
        st.altair_chart(chart, use_container_width=True)

    elif page == "💎 Magic Item Artificer":
        st.title("💎 Magic Item Artificer")
        with st.expander("📜 How to use"):
            st.write("Define a theme and select a rarity. The 'Masterwork' logic ensures the item's charges and power levels are mechanically balanced for D&D 5e.")
        
        item_theme = st.text_input("Item Name/Type", key="magic_item_theme")
        rarity_choice = st.selectbox("Select Rarity", ["Common", "Uncommon", "Rare", "Very Rare", "Legendary"], key="magic_item_rarity")
        
        if st.button("Forge Magic Item"):
            balance = get_item_balance_rules(rarity_choice)
            prompt = f"Design a {rarity_choice} D&D 5e magic item: {item_theme}. RULES: {balance}"
            st.session_state.ai_outputs["magic_item"] = get_ai_response(prompt, llm_provider, user_api_key)
        if "magic_item" in st.session_state.ai_outputs:
            st.markdown(f"<div class='stat-card'>{st.session_state.ai_outputs['magic_item']}</div>", unsafe_allow_html=True)

    elif page == "📜 Scribe's Handouts":
        st.title("📜 Scribe's Handouts")
        with st.expander("📜 How to use"):
            st.write("Pick a style and a plot hook. The Scribe will write the text and use AI to generate a matching visual reference for your players.")
        
        h_style = st.selectbox("Style", ["Wanted Poster", "King's Decree", "Torn Journal Page"])
        msg = st.text_input("Core Hook")
        if st.button("Generate Handout"):
            st.session_state.ai_outputs["handout_text"] = get_ai_response(f"Write a {h_style} about {msg}", llm_provider, user_api_key)
            st.session_state.ai_outputs["handout_img"] = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(msg)}?width=512&height=512"
        if "handout_text" in st.session_state.ai_outputs:
            st.markdown(f"<div class='handout-card'><h3>{h_style.upper()}</h3><img src='{st.session_state.ai_outputs['handout_img']}' width='100%'/><br>{st.session_state.ai_outputs['handout_text']}</div>", unsafe_allow_html=True)

    # --- ALL OTHER TOOLS (GENERIC PATTERN) ---
    else:
        st.title(f"{page}")
        with st.expander("📜 How to use"):
            st.write(f"The {page} uses LLM inference to generate lore and mechanics. Simply input your prompt and click generate.")
        
        user_val = st.text_input("Input concept...")
        if st.button("Generate"):
            st.session_state.ai_outputs[page] = get_ai_response(f"Generate {page} content for: {user_val}", llm_provider, user_api_key)
        if page in st.session_state.ai_outputs:
            st.markdown(f"<div class='stat-card'>{st.session_state.ai_outputs[page]}</div>", unsafe_allow_html=True)

    st.sidebar.markdown("---")
    st.sidebar.download_button("📥 Export Session Log", st.session_state.session_log, file_name="DM_Log.txt", use_container_width=True)