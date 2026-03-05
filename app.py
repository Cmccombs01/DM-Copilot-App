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

# --- 🏰 THEMED UI (CROSS-BROWSER FIX) ---
# This version ensures Edge and Firefox respect the Parchment & Crimson theme
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=MedievalSharp&family=Crimson+Text:ital,wght@0,400;0,700;1,400&display=swap');
    
    /* Force Parchment Background for Chrome, Edge, and Firefox */
    [data-testid="stAppViewContainer"] {
        background-color: #f4ecd8 !important;
        background-image: url("https://www.transparenttextures.com/patterns/old-map.png") !important;
    }

    /* Transparent Header/Toolbar */
    [data-testid="stHeader"], [data-testid="stToolbar"] {
        background-color: rgba(0,0,0,0) !important;
    }

    /* Global Text Color: Deep Crimson */
    html, body, [class*="st-"] {
        color: #4a0404 !important;
        font-family: 'Crimson Text', serif;
    }

    /* Sidebar Styling: Deep Maroon/Dark Leather */
    [data-testid="stSidebar"] {
        background-image: url("https://www.transparenttextures.com/patterns/dark-leather.png") !important;
        background-color: #2e0808 !important;
        border-right: 3px solid #d4af37;
    }
    
    /* Sidebar Text: Force White for contrast on all browsers */
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
        color: #ffffff !important;
    }

    /* Input Fields: Fix for Firefox "White-on-White" text bug */
    input, select, textarea {
        background-color: #ffffff !important;
        color: #000000 !important;
        border: 1px solid #4a0404 !important;
    }

    /* Specialized Cards */
    .stat-card { background-color: #ffffff; border: 1px solid #d1d1d1; padding: 20px; border-radius: 8px; border-left: 10px solid #b22222; margin-bottom: 20px; color: #1a1a1a; }
    .handout-card { background-color: #fdf6e3; background-image: url("https://www.transparenttextures.com/patterns/parchment.png"); border: 2px solid #5d4037; padding: 30px; box-shadow: 10px 10px 20px rgba(0,0,0,0.1); color: #2c1b0e !important; }
    
    /* Buttons: Crimson themed */
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
    """Returns strict balancing rules based on item rarity for the LLM."""
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

# --- TOOL FUNCTIONS ---
def generic_ai_tool(title, prompt_prefix, input_label, output_key, llm, key_val):
    st.title(title)
    user_val = st.text_input(input_label, key=f"in_{output_key}")
    if st.button(f"Generate {title}", key=f"btn_{output_key}"):
        with st.spinner("Consulting the Grimoire..."):
            st.session_state.ai_outputs[output_key] = get_ai_response(f"{prompt_prefix}: {user_val}", llm, key_val)
    if output_key in st.session_state.ai_outputs:
        st.markdown(f"<div class='stat-card'>{st.session_state.ai_outputs[output_key]}</div>", unsafe_allow_html=True)

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

    # --- ROUTING LOGIC ---
    if page == "🤝 Matchmaker":
        generic_ai_tool("🤝 Campaign Matchmaker", "Analyze D&D campaign compatibility for", "Pitch/Preferences", "match", llm_provider, user_api_key)
    
    elif page == "⚔️ Encounter Architect":
        generic_ai_tool("⚔️ Encounter Architect", "Create a balanced D&D 5e combat encounter for", "Party Level/Theme", "encounter", llm_provider, user_api_key)

    elif page == "🏰 Dungeon Map Generator":
        st.title("🏰 Procedural Map Generator")
        size = st.slider("Map Size", 5, 15, 8)
        if st.button("Generate Dungeon"):
            grid = [["⬛" if random.random() < 0.3 else "⬜" for _ in range(size)] for _ in range(size)]
            grid[0][0], grid[size-1][size-1] = "🚪", "🐉"
            st.session_state.ai_outputs["map_grid"] = f"<div class='dungeon-grid'>{'<br>'.join([''.join(row) for row in grid])}</div>"
        if "map_grid" in st.session_state.ai_outputs:
            st.markdown(st.session_state.ai_outputs["map_grid"], unsafe_allow_html=True)

    elif page == "📖 Spellbook Analytics":
        st.title("📖 Spellbook Analytics")
        st.info("Upload a spell CSV or view sample trends.")
        data = pd.DataFrame({"School": ["Evocation", "Necromancy", "Abjuration"], "Count": [10, 5, 8]})
        st.altair_chart(alt.Chart(data).mark_bar().encode(x='School', y='Count'))

    elif page == "🏙️ Instant City Generator":
        generic_ai_tool("🏙️ Instant City Generator", "Generate a detailed fantasy city layout including districts and 3 points of interest for", "City Name/Climate", "city", llm_provider, user_api_key)

    elif page == "🧩 Trap Architect":
        generic_ai_tool("🧩 Trap Architect", "Design a complex D&D 5e trap including trigger, effect, and countermeasure for", "Trap Level/Theme", "trap", llm_provider, user_api_key)

    elif page == "🎭 NPC Quick-Forge":
        generic_ai_tool("🎭 NPC Quick-Forge", "Generate a D&D NPC with a name, quirk, and secret for", "NPC Concept", "npc", llm_provider, user_api_key)

    elif page == "📜 Scribe's Handouts":
        st.title("📜 Scribe's Handouts")
        h_style = st.selectbox("Style", ["Wanted Poster", "King's Decree", "Torn Journal Page"])
        msg = st.text_input("Core Hook")
        if st.button("Generate Handout"):
            res = get_ai_response(f"Write a {h_style} about {msg}", llm_provider, user_api_key)
            st.session_state.ai_outputs["handout_text"] = res
            st.session_state.ai_outputs["handout_img"] = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(msg)}?width=512&height=512"
        if "handout_text" in st.session_state.ai_outputs:
            st.markdown(f"<div class='handout-card'><h3>{h_style.upper()}</h3><img src='{st.session_state.ai_outputs['handout_img']}' width='100%'/><br>{st.session_state.ai_outputs['handout_text']}</div>", unsafe_allow_html=True)

    elif page == "💎 Magic Item Artificer":
        st.title("💎 Magic Item Artificer")
        item_theme = st.text_input("Item Name/Type", placeholder="e.g. A flaming greatsword", key="magic_item_theme")
        rarity_choice = st.selectbox("Select Rarity", ["Common", "Uncommon", "Rare", "Very Rare", "Legendary"], key="magic_item_rarity")
        
        # Pull in the new Recharge Tier Logic
        balance_instructions = get_item_balance_rules(rarity_choice)
        
        if st.button("Forge Magic Item", key="btn_magic_item"):
            with st.spinner("Enchanting the artifact..."):
                prompt = f"""
                Design a {rarity_choice} D&D 5e magic item based on this theme: {item_theme}.
                STRICT BALANCING RULES: {balance_instructions}
                Include Name, Rarity, Description, Mechanics, and Attunement requirement.
                """
                st.session_state.ai_outputs["magic_item"] = get_ai_response(prompt, llm_provider, user_api_key)
        
        if "magic_item" in st.session_state.ai_outputs:
            st.markdown(f"<div class='stat-card'>{st.session_state.ai_outputs['magic_item']}</div>", unsafe_allow_html=True)

    elif page == "💀 Cursed Item Creator":
        generic_ai_tool("💀 Cursed Item Creator", "Design a magic item with a debilitating but thematic curse for", "Item Theme", "curse", llm_provider, user_api_key)

    elif page == "💰 Dynamic Shop Generator":
        generic_ai_tool("💰 Dynamic Shop Generator", "Generate a shop inventory with names, descriptions, and gold costs for", "Shop Type (e.g. Alchemist)", "shop", llm_provider, user_api_key)

    elif page == "🎒 'Pocket Trash' Loot":
        generic_ai_tool("🎒 'Pocket Trash' Loot", "List 5 weird, non-magical items found in the pockets of", "Target Creature", "trash", llm_provider, user_api_key)

    elif page == "🐉 The Dragon's Hoard":
        generic_ai_tool("🐉 The Dragon's Hoard", "Generate a massive treasure hoard including gold, gems, and art for", "Hoard CR Tier", "hoard", llm_provider, user_api_key)

    elif page == "🍻 Tavern Rumor Mill":
        generic_ai_tool("🍻 Tavern Rumor Mill", "Provide 3 rumors (1 true, 1 false, 1 misleading) about", "Location/Person", "rumors", llm_provider, user_api_key)

    elif page == "🌍 Worldbuilder":
        generic_ai_tool("🌍 Worldbuilder", "Describe a unique fantasy continent with history and geography for", "World Theme", "world", llm_provider, user_api_key)

    elif page == "📖 Session Recap Scribe":
        generic_ai_tool("📖 Session Recap Scribe", "Turn these rough notes into a dramatic narrative session recap:", "DM Notes", "recap", llm_provider, user_api_key)

    elif page == "🧠 Assistant":
        generic_ai_tool("🧠 Assistant", "You are a master DM assistant. Answer this query:", "Ask anything...", "assistant", llm_provider, user_api_key)

    elif page == "📫 Give Feedback":
        st.title("📫 Tavern Suggestion Box")
        st.text_area("What features should we add next?")
        if st.button("Submit Feedback"):
            st.success("The ravens have delivered your message!")

    st.sidebar.markdown("---")
    st.sidebar.download_button("📥 Export Session Log", st.session_state.session_log, file_name="DM_Log.txt", use_container_width=True)