import streamlit as st
import pandas as pd
import streamlit_analytics2 as streamlit_analytics
import random
from datetime import datetime
import os
import json
import plotly.express as px
import PyPDF2 # New dependency
from openai import OpenAI # New dependency

# --- 🚑 TRAFFIC SURGE PATCH FOR ANALYTICS ---
import streamlit_analytics2.display as sa2_display
if not hasattr(sa2_display, "original_show_results"):
    sa2_display.original_show_results = sa2_display.show_results
def safe_show_results(data, reset_data, unsafe_password):
    safe_data = data.copy()
    safe_data["widgets"] = data.get("widgets", {}).copy()
    return sa2_display.original_show_results(safe_data, reset_data, unsafe_password)
sa2_display.show_results = safe_show_results

st.set_page_config(page_title="DM Co-Pilot | Masterwork Edition", page_icon="🐉", layout="wide")

# --- 🌌 THEME & STYLING ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=MedievalSharp&display=swap');
    [data-testid="stAppViewContainer"] { background-color: #000000 !important; }
    [data-testid="stAppViewContainer"] p, span, label, li { color: #00FF00 !important; font-family: monospace !important; }
    h1, h2, h3 { font-family: 'MedievalSharp', cursive; color: #00FF00 !important; text-shadow: 0 0 10px #00FF00; }
    [data-testid="stSidebar"] { background-color: #000000 !important; border-right: 2px solid #00FF00 !important; }
    .stat-card {background-color: #0a0a0a !important; border: 1px solid #00FF00 !important; padding: 25px; border-radius: 8px; border-left: 10px solid #00FF00 !important; color: #00FF00 !important; margin-bottom: 20px; }
    .stButton>button {background-color: #000000 !important; color: #00FF00 !important; border: 2px solid #00FF00 !important; width: 100%; transition: 0.3s; }
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

# --- 🚀 MAIN APP WITH FIRESTORE ---
try:
    firestore_key = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
    analytics_context = streamlit_analytics.track(firestore_key_file=firestore_key, firestore_collection_name="dm_copilot_traffic")
except Exception:
    analytics_context = streamlit_analytics.track()

with analytics_context:
    st.sidebar.markdown("<h2 style='text-align: center;'>🐉 DM CO-PILOT</h2>", unsafe_allow_html=True)
    st.sidebar.markdown("### ☕ Support the Smith")
    st.sidebar.markdown("[![Support](https://img.shields.io/badge/Donate-Buy%20Me%20A%20Coffee-orange?style=for-the-badge&logo=buy-me-a-coffee)](https://www.buymeacoffee.com/calebmccombs)")
    
    st.sidebar.markdown("---")
    llm_provider = st.sidebar.radio("Engine", ["☁️ Groq (Cloud)", "💻 Ollama (Local)"])
    user_api_key = st.sidebar.text_input("Groq API Key", type="password") if llm_provider == "☁️ Groq (Cloud)" else ""
    
    st.sidebar.markdown("---")
    page = st.sidebar.radio("Navigation", [
        "📜 DM's Guide", 
        "🆕 Patch Notes & Roadmap", 
        "🎙️ Audio Scribe", # NEW
        "📚 PDF-Lore Chat", # NEW
        "🤝 Matchmaker", 
        "⚔️ Encounter Architect", 
        "🏰 Dungeon Map Generator", 
        "🍻 Tavern Rumor Mill", 
        "💰 Dynamic Shops", 
        "🧩 Trap Architect", 
        "🎭 NPC Quick-Forge", 
        "💎 Magic Item Artificer", 
        "💰 Loot Hoard", 
        "📫 Give Feedback"
    ])

    # --- 🎲 SIDEBAR DICE ROLLER ---
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🎲 Quick-Roll")
    d_col1, d_col2 = st.sidebar.columns(2)
    with d_col1:
        if st.button("d20"): st.session_state.last_roll = f"d20: {random.randint(1, 20)}"
        if st.button("d10"): st.session_state.last_roll = f"d10: {random.randint(1, 10)}"
    with d_col2:
        if st.button("d12"): st.session_state.last_roll = f"d12: {random.randint(1, 12)}"
        if st.button("d8"): st.session_state.last_roll = f"d8: {random.randint(1, 8)}"
    
    if "last_roll" in st.session_state:
        st.sidebar.markdown(f"<div class='dice-result'>{st.session_state.last_roll}</div>", unsafe_allow_html=True)

    # --- PAGE LOGIC ---
    if page == "📜 DM's Guide":
        st.title("📜 Welcome to the DM Co-Pilot")
        st.toast("🐉 Masterwork Edition Active!", icon="⚔️")
        st.markdown("<div class='stat-card'>### System Online\nSelect a tool from the sidebar to begin.</div>", unsafe_allow_html=True)

    elif page == "🆕 Patch Notes & Roadmap":
        st.title("🆕 Patch Notes & Roadmap")
        st.success("🚀 **Live Today:** Audio Scribe & PDF-Lore Chat Integration!")
        st.info("🗺️ **Roadmap:** Image Generation (DALL-E/Stable Diffusion) & Initiative Tracker.")

    elif page == "🎙️ Audio Scribe":
        st.title("🎙️ Audio Scribe (Whisper)")
        st.markdown("Upload a voice memo of your session. We'll transcribe it and summarize the key points.")
        audio_file = st.file_uploader("Upload Audio (mp3, wav, m4a)", type=["mp3", "wav", "m4a"])
        
        if audio_file:
            if st.button("Transcribe & Log"):
                with st.spinner("Whisper is listening..."):
                    # Whisper requires an OpenAI Key. Using Groq key as fallback if provided.
                    client = OpenAI(api_key=user_api_key if user_api_key else st.secrets.get("OPENAI_API_KEY"))
                    transcript = client.audio.transcriptions.create(model="whisper-1", file=audio_file)
                    summary = get_ai_response(f"Summarize this D&D session transcript into bullet points: {transcript.text}", llm_provider, user_api_key)
                    st.session_state.ai_outputs["audio_summary"] = summary
        
        if "audio_summary" in st.session_state.ai_outputs:
            st.markdown(f"<div class='stat-card'>{st.session_state.ai_outputs['audio_summary']}</div>", unsafe_allow_html=True)

    elif page == "📚 PDF-Lore Chat":
        st.title("📚 PDF-Lore Chat")
        st.markdown("Upload your World Anvil PDF or Homebrew Guide to chat with your lore.")
        pdf_file = st.file_uploader("Upload Lore PDF", type="pdf")
        user_query = st.text_input("Ask a question about your world:")

        if pdf_file and user_query:
            if st.button("Query Lore"):
                with st.spinner("Consulting the archives..."):
                    reader = PyPDF2.PdfReader(pdf_file)
                    # Pulling first 5 pages to avoid context window blowing up
                    text_context = ""
                    for i in range(min(5, len(reader.pages))):
                        text_context += reader.pages[i].extract_text()
                    
                    full_prompt = f"Using this lore: {text_context}\n\nQuestion: {user_query}"
                    st.session_state.ai_outputs["lore_answer"] = get_ai_response(full_prompt, llm_provider, user_api_key)

        if "lore_answer" in st.session_state.ai_outputs:
            st.markdown(f"<div class='stat-card'>{st.session_state.ai_outputs['lore_answer']}</div>", unsafe_allow_html=True)

    elif page == "🤝 Matchmaker":
        st.title("🤝 Campaign Matchmaker")
        user_pref = st.text_area("What kind of game do your players want?")
        if st.button("Generate Pitches"):
            st.session_state.ai_outputs["match"] = get_ai_response(f"Generate 3 campaign pitches for: {user_pref}", llm_provider, user_api_key)
        if "match" in st.session_state.ai_outputs:
            st.markdown(f"<div class='stat-card'>{st.session_state.ai_outputs['match']}</div>", unsafe_allow_html=True)

    elif page == "⚔️ Encounter Architect":
        st.title("⚔️ Encounter Architect")
        boss_mode = st.toggle("Enable 'Boss Mode'")
        e_lvl = st.slider("Party Level", 1, 20, 5)
        e_theme = st.text_input("Theme", placeholder="e.g., Undead swamp")
        if st.button("Build Encounter"):
            st.session_state.ai_outputs["enc"] = get_ai_response(f"Build a level {e_lvl} encounter: {e_theme}. Boss Mode: {boss_mode}", llm_provider, user_api_key)
        if "enc" in st.session_state.ai_outputs:
            st.markdown(f"<div class='stat-card'>{st.session_state.ai_outputs['enc']}</div>", unsafe_allow_html=True)
            foundry_enc = {"name": "Encounter", "type": "combat", "system": {"description": {"value": st.session_state.ai_outputs['enc']}}}
            st.download_button("📤 Export for Foundry VTT", data=json.dumps(foundry_enc), file_name="encounter.json")

    elif page == "🏰 Dungeon Map Generator":
        st.title("🏰 Tactical Dungeon Map Generator")
        if st.button("Generate Layout"):
            grid = ["".join(random.choices([".", "#", "?"], weights=[75, 20, 5], k=12)) for _ in range(12)]
            st.session_state.ai_outputs["map_grid"] = "\n".join(grid)
            st.session_state.ai_outputs["map_desc"] = get_ai_response("Describe a tactical D&D battlemap.", llm_provider, user_api_key)
        if "map_grid" in st.session_state.ai_outputs:
            st.code(st.session_state.ai_outputs["map_grid"])
            st.markdown(f"<div class='stat-card'>{st.session_state.ai_outputs.get('map_desc', '')}</div>", unsafe_allow_html=True)

    elif page == "🍻 Tavern Rumor Mill":
        st.title("🍻 Tavern Rumor Mill")
        loc = st.text_input("Location Name", "The Sword Coast")
        if st.button("Listen for Rumors"):
            st.session_state.ai_outputs["rumor"] = get_ai_response(f"Generate 3 rumors for {loc}: one true, one false, one dangerously misleading.", llm_provider, user_api_key)
        if "rumor" in st.session_state.ai_outputs:
            st.markdown(f"<div class='stat-card'>{st.session_state.ai_outputs['rumor']}</div>", unsafe_allow_html=True)

    elif page == "💰 Dynamic Shops":
        st.title("💰 Dynamic Shops")
        shop_type = st.selectbox("Shop Type", ["Blacksmith", "Alchemist", "Curio Shop"])
        if st.button("Open Shop"):
            st.session_state.ai_outputs["shop"] = get_ai_response(f"Generate a {shop_type} with a quirky shopkeeper.", llm_provider, user_api_key)
        if "shop" in st.session_state.ai_outputs:
            st.markdown(f"<div class='stat-card'>{st.session_state.ai_outputs['shop']}</div>", unsafe_allow_html=True)

    elif page == "💎 Magic Item Artificer":
        st.title("💎 Magic Item Artificer")
        rarity = st.selectbox("Rarity", ["Common", "Uncommon", "Rare", "Very Rare", "Legendary"])
        cursed = st.checkbox("Attach Narrative Curse")
        if st.button("Forge Item"):
            prompt = f"Design a {rarity} magic item."
            if cursed: prompt += " Include a deeply unsettling narrative curse."
            st.session_state.ai_outputs["magic"] = get_ai_response(prompt, llm_provider, user_api_key)
        if "magic" in st.session_state.ai_outputs:
            st.markdown(f"<div class='stat-card'>{st.session_state.ai_outputs['magic']}</div>", unsafe_allow_html=True)

    elif page == "💰 Loot Hoard":
        st.title("💰 Loot Hoard Generator")
        cr = st.slider("Monster CR", 0, 30, 5)
        if st.button("Generate Hoard"):
            gp = random.randint(10, 100) * cr
            st.session_state.ai_outputs["loot"] = f"**Hoard Found:** {gp} Gold Pieces."
            st.session_state.ai_outputs["loot_desc"] = get_ai_response(f"Flavorful loot for CR {cr}.", llm_provider, user_api_key)
        if "loot" in st.session_state.ai_outputs:
            st.markdown(f"<div class='stat-card'>{st.session_state.ai_outputs['loot']}\n\n{st.session_state.ai_outputs.get('loot_desc', '')}</div>", unsafe_allow_html=True)

    elif page == "🎭 NPC Quick-Forge":
        st.title("🎭 NPC Quick-Forge")
        if st.button("Forge NPC"):
            st.session_state.ai_outputs["npc"] = get_ai_response("Create a D&D NPC.", llm_provider, user_api_key)
        if "npc" in st.session_state.ai_outputs:
            st.markdown(f"<div class='stat-card'>{st.session_state.ai_outputs['npc']}</div>", unsafe_allow_html=True)

    elif page == "🧩 Trap Architect":
        st.title("🧩 Trap Architect")
        if st.button("Construct Trap"):
            st.session_state.ai_outputs["trap"] = get_ai_response("Design a trap.", llm_provider, user_api_key)
        if "trap" in st.session_state.ai_outputs:
            st.markdown(f"<div class='stat-card'>{st.session_state.ai_outputs['trap']}</div>", unsafe_allow_html=True)

    elif page == "📫 Give Feedback":
        st.title("📫 Tavern Suggestion Box")
        star_rating = st.radio("Rate your experience!", ["⭐", "⭐⭐", "⭐⭐⭐", "⭐⭐⭐⭐", "⭐⭐⭐⭐⭐"], index=4, horizontal=True)
        user_feedback = st.text_area("What should we add next?")
        if st.button("Submit Feedback"):
            try:
                from streamlit_gsheets import GSheetsConnection
                conn = st.connection("gsheets", type=GSheetsConnection)
                new_data = pd.DataFrame({"Timestamp": [datetime.now()], "Stars": [star_rating], "Feedback": [user_feedback]})
                existing_data = conn.read(worksheet="Sheet1", ttl=5).dropna(how="all")
                conn.update(worksheet="Sheet1", data=pd.concat([existing_data, new_data], ignore_index=True))
                st.success("Message recorded in your Grimoire.")
            except:
                st.error("Feedback link offline, check secrets.")

    # --- 💾 GLOBAL EXPORT LOGIC ---
    st.sidebar.markdown("---")
    adventure_content = f"# 🐉 DELVER'S GRIMOIRE: ADVENTURE EXPORT\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
    for key, val in st.session_state.ai_outputs.items():
        adventure_content += f"## {key.replace('_', ' ').upper()}\n{val}\n\n"
    st.sidebar.download_button("📥 Download Full Adventure (.md)", adventure_content, file_name=f"Adventure_{datetime.now().strftime('%m%d')}.md")
    st.sidebar.download_button("📥 Export Session Log (RAW)", st.session_state.session_log, file_name="DM_Log.txt")
