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

st.set_page_config(page_title="DM Co-Pilot | Masterwork Edition", page_icon="🐉", layout="wide")

# --- 🚦 ROUTING ---
is_analytics = st.query_params.get("analytics") == "on"
is_admin = st.query_params.get("admin") == "on"

# --- 🌌 THEME & STYLING ---
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
        border: 2px solid #00FF00 !important; width: 100%; transition: 0.3s;
    }
    .stButton>button:hover { background-color: #00FF00 !important; color: #000000 !important; }
    .dice-result { font-size: 1.5rem; font-weight: bold; color: #00FF00; text-align: center; border: 2px dashed #00FF00; padding: 5px; margin-top: 5px; }
    </style>
""", unsafe_allow_html=True)

# --- ⚙️ HELPER LOGIC ---
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
try:
    firestore_key = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
    analytics_context = streamlit_analytics.track(firestore_key_file=firestore_key, firestore_collection_name="dm_copilot_traffic")
except Exception:
    analytics_context = streamlit_analytics.track()

with analytics_context:
    st.sidebar.markdown("<h2 style='text-align: center;'>🐉 DM CO-PILOT</h2>", unsafe_allow_html=True)
    
    # --- 💰 MONETIZATION ---
    st.sidebar.markdown("### ☕ Support the Smith")
    st.sidebar.markdown("[![Support](https://img.shields.io/badge/Donate-Buy%20Me%20A%20Coffee-orange?style=for-the-badge&logo=buy-me-a-coffee)](https://www.buymeacoffee.com/calebmccombs)")
    
    st.sidebar.markdown("---")
    llm_provider = st.sidebar.radio("Engine", ["☁️ Groq (Cloud)", "💻 Ollama (Local)"])
    user_api_key = st.sidebar.text_input("Groq API Key", type="password") if llm_provider == "☁️ Groq (Cloud)" else ""
    st.sidebar.markdown("---")
    
    page = st.sidebar.radio("Navigation", [
        "📜 DM's Guide", "🤝 Matchmaker", "⚔️ Encounter Architect", "🏰 Dungeon Map Generator",
        "🧩 Trap Architect", "🎭 NPC Quick-Forge", "💎 Magic Item Artificer", "💰 Loot Hoard", "📫 Give Feedback"
    ])

    # --- 🎲 SIDEBAR DICE ROLLER ---
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🎲 Quick-Roll")
    d_col1, d_col2 = st.sidebar.columns(2)
    with d_col1:
        if st.button("d20"): st.session_state.last_roll = f"d20: {random.randint(1, 20)}"
        if st.button("d10"): st.session_state.last_roll = f"d10: {random.randint(1, 10)}"
        if st.button("d6"): st.session_state.last_roll = f"d6: {random.randint(1, 6)}"
    with d_col2:
        if st.button("d12"): st.session_state.last_roll = f"d12: {random.randint(1, 12)}"
        if st.button("d8"): st.session_state.last_roll = f"d8: {random.randint(1, 8)}"
        if st.button("d4"): st.session_state.last_roll = f"d4: {random.randint(1, 4)}"
    if "last_roll" in st.session_state:
        st.sidebar.markdown(f"<div class='dice-result'>{st.session_state.last_roll}</div>", unsafe_allow_html=True)

    if page == "📜 DM's Guide":
        st.title("📜 Welcome to the DM Co-Pilot")
        st.markdown("<div class='stat-card'>### Pro Edition Active\nUse the sidebar for navigation and the <b>Quick-Roll</b> dice utility. Admin export is now hidden.</div>", unsafe_allow_html=True)

    elif page == "💰 Loot Hoard":
        st.title("💰 Loot Hoard Generator")
        cr = st.slider("Monster Challenge Rating (CR)", 0, 30, 5)
        if st.button("Generate Hoard"):
            gp = random.randint(10, 100) * cr
            sp = random.randint(50, 500) * cr
            gems = random.randint(1, 5) if cr > 10 else 0
            art = random.choice(["Golden Chalice", "Silk Tapestry", "Jade Idol", "Ivory Statuette"]) if random.random() > 0.8 else "None"
            res = f"**Hoard Found:**\n- {gp} Gold Pieces\n- {sp} Silver Pieces\n- {gems} Rare Gems\n- **Special Object:** {art}"
            st.session_state.ai_outputs["loot"] = res
            prompt = f"Describe a flavorful D&D loot stash for a CR {cr} creature. Include {gp} gold and {art} if applicable."
            st.session_state.ai_outputs["loot_desc"] = get_ai_response(prompt, llm_provider, user_api_key)
        if "loot" in st.session_state.ai_outputs:
            st.markdown(f"<div class='stat-card'>{st.session_state.ai_outputs['loot']}\n\n{st.session_state.ai_outputs.get('loot_desc', '')}</div>", unsafe_allow_html=True)

    elif page == "🎭 NPC Quick-Forge":
        st.title("🎭 NPC Quick-Forge")
        npc_race = st.selectbox("Race", ["Human", "Elf", "Dwarf", "Tiefling", "Dragonborn"])
        npc_role = st.text_input("Role")
        if st.button("Forge NPC"):
            st.session_state.ai_outputs["npc"] = get_ai_response(f"D&D NPC: {npc_race} {npc_role}.", llm_provider, user_api_key)
        if "npc" in st.session_state.ai_outputs:
            st.markdown(f"<div class='stat-card'>{st.session_state.ai_outputs['npc']}</div>", unsafe_allow_html=True)

    elif page == "🏰 Dungeon Map Generator":
        st.title("🏰 Tactical Dungeon Map Generator")
        if st.button("Generate Layout"):
            grid = ["".join(random.choices([".", "#", "?"], weights=[70, 20, 10], k=10)) for _ in range(10)]
            st.session_state.ai_outputs["map_grid"] = "\n".join(grid)
        if "map_grid" in st.session_state.ai_outputs:
            st.code(st.session_state.ai_outputs["map_grid"])

    elif page == "🧩 Trap Architect":
        st.title("🧩 Trap Architect")
        t_lvl = st.number_input("Party Level", 1, 20, 5)
        if st.button("Construct Trap"):
            st.session_state.ai_outputs["trap"] = get_ai_response(f"Design level {t_lvl} trap.", llm_provider, user_api_key)
        if "trap" in st.session_state.ai_outputs:
            st.markdown(f"<div class='stat-card'>{st.session_state.ai_outputs['trap']}</div>", unsafe_allow_html=True)

    elif page == "📫 Give Feedback":
        st.title("📫 Tavern Suggestion Box")
        if st.button("Submit Feedback"):
            st.success("Message recorded in your Grimoire.")

    # --- 🕵️‍♂️ HIDDEN ADMIN SECTION ---
    if is_admin:
        st.markdown("---")
        with st.expander("📊 SECRET ADMIN DATA EXPORT"):
            if os.path.exists("telemetry_feedback.csv"):
                df = pd.read_csv("telemetry_feedback.csv")
                st.dataframe(df)
            else:
                st.info("No CSV data found.")

    st.sidebar.markdown("---")
    st.sidebar.download_button("📥 Export Session Log", st.session_state.session_log, file_name="DM_Log.txt")
