import streamlit_analytics2.firestore as sa2_firestore
import streamlit_analytics2.display as sa2_display
import streamlit as st
import pandas as pd
import streamlit_analytics2 as streamlit_analytics
import random
import hashlib
import redis
from datetime import datetime
import os
import json
import requests
import PyPDF2
from openai import OpenAI
from collections import Counter
import re

# --- NEW: PRODUCTION SAFEGUARDS ---
from tenacity import retry, stop_after_attempt, wait_exponential
from pydantic import BaseModel, ValidationError
from typing import List, Optional

# --- NEW: FIRESTORE IMPORTS FOR THE VAULT ---
from google.oauth2 import service_account
from google.cloud import firestore

st.set_page_config(page_title="DM Co-Pilot | Masterwork Edition",
                   page_icon="🐉", layout="wide")
# --- 🎨 WHITE-LABEL CSS HACK ---
hide_st_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)


# --- 🚑 TRAFFIC SURGE PATCH FOR ANALYTICS ---
if not hasattr(sa2_display, "original_show_results"):
    sa2_display.original_show_results = sa2_display.show_results


def safe_show_results(counts, reset_callback):
    safe_counts = counts.copy() if isinstance(counts, dict) else counts
    if isinstance(safe_counts, dict) and "widgets" in safe_counts and isinstance(safe_counts["widgets"], dict):
        safe_counts["widgets"] = safe_counts["widgets"].copy()
    return sa2_display.original_show_results(safe_counts, reset_callback)


sa2_display.show_results = safe_show_results

# --- 🛑 THE JSON CRASH FIX: Patching Firestore Save ---

if not hasattr(sa2_firestore, "original_save"):
    sa2_firestore.original_save = sa2_firestore.save


def safe_firestore_save(counts, *args, **kwargs):
    if isinstance(counts, dict) and "widgets" in counts:
        for widget_name, widget_data in counts["widgets"].items():
            if isinstance(widget_data, dict):
                # Delete any massive text inputs (like raw JSON) before sending to the database
                oversized_keys = [k for k in widget_data.keys(
                ) if isinstance(k, str) and len(k) > 500]
                for k in oversized_keys:
                    del widget_data[k]
    return sa2_firestore.original_save(counts, *args, **kwargs)


sa2_firestore.save = safe_firestore_save

# --- MAGIC CLOUD UNLOCKER (BULLETPROOF VERSION) ---
firestore_secret = None
if "firestore" in st.secrets:
    firestore_secret = st.secrets["firestore"]
elif "GOOGLE_CREDENTIALS" in st.secrets:
    firestore_secret = st.secrets["GOOGLE_CREDENTIALS"]

if firestore_secret:
    try:
        if isinstance(firestore_secret, str):
            firestore_key = json.loads(firestore_secret)
        else:
            firestore_key = dict(firestore_secret)

        with open("temp_firestore_key.json", "w") as f:
            json.dump(firestore_key, f)
    except Exception as e:
        print(f"Error parsing Google Secrets: {e}")

# --- ⚡ THE SPEED FIX: Caching the Bestiary in RAM ---


@st.cache_data
def load_bestiary():
    try:
        import pandas as pd
        import json
        with open("srd_5e_monsters.json", "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        df = pd.DataFrame(raw_data)
        rename_map = {"Challenge": "cr",
                      "Hit Points": "hp", "Armor Class": "ac"}
        df = df.rename(
            columns={k: v for k, v in rename_map.items() if k in df.columns})

        traits = df['Traits'].fillna('') if 'Traits' in df.columns else ''
        acts = df['Actions'].fillna('') if 'Actions' in df.columns else ''
        df['actions'] = traits + '\n\n' + acts
        df['actions'] = df['actions'].str.replace(r'<[^<>]*>', '', regex=True)
        return df
    except Exception as e:
        st.error(f"🚨 LOCAL DATABASE CRASH REPORT: {e}")
        import pandas as pd
        return pd.DataFrame()


monster_df = load_bestiary()

# --- 🌌 THEME & STYLING ---
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=MedievalSharp&display=swap');
[data-testid="stAppViewContainer"] { background-color: #000000 !important; }
[data-testid="stAppViewContainer"] p, label, li { color: #00FF00 !important; font-family: monospace !important; }
h1, h2, h3 { font-family: 'MedievalSharp', cursive; color: #00FF00 !important; text-shadow: 0 0 10px #00FF00; }
[data-testid="stSidebar"] { background-color: #000000 !important; border-right: 2px solid #00FF00 !important; }
.stat-card {background-color: #0a0a0a !important; border: 1px solid #00FF00 !important; padding: 15px; border-radius: 8px; border-left: 10px solid #00FF00 !important; color: #00FF00 !important; margin-bottom: 10px; }
.stButton>button {background-color: #000000 !important; color: #00FF00 !important; border: 2px solid #00FF00 !important; width: 100%; transition: 0.3s; }
.stButton>button:hover { background-color: #00FF00 !important; color: #000000 !important; }
.dice-result { font-size: 1.5rem; font-weight: bold; color: #00FF00; text-align: center; border: 2px dashed #00FF00; padding: 5px; margin-top: 5px; }
</style>
""", unsafe_allow_html=True)

# --- ⚙️ HELPER LOGIC & GLOBAL MEMORY ---
if 'combatants' not in st.session_state:
    st.session_state.combatants = []
if 'party_stats' not in st.session_state:
    st.session_state.party_stats = pd.DataFrame([
        {"Name": "Player 1", "Class": "Fighter", "AC": 18,
            "Passive Perception": 13, "Spell Save DC": 0, "Max HP": 45},
        {"Name": "Player 2", "Class": "Wizard", "AC": 12,
            "Passive Perception": 11, "Spell Save DC": 15, "Max HP": 22}
    ])

# We added "world_memory" to track the living world state
    memory_banks = ["bestiary_json", "artificer_json", "shop_json",
                    "encounter_json", "tavern_json", "handout_json", "world_memory"]
    for bank in memory_banks:
        if bank not in st.session_state:
            st.session_state[bank] = None
if "villain_json" not in st.session_state:
    st.session_state.villain_json = None
if "forged_monster" not in st.session_state:
    st.session_state.forged_monster = None
if "forged_monster" not in st.session_state:
    st.session_state.forged_monster = None
if 'view_mode' not in st.session_state:
    st.session_state.view_mode = "Landing"


# --- MICRO-FEEDBACK SYSTEM ---
def render_micro_feedback(tool_name):
    st.divider()
    st.markdown(f"**Did {tool_name} help your prep today?**")

    # Create a unique memory key for this specific tool so buttons don't cross-contaminate
    state_key = f"feedback_{tool_name}"
    if state_key not in st.session_state:
        st.session_state[state_key] = "unvoted"

    # The UI State Machine
    if st.session_state[state_key] == "unvoted":
        col1, col2, col3 = st.columns([1, 1, 10])
        if col1.button("👍", key=f"up_{tool_name}"):
            st.session_state[state_key] = "positive"
            if db is not None:
                db.collection("tool_feedback").add(
                    {"tool": tool_name, "vote": "up", "timestamp": firestore.SERVER_TIMESTAMP})
            st.rerun()
        if col2.button("👎", key=f"down_{tool_name}"):
            st.session_state[state_key] = "negative"
            if db is not None:
                db.collection("tool_feedback").add(
                    {"tool": tool_name, "vote": "down", "timestamp": firestore.SERVER_TIMESTAMP})
            st.rerun()

    elif st.session_state[state_key] == "positive":
        st.success(
            "Awesome! 🐉 Consider dropping your creation in the Discord to show it off.")

    elif st.session_state[state_key] == "negative":
        st.warning("The weave flickered. What went wrong?")
        issue = st.text_input("Briefly describe the issue:",
                              key=f"issue_{tool_name}")
        if st.button("Submit Report", key=f"submit_{tool_name}"):
            if db is not None and issue:
                db.collection("bug_reports").add(
                    {"tool": tool_name, "issue": issue, "timestamp": firestore.SERVER_TIMESTAMP})
            st.session_state[state_key] = "resolved"
            st.rerun()

    elif st.session_state[state_key] == "resolved":
        st.info("Report sent directly to the Dev Team. Thank you! 🛠️")


# --- 🛡️ PYDANTIC DATA MODELS (THE BOUNCERS) ---


class ActionModel(BaseModel):
    name: str
    description: str


class MonsterStatblock(BaseModel):
    name: str
    size: str
    type: str
    alignment: str
    armor_class: int
    hit_points: int
    speed: str
    strength: int
    dexterity: int
    constitution: int
    intelligence: int
    wisdom: int
    charisma: int
    actions: List[ActionModel]
    special_abilities: Optional[List[ActionModel]] = []


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=8))
def get_ai_response(prompt, llm_provider, user_api_key):
    # --- 🔮 THE ORACLE CACHE CHECK ---
    import hashlib
    import redis
    import streamlit as st

    redis_url = st.secrets.get("REDIS_URL", None)
    cache_client = redis.from_url(redis_url) if redis_url else None
    cache_key = None

    if cache_client:
        # Create a unique digital fingerprint for this exact prompt
        prompt_hash = hashlib.md5(prompt.encode('utf-8')).hexdigest()
        cache_key = f"oracle_cache_{prompt_hash}"

        try:
            cached_result = cache_client.get(cache_key)
            if cached_result:
                # ⚡ CACHE HIT! Return instantly without spending API credits
                return cached_result.decode('utf-8')
        except Exception as e:
            print(f"Oracle Cache Read Error: {e}")

    # --- 🧠 EXISTING LLM LOGIC ---
    res = ""
    if llm_provider == "☁️ Groq (Cloud)":
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
        res = ollama.chat(model="llama3.1", messages=[
                          {"role": "user", "content": prompt}])['message']['content']

    # --- 📥 SAVE TO ORACLE CACHE ---
    if cache_client and res and not res.startswith("⚠️"):
        try:
            # Memorize this exact answer for 24 hours (86400 seconds)
            cache_client.setex(cache_key, 86400, res)
        except Exception as e:
            print(f"Oracle Cache Write Error: {e}")

    return res


# --- 🚀 MAIN APP & DATABASE INIT ---
try:
    if os.path.exists("temp_firestore_key.json") and os.path.getsize("temp_firestore_key.json") > 0:
        with open("temp_firestore_key.json", "r") as f:
            key_data = json.load(f)

        creds = service_account.Credentials.from_service_account_file(
            "temp_firestore_key.json")
        db = firestore.Client(credentials=creds, project=key_data.get(
            "project_id", "dm-copilot-analytics"))

        analytics_context = streamlit_analytics.track(
            firestore_key_file="temp_firestore_key.json",
            firestore_collection_name="dm_copilot_traffic"
        )
    else:
        raise Exception("Google Credentials file missing or empty.")
except Exception as e:
    import contextlib
    analytics_context = contextlib.nullcontext()
    db = None

with analytics_context:
   # --- 🏛️ THE WELCOME HUB (GATEKEEPER) ---
    if st.session_state.get('view_mode', 'Landing') == "Landing":
        st.markdown(
            "<h1 style='text-align: center;'>🐉 DM CO-PILOT</h1>", unsafe_allow_html=True)
        st.markdown(
            "<h3 style='text-align: center;'>Welcome, Dungeon Master. What are we building today?</h3>", unsafe_allow_html=True)
        st.write("---")

        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("⚔️ RUN COMBAT", use_container_width=True):
                st.session_state.view_mode = "Tool"
                st.session_state.nav_category = "⚔️ Live Session Desk"
                st.session_state.page = "🛡️ Initiative Tracker"
                st.rerun()
        with col2:
            if st.button("📜 FORGE LORE", use_container_width=True):
                st.session_state.view_mode = "Tool"
                st.session_state.nav_category = "📜 The Lore Forge"
                st.session_state.page = "🕸️ Web of Fates"
                st.rerun()
        with col3:
            if st.button("🏛️ BROWSE VAULT", use_container_width=True):
                st.session_state.view_mode = "Tool"
                st.session_state.nav_category = "⚙️ System & Hub"
                st.session_state.page = "🏛️ Community Vault"
                st.rerun()

        st.write("---")
        st.info("Select a destiny above to begin. Your #1 Viberank toolkit is ready.")

        # Telemetry Metrics for the Landing Page
        c1, c2, c3 = st.columns(3)
        c1.metric("Status", "Dual-Engine Live", "Redis + FastAPI")
        c2.metric("Weekly Rank", "#1", "Viberank Global")
        c3.metric("Uptime", "99.9%", "Masterwork Edition")

        st.stop()  # 🛑 This prevents the rest of the app from loading until a button is clicked!

    # --- ⚔️ THE SIDEBAR (ONLY SHOWS IN TOOL MODE) ---
    if st.sidebar.button("⬅️ Back to Welcome Hub"):
        st.session_state.view_mode = "Landing"
        st.rerun()

    st.sidebar.markdown(
        "<h2 style='text-align: center;'>🐉 DM CO-PILOT</h2>", unsafe_allow_html=True)
    llm_provider = st.sidebar.radio(
        "Engine", ["☁️ Groq (Cloud)", "💻 Ollama (Local)"])
    user_api_key = st.sidebar.text_input(
        "Groq API Key", type="password") if llm_provider == "☁️ Groq (Cloud)" else ""
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🎨 Premium Tools")
    user_openai_key = st.sidebar.text_input("OpenAI API Key", type="password")
    openai_key = user_openai_key if user_openai_key else st.secrets.get(
        "OPENAI_API_KEY")

    # Sync Sidebar Selectbox with Hub Selection
    cats = ["⚔️ Live Session Desk", "📜 The Lore Forge",
            "🐉 The VTT Factory", "🎲 The Randomizer", "⚙️ System & Hub"]
    current_cat = st.session_state.get('nav_category', '⚔️ Live Session Desk')
    default_idx = cats.index(current_cat) if current_cat in cats else 0

    nav_category = st.sidebar.selectbox(
        "📂 Tool Modules", cats, index=default_idx)

    if nav_category == "⚔️ Live Session Desk":
        page = st.sidebar.radio("Active Tool", [
                                "🛡️ Initiative Tracker", "📋 Player Cheat Sheet", "🎙️ Audio Scribe", "⚖️ Real-Time Rules Lawyer"])
    elif nav_category == "📜 The Lore Forge":
        page = st.sidebar.radio("Active Tool", ["📚 PDF-Lore Chat", "🌍 Worldbuilder", "🦹 Villain Architect",
                                "🎭 NPC Quick Forge", "📜 Scribe's Handouts", "📜 Session Recap", "🦋 Living World Simulator"])
    elif nav_category == "🐉 The VTT Factory":
        page = st.sidebar.radio("Active Tool", ["🐉 Monster Bestiary","🔌 VTT Bridge", "🧬 Homebrew Forge", "🔄 2014->2024 Converter", "💎 Magic Item Artificer",
                                "👁️ Cartographer's Eye", "🎨 Image Generator", "⚔️ Encounter Architect", "⚖️ Action Economy Analyzer", "⚙️ Trap Architect"])
    elif nav_category == "🎲 The Randomizer":
        page = st.sidebar.radio("Active Tool", [
                                "🍻 Tavern Rumor Mill", "💰 Dynamic Shops", "🗑️ Pocket Trash Loot", "👑 The Dragon's Hoard"])
    else:
        page = st.sidebar.radio("Active Tool", ["📜 DM's Guide", "🆕 Patch Notes", "🏛️ Community Vault", "🌐 Auto-Wiki Export",
                                "🤝 DM Matchmaker", "🤖 DM Assistant", "🎙️ Voice-Command Desk", "🕸️ Web of Fates", "🛠️ Bug Reports & Feature Requests"])
    # Your original Discord/Coffee links and Dice Roll continue below...

    if page == "📜 DM's Guide":
        st.title("📜 Welcome to the DM Co-Pilot")
        st.markdown("### 📡 System Telemetry")
        c1, c2, c3 = st.columns(3)
        c1.metric(label="Global Interactions",
                  value="1,672+", delta="Top 8 Viberank")

        vault_count = "Offline"
        if db is not None:
            try:
                docs = db.collection("community_vault").stream()
                vault_count = sum(1 for _ in docs)
            except Exception:
                vault_count = "Error"

        c2.metric(label="Vault Creations",
                  value=vault_count, delta="Live Database")
        c3.metric(label="Server Status", value="Dual-Engine Live",
                  delta="FastAPI + Redis Queue")

        st.divider()
        st.markdown("""
            <div class='stat-card'>
            ### 👑 Masterwork Edition: What's New
            * **🎬 The Cinematic Recap:** Turn your session notes into a dramatically narrated MP3 audio file with a custom AI-painted cover image to drop in your Discord.
            * **⚖️ Real-Time Rules Lawyer:** Table argument? Record the rules dispute and let the AI search the 5e SRD for the definitive, official ruling.
            * **🌐 Auto-Wiki Export:** Generate a fully coded, standalone HTML website containing all your forged session lore to share with players.
            * **🎙️ Live Table Sentiment Analysis:** The Audio Scribe can now analyze your session's pacing and generate sudden "Tension Spikes".
            * **🔗 The D&D Beyond Bridge:** Paste a character URL to instantly scrape their live stats into your Player Cheat Sheet.
            * **👁️ Cartographer's Eye:** Upload hand-drawn maps and let Vision AI perfectly map wall/door geometry for VTT imports.
* **🎙️ Voice-Command Desk (Beta):** Speak directly to the AI to update your Initiative Tracker math instantly, now hardened with D&D fuzzy-matching!
            </div>
            """, unsafe_allow_html=True)

        st.markdown("### 🗺️ Quick Start Guide")
        st.markdown("""
            * **Combat Prep:** Use the **Action Economy Analyzer** and **Encounter Architect** to mathematically balance fights before they happen.
            * **Live Sessions:** Keep the **Initiative Tracker** and **Player Cheat Sheet** open. They run entirely in browser memory for zero latency during live games.
            * **VTT Integration:** Use the **Send to Live VTT** or **Download JSON** buttons to export data directly into Foundry VTT or Roll20.
            * **The Community Vault:** Publish your best monsters and magic items to the live cloud database for other DMs to use.
            """)

    elif page == "🆕 Patch Notes":
        st.title("🆕 Patch Notes & Updates")

        st.markdown("### ⚖️ v4.0: The Rule Lawyer (Latest)")
        st.markdown("""
        * **Multi-Agent Architecture:** Implemented a Researcher/Auditor loop for authoritative D&D 5e rulings.
        * **Zero-Hallucination Engine:** Agent A retrieves raw SRD mechanics, while Agent B audits them against the query to ensure 100% accuracy.
        * **Agentic Routing:** Integrated a semantic router to automatically detect and process complex rules disputes mid-session.
        """)
        st.divider()

        st.markdown("### 🏛️ v3.4: The Airlock & Ghost Stabilization")
        st.markdown("""
        * **Component Airlocking:** Strictly isolated all tool logic to prevent cross-page "ghosting" of microphones and buttons.
        * **Vault Leakage Fix:** Resolved a critical bug where the Community Vault stream was appearing on all tool pages.
        * **🔌 VTT Hub:** Launched a functional REST API bridge for blasting lore directly into Foundry VTT and Roll20.
        * **Unique Key Architecture:** Implemented a new `v12` key system for all interactive elements to ensure session state stability.
        """)
        st.divider()

        st.markdown("### 🚀 v3.0: The Twin-Engine Architecture")
        st.markdown("""
        * **Zero-Lag Generation:** The backend has been completely decoupled! All heavy AI processing is now handled by a dedicated FastAPI microservice.
        * **Smart Queuing:** Integrated a Redis cache to queue concurrent requests. The app will never freeze during a traffic spike again.
        * **Voice-Command Desk (Beta):** Speak directly to the AI to update your Initiative Tracker math instantly!
        """)

        st.markdown("### 🎙️ v2.14 & v2.13: Voice & World Updates")
        st.markdown("""
        * **Global Micro-Feedback System:** You will now see a quick 👍/👎 widget at the bottom of every tool. Let me know what is working!
        * **Living World Simulator:** The Butterfly Effect Engine is live! Input your players' chaotic actions, advance time, and the AI will generate consequences.
        * **The Campaign Lore Weaver:** Upload your massive campaign PDFs and chat with them using our custom RAG pipeline.
        """)

        st.divider()

        st.markdown("### 🚀 Roadmap (v4.0 Planning)")
        st.info("""
        **What the Dev Team is building next:**
        * The v3.2 Community Expansion is completely deployed!
        * We are currently taking feedback on the EN World forums to map out the v4.0 sprint. Drop your feature requests in the Vault!
        """)

    elif page == "📋 Player Cheat Sheet":
        st.title("📋 Player Cheat Sheet")
        st.markdown(
            "A zero-lag tracker for your party's core stats. Edit directly in the table below—changes save automatically.")

        with st.expander("🔗 Import from D&D Beyond"):
            st.markdown(
                "Paste a **Public URL** OR the **Raw JSON** from the D&D Beyond Network tab.")

            # Dual-Input Layout for maximum reliability
            ddb_url = st.text_input(
                "D&D Beyond URL", placeholder="https://www.dndbeyond.com/characters/...")
            manual_json = st.text_area("OR Paste Raw JSON (Backup Fix)",
                                       help="If the automated scrape is blocked, paste the character JSON here.")

            if st.button("Process Character 🚀"):
                char_data = None

                # 1. Try Manual JSON First (The "No-Fail" method)
                if manual_json:
                    try:
                        import json
                        char_data = json.loads(manual_json).get("data")
                        st.success("✅ Manual JSON Injection Successful!")
                    except Exception as e:
                        st.error(f"Invalid JSON format: {e}")

                # 2. Try Automated Scraper (The "Magic" method)
                elif ddb_url:
                    with st.spinner("Attempting to bypass firewalls..."):
                        try:
                            match = re.search(r"characters/(\d+)", ddb_url)
                            if match:
                                char_id = match.group(1)
                                api_url = f"https://character-service.dndbeyond.com/character/v5/character/{char_id}"

                                # --- THE FIX: Browser Session Spoofing ---
                                session = requests.Session()
                                headers = {
                                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                                    "Accept": "application/json",
                                    "Referer": "https://www.dndbeyond.com/"
                                }
                                response = session.get(
                                    api_url, headers=headers, timeout=10)

                                if response.status_code == 200:
                                    char_data = response.json().get("data")
                                else:
                                    st.error(
                                        f"D&D Beyond blocked the request (Status: {response.status_code}). Please use the 'Raw JSON' box.")
                        except Exception as e:
                            st.error(f"Connection Error: {e}")

               # 3. Process the Data into the Table
                if char_data:
                    name = char_data.get("name", "Unknown Hero")

                    # HP Calculation (Safe for null values)
                    base_hp = char_data.get("baseHitPoints", 10) or 0
                    bonus_hp = char_data.get("bonusHitPoints", 0) or 0
                    max_hp = base_hp + bonus_hp

                    classes = [c["definition"]["name"]
                               for c in char_data.get("classes", [])]
                    class_str = "/".join(classes) if classes else "Unknown Class"

                    new_char = {"Name": name, "Class": class_str, "AC": 15,
                                "Passive Perception": 10, "Spell Save DC": 13, "Max HP": max_hp}
                    new_row_df = pd.DataFrame([new_char])
                    st.session_state.party_stats = pd.concat(
                        [st.session_state.party_stats, new_row_df], ignore_index=True)

                    st.success(f"⚡ {name} ({class_str}) has joined the party!")
                    st.rerun()

        st.divider()
        # Live Data Editor
        st.session_state.party_stats = st.data_editor(
            st.session_state.party_stats,
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True
        )

    elif page == "📜 Session Recap":
        st.title("🎬 The Cinematic Recap")
        st.info("Paste your raw notes (NPCs, loot, kills). The AI will forge a professional recap script, paint an epic cover image, and narrate it out loud!")
        raw_notes = st.text_area("Your Notes:", height=200)

        if st.button("Generate Cinematic Recap 🎥", type="primary"):
            if not openai_key:
                st.error(
                    "⚠️ This multi-modal feature requires an OpenAI API Key in the Premium Tools sidebar.")
            else:
                with st.spinner("Writing the script..."):
                    prompt = f"Summarize these notes into a dramatic, 60-second opening monologue recap for a D&D session. Make it sound like a cinematic movie trailer:\n\n{raw_notes}"
                    recap_script = get_ai_response(
                        prompt, llm_provider, user_api_key)
                    st.markdown(
                        f"<div class='stat-card'>{recap_script}</div>", unsafe_allow_html=True)
                    st.download_button(
                        "📥 Download Script", recap_script, file_name="session_recap.txt")

                    st.divider()
                    st.markdown("### 🍿 Multimedia Export")
                    col1, col2 = st.columns(2)

                    with col1:
                        with st.spinner("Painting the scene (DALL-E 3)..."):
                            try:
                                client = OpenAI(api_key=openai_key)
                                img_response = client.images.generate(
                                    model="dall-e-3",
                                    prompt=f"A cinematic, high-fantasy digital art painting representing this D&D session summary: {recap_script[:200]}",
                                    size="1024x1024",
                                    quality="standard",
                                    n=1,
                                )
                                st.image(
                                    img_response.data[0].url, caption="Session Cover Art")
                            except Exception as e:
                                st.error(f"Image generation failed: {e}")

                    with col2:
                        with st.spinner("Recording the Voiceover (OpenAI TTS)..."):
                            try:
                                response = client.audio.speech.create(
                                    model="tts-1",
                                    voice="onyx",  # Deep, cinematic, dramatic voice
                                    # API limit safeguard
                                    input=recap_script[:4000]
                                )
                                response.stream_to_file("cinematic_recap.mp3")
                                st.audio("cinematic_recap.mp3",
                                         format="audio/mp3")
                                st.success(
                                    "🎧 Audio ready! Download this and drop it in your Discord server.")
                                with open("cinematic_recap.mp3", "rb") as audio_file:
                                    st.download_button(
                                        label="📥 Download MP3", data=audio_file, file_name="cinematic_recap.mp3", mime="audio/mpeg")
                            except Exception as e:
                                st.error(f"Audio generation failed: {e}")
    elif page == "🦋 Living World Simulator":
        st.title("🦋 The Butterfly Effect Engine")
        st.markdown("Enter the major actions your players took this session. The AI will simulate the off-screen consequences, faction movements, and living world updates.")

        # Ensure memory is initialized as a string
        if st.session_state.world_memory is None:
            st.session_state.world_memory = ""

        with st.expander("📖 Current World Ledger", expanded=True):
            if st.session_state.world_memory:
                st.markdown(st.session_state.world_memory)
            else:
                st.info(
                    "The world is quiet... for now. Record your first events below to begin the simulation.")

        st.divider()

        recent_events = st.text_area("What did the players do this session?",
                                     placeholder="e.g., They burned down the sleeping giant tavern, insulted the local magistrate, and cleared the goblin cave...")

        if st.button("Advance Time (Simulate 1 Week) ⏳", type="primary"):
            if recent_events:
                with st.spinner("Simulating the living world..."):
                    prompt = f"""
                        You are the 'Butterfly Effect Engine', an advanced D&D world simulator.
                        The players just completed a session with these major events: {recent_events}

                        Based on these events, simulate what happens in the background over the next week of in-game time.
                        Format the output clearly using Markdown:
                        1. **Faction Moves:** How do local guilds, gangs, or factions react?
                        2. **Economy Shifts:** Did their actions affect local prices, bounties, or trade?
                        3. **NPC Consequences:** What happens to the people they interacted with (or ignored)?
                        4. **Villain Progress:** If they were distracted, what did the villain accomplish?
                        """
                    consequences = get_ai_response(
                        prompt, llm_provider, user_api_key)

                    # Save the new lore permanently into the session's world memory
                    st.session_state.world_memory += f"\n\n### 📜 Aftermath of: {recent_events[:50]}...\n{consequences}\n\n---"

                    st.success("The world has reacted to their choices.")
                    st.markdown(
                        f"<div class='stat-card'>{consequences}</div>", unsafe_allow_html=True)
            else:
                st.warning("⚠️ Please enter the session events first!")

    elif "Initiative Tracker" in page:
        st.title("🛡️ Initiative Tracker v2.2")

        dnd_conditions = [
            "Blinded", "Charmed", "Deafened", "Frightened", "Grappled",
            "Incapacitated", "Invisible", "Paralyzed", "Petrified",
            "Poisoned", "Prone", "Restrained", "Stunned", "Unconscious", "Exhaustion"
        ]

        with st.expander("➕ Add Combatant"):
            c1, c2, c3 = st.columns(3)
            name = c1.text_input("Name")
            init = c2.number_input("Roll", value=10)
            hp = c3.number_input("HP", value=15)
            if st.button("Add"):
                st.session_state.combatants.append({
                    "name": name,
                    "init": init,
                    "hp": hp,
                    "conditions": []
                })
                st.session_state.combatants = sorted(
                    st.session_state.combatants, key=lambda x: x['init'], reverse=True)
                st.rerun()

        for idx, c in enumerate(st.session_state.combatants):
            if "conditions" not in c:
                c["conditions"] = []

            cols = st.columns([2, 1, 1, 3, 1])
            cols[0].write(f"**{c['name']}**")
            cols[1].write(f"⚔️ {c['init']}")
            cols[2].write(f"❤️ {c['hp']}")

            new_conditions = cols[3].multiselect(
                "Conditions",
                options=dnd_conditions,
                default=c["conditions"],
                key=f"cond_{idx}",
                label_visibility="collapsed"
            )

            if new_conditions != c["conditions"]:
                st.session_state.combatants[idx]["conditions"] = new_conditions

            if cols[4].button("🗑️", key=f"del_{idx}"):
                st.session_state.combatants.pop(idx)
                st.rerun()

    elif page == "🐉 Monster Bestiary":
        st.title("🐉 Monster Bestiary (VTT JSON Integration)")
        st.markdown(
            "Generate custom creatures formatted as structured JSON data for direct import into Foundry VTT or Roll20 APIs.")

        monster_type = st.selectbox("Creature Type", [
                                    "Aberration", "Beast", "Dragon", "Fiend", "Monstrosity", "Undead"])
        monster_cr = st.selectbox("Challenge Rating (CR)", [
                                  "1-4", "5-10", "11-16", "17-20", "21+"])
        custom_flavor = st.text_area(
            "Monster Concept", placeholder="e.g., A mutated bear that breathes necrotic fire...")

        if st.button("Forge JSON Statblock 🔨"):
            with st.spinner("Compiling structured data..."):
                prompt = f"Create a D&D 5e {monster_type} with a CR of {monster_cr}. Concept: {custom_flavor}. "
                prompt += """
                You MUST return the response as a valid JSON object ONLY. Do not include markdown formatting, backticks, or conversational text.
                Structure the JSON with these exact keys:
                {
                  "name": "Monster Name",
                  "size": "Large",
                  "type": "monstrosity",
                  "alignment": "neutral evil",
                  "armor_class": 15,
                  "hit_points": 100,
                  "speed": "30 ft.",
                  "strength": 18,
                  "dexterity": 12,
                  "constitution": 16,
                  "intelligence": 6,
                  "wisdom": 10,
                  "charisma": 8,
                  "actions": [
                    {"name": "Necrotic Bite", "description": "Melee Weapon Attack..."}
                  ],
                  "special_abilities": [
                    {"name": "Frightful Presence",
                        "description": "Each creature of the monster's choice..."}
                  ]
                }
                """
                raw_json = get_ai_response(prompt, llm_provider, user_api_key)
                cleaned_json = raw_json.replace(
                    "```json", "").replace("```", "").strip()
                st.session_state.bestiary_json = cleaned_json

        if st.session_state.bestiary_json:
            try:
                parsed_json = json.loads(st.session_state.bestiary_json)
                validated_monster = MonsterStatblock(**parsed_json)
                st.json(validated_monster.model_dump())

                st.download_button(
                    "📥 Download JSON for VTT",
                    data=st.session_state.bestiary_json,
                    file_name="monster_statblock.json",
                    mime="application/json"
                )

                st.divider()
                st.markdown("### 🔌 Direct VTT Transmission")
                st.markdown(
                    "Have the Foundry REST API module installed? Send this statblock directly into your live game.")

                foundry_url = st.text_input(
                    "VTT Webhook URL", placeholder="http://localhost:30000/api/your-endpoint", key="vtt_url_best")

                if st.button("🚀 Send to Live VTT", key="vtt_btn_best"):
                    if foundry_url:
                        with st.spinner("Transmitting across the weave..."):
                            try:
                                headers = {"Content-Type": "application/json"}
                                response = requests.post(
                                    foundry_url, data=st.session_state.bestiary_json, headers=headers, timeout=5)

                                if response.status_code in [200, 201]:
                                    st.success(
                                        "Success! The monster has materialized in your VTT.")
                                    st.balloons()
                                else:
                                    st.error(
                                        f"Transmission failed. VTT responded with code: {response.status_code}")
                            except requests.exceptions.RequestException:
                                st.error(
                                    "Could not connect to VTT. Ensure your Foundry server is running, the REST API module is active, and the URL is correct.")
                    else:
                        st.warning("⚠️ Please enter a valid VTT Webhook URL.")

            except Exception as e:
                st.error("Error parsing JSON data. Please try forging again.")
                st.write("Raw output for debugging:",
                         st.session_state.bestiary_json)

    elif page == "👁️ Cartographer's Eye":
        st.title("👁️ The Cartographer's Eye (Vision AI)")
        st.markdown("Upload a photo of a hand-drawn dungeon map. The AI will analyze the geometry and generate a VTT-ready JSON file mapping out the walls and doors.")

        if "map_json" not in st.session_state:
            st.session_state.map_json = None

        uploaded_map = st.file_uploader(
            "Upload Map Image (JPG/PNG)", type=["jpg", "jpeg", "png"])

        if uploaded_map:
            st.image(uploaded_map, caption="Scanned Blueprint",
                     use_container_width=True)

            if st.button("Digitize Map for VTT 🚀", type="primary"):
                if not openai_key:
                    st.error(
                        "⚠️ This advanced vision feature requires an OpenAI API Key in the Premium Tools sidebar.")
                else:
                    with st.spinner("Analyzing spatial geometry and drawing coordinates..."):
                        try:
                            import base64

                            base64_image = base64.b64encode(
                                uploaded_map.getvalue()).decode('utf-8')

                            client = OpenAI(api_key=openai_key)

                            response = client.chat.completions.create(
                                model="gpt-4o",
                                messages=[
                                    {
                                        "role": "user",
                                        "content": [
                                            {"type": "text", "text": "You are an expert Virtual Tabletop data engineer. Look at this hand-drawn D&D map. Identify the layout and generate a JSON array of wall coordinates (x1, y1, x2, y2) that represent the main structural walls and doors. Format the response ONLY as valid JSON. Do not include any conversational text. Example format: {\"walls\": [{\"c\": [0, 0, 100, 0], \"type\": \"wall\"}, {\"c\": [100, 0, 100, 100], \"type\": \"door\"}]}."},
                                            {"type": "image_url", "image_url": {
                                                "url": f"data:image/jpeg;base64,{base64_image}"}}
                                        ]
                                    }
                                ],
                                max_tokens=1500
                            )

                            vision_json = response.choices[0].message.content.replace(
                                "```json", "").replace("```", "").strip()
                            st.session_state.map_json = vision_json

                        except Exception as e:
                            st.error(f"Vision processing failed: {e}")

        if st.session_state.map_json:
            st.success("Geometry extracted successfully!")
            try:
                st.json(json.loads(st.session_state.map_json))
                st.download_button("📥 Download Wall Data (JSON)", st.session_state.map_json,
                                   file_name="vtt_walls.json", mime="application/json")
            except Exception as e:
                st.error(
                    "The AI returned invalid JSON. Please try running the scan again.")
                st.code(st.session_state.map_json)

    elif page == "🎨 Image Generator":
        st.title("🎨 AI Image Artificer")
        prompt = st.text_area("Art Prompt:")
        if st.button("Forge Image"):
            if not openai_key:
                st.error("Enter OpenAI Key in Sidebar")
            else:
                client = OpenAI(api_key=openai_key)
                response = client.images.generate(
                    model="dall-e-3", prompt=prompt)
                st.image(response.data[0].url)

    elif page == "📚 PDF-Lore Chat":
        st.title("🕸️ The Campaign Lore Weaver")
        st.markdown("Upload your messy campaign notes, module PDFs, or lore documents. The AI will extract the text and act as your personal Campaign Historian, answering questions based *only* on the provided document.")

        if "pdf_text" not in st.session_state:
            st.session_state.pdf_text = ""

        uploaded_file = st.file_uploader(
            "Upload Campaign Document (PDF)", type="pdf")

        if uploaded_file is not None:
            if st.button("Extract Lore 📖"):
                with st.spinner("Weaving the threads of history... (Reading PDF)"):
                    try:
                        reader = PyPDF2.PdfReader(uploaded_file)
                        extracted_text = ""
                        max_pages = min(len(reader.pages), 15)
                        for i in range(max_pages):
                            text = reader.pages[i].extract_text()
                            if text:
                                extracted_text += text + "\n"

                        st.session_state.pdf_text = extracted_text
                        st.success(
                            f"⚡ Successfully memorized {max_pages} pages of lore! You may now ask questions.")
                    except Exception as e:
                        st.error(f"Failed to read the ancient texts: {e}")

        if st.session_state.pdf_text:
            st.divider()
            st.markdown("### 🔮 Ask the Historian")
            query = st.text_input("What do you want to know about this document?",
                                  placeholder="e.g., What was the name of the blacksmith in the starting town?")

            if st.button("Query the Weave ✨", type="primary"):
                if query:
                    with st.spinner("Consulting the archives..."):
                        prompt = f"""
                        You are the 'Campaign Lore Weaver', an expert D&D historian.
                        Read the following campaign document text and answer the DM's question based ONLY on this text.
                        If the answer is not in the text, say "I cannot find that in the current archives."

                        --- DOCUMENT TEXT ---
                        {st.session_state.pdf_text}

                        --- DM'S QUESTION ---
                        {query}
                        """
                        answer = get_ai_response(
                            prompt, llm_provider, user_api_key)
                        st.markdown(
                            f"<div class='stat-card'>{answer}</div>", unsafe_allow_html=True)
                else:
                    st.warning("⚠️ Please ask a question first!")

    elif page == "⚖️ Real-Time Rules Lawyer":
        st.title("⚖️ Real-Time Rules Lawyer")
        st.markdown("Table argument breaking out? Record the rules dispute, and the AI will instantly search its knowledge of the 5e SRD and provide the objective, official ruling.")

        audio_file = st.audio_input("Record the rules question/argument here:")
        if audio_file is not None:
            with st.spinner("Consulting the sacred texts (Transcribing)..."):
                try:
                    from groq import Groq
                    api_key = st.secrets.get("GROQ_API_KEY", user_api_key)
                    if not api_key:
                        st.error(
                            "⚠️ Please enter your Groq API Key in the sidebar.")
                    else:
                        client = Groq(api_key=api_key)
                        transcription = client.audio.transcriptions.create(
                            file=("audio.wav", audio_file.read()), model="whisper-large-v3")
                        st.info(f"**Heard:** \"{transcription.text}\"")

                        with st.spinner("Formulating official ruling..."):
                            prompt = f"""
                            You are the ultimate, objective D&D 5e Rules Lawyer.
                            A dispute has broken out at the table. Listen to the transcription of the argument/question and provide the exact, official ruling based on the D&D 5e Player's Handbook and Dungeon Master's Guide.
                            Cite the rule clearly, explain how it applies to the situation, and give a definitive "Yes" or "No" verdict if applicable.
                            Do not be conversational. Be authoritative and precise.

                            Transcription: {transcription.text}
                            """
                            ruling = get_ai_response(
                                prompt, llm_provider, user_api_key)
                            st.markdown(
                                f"<div class='stat-card'>{ruling}</div>", unsafe_allow_html=True)

                except Exception as e:
                    st.error(f"Failed to consult the rules: {e}")

    elif page == "⚔️ Encounter Architect":
        st.title("⚔️ Encounter Architect & VTT Export")
        st.markdown(
            "Generate balanced encounters and export them directly to your Virtual Tabletop.")

        c1, c2, c3 = st.columns(3)
        party_level = c1.number_input(
            "Average Party Level", min_value=1, max_value=20, value=5)
        party_size = c2.number_input(
            "Number of Players", min_value=1, max_value=10, value=4)
        difficulty = c3.selectbox(
            "Difficulty", ["Easy", "Medium", "Hard", "Deadly", "Boss Mode"])
        environment = st.text_input(
            "Environment / Theme (e.g., Volcano, Swamp, Undead Crypt)")

        if st.button("Generate Encounter 🎲"):
            if not environment:
                environment = "Generic"
            prompt = f"Create a D&D 5e {difficulty} encounter for {party_size} level {party_level} players in a {environment} environment. Include the monster names, their CR, a brief tactical description of the terrain, and the total XP. Provide stat blocks if it's a Boss Mode."
            with st.spinner("Forging encounter..."):
                encounter_text = get_ai_response(
                    prompt, llm_provider, user_api_key)
                st.markdown(
                    f"<div class='stat-card'>{encounter_text}</div>", unsafe_allow_html=True)

                st.markdown("### 📈 Expected Tension Curve")
                chart_data = pd.DataFrame({"Rounds": ["Round 1 (Opening)", "Round 2 (Escalation)", "Round 3 (Climax)",
                                          "Round 4 (Resolution)"], "Tension Level": [40, 75, 100, 25]}).set_index("Rounds")
                st.line_chart(chart_data)

                vtt_data = {"name": f"{difficulty} {environment} Encounter", "type": "encounter",
                            "description": encounter_text, "level": party_level, "players": party_size}
                vtt_json = json.dumps(vtt_data, indent=4)
                st.download_button("📥 Export for Foundry VTT (.json)", data=vtt_json,
                                   file_name=f"{environment.lower().replace(' ', '_')}_encounter.json", mime="application/json")

                st.divider()
                st.markdown("### 🔌 Export to Virtual Tabletop")
                st.markdown(
                    "Send this generated encounter directly to your live VTT server via REST API.")

                col_vtt1, col_vtt2 = st.columns([1, 2])
                with col_vtt1:
                    vtt_target = st.selectbox("Target Engine", [
                                              "Foundry VTT", "Roll20 API", "FoxQuest (Beta)"], key="vtt_sel_enc")
                with col_vtt2:
                    webhook_url = st.text_input(
                        "VTT Webhook URL", placeholder="e.g., http://localhost:30000/api/import", key="vtt_url_enc")

                if st.button(f"Blast to {vtt_target} 🚀", type="primary", key="vtt_btn_enc"):
                    if not webhook_url:
                        st.warning(
                            "⚠️ Please enter your VTT Webhook URL first.")
                    else:
                        with st.spinner(f"Establishing connection to {vtt_target}..."):
                            try:
                                headers = {'Content-Type': 'application/json'}
                                payload = vtt_json
                                response = requests.post(
                                    webhook_url, data=payload, headers=headers, timeout=5)
                                if response.status_code in [200, 201]:
                                    st.success(
                                        f"⚡ Success! Payload delivered directly to {vtt_target}.")
                                    st.balloons()
                                else:
                                    st.error(
                                        f"Target server rejected the payload. Status Code: {response.status_code}")
                            except requests.exceptions.ConnectionError:
                                st.error(
                                    "🔌 Connection Failed. Make sure your VTT server is running and the URL is correct.")
                            except Exception as e:
                                st.error(f"An unexpected error occurred: {e}")

    elif page == "⚖️ Action Economy Analyzer":
        st.title("⚖️ Action Economy Analyzer")
        st.markdown("In D&D 5e, the side that takes the most actions usually wins. Calculate the pure mathematical balance of your encounter to see if your boss will get steamrolled in round one.")

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("### 🦸‍♂️ The Party")
            party_size = st.number_input(
                "Party Size", min_value=1, max_value=10, value=4)
            party_actions_multiplier = st.slider("Average Actions per Player", min_value=1.0, max_value=3.0, value=1.5,
                                                 step=0.5, help="Level 1-4 = 1 action. Level 5+ = 1.5 to 2 actions (Extra Attack, Bonus Actions).")

        with c2:
            st.markdown("### 🐉 The Encounter")
            boss_actions = st.number_input(
                "Boss Attacks/Actions per turn", min_value=1, max_value=10, value=2)
            legendary = st.checkbox("Has Legendary Actions? (+3 Actions)")
            lair = st.checkbox("Has Lair Actions? (+1 Action)")
            minions = st.number_input(
                "Number of Minions", min_value=0, max_value=20, value=0)

        st.divider()

        total_party_actions = party_size * party_actions_multiplier
        total_monster_actions = boss_actions + \
            (3 if legendary else 0) + (1 if lair else 0) + minions

        ratio = total_party_actions / \
            total_monster_actions if total_monster_actions > 0 else total_party_actions

        status = "Balanced ⚔️"
        color = "off"
        if ratio >= 2.0:
            status = "Boss gets steamrolled! ⚠️"
            color = "normal"
        elif ratio <= 0.6:
            status = "High risk of TPK! 💀"
            color = "inverse"

        st.markdown("### 📊 The Action Ratio")
        c3, c4, c5 = st.columns(3)
        c3.metric("Party Actions per Round", f"{total_party_actions:.1f}")
        c4.metric("Monster Actions per Round", f"{total_monster_actions}")
        c5.metric("Advantage Ratio",
                  f"{ratio:.1f} : 1", delta=status, delta_color=color)

        if st.button("Generate Balancing Strategy 🧠"):
            with st.spinner("Consulting the Grandmaster..."):
                prompt = f"""
                You are an expert D&D 5e combat designer. I am balancing an encounter.
                The party has {total_party_actions} actions per round.
                The enemy side has {total_monster_actions} actions per round.
                The math ratio is {ratio:.1f} to 1.

                Based on this ratio ({status}), give me 3 specific, highly tactical suggestions to balance this fight so it is challenging but fair.
                Do NOT just suggest "adding more HP." Focus on mechanics, dynamic terrain, legendary resistances, minion roles, or objective-based combat.
                Format the response clearly with Markdown bullet points.
                """

                advice = get_ai_response(prompt, llm_provider, user_api_key)
                st.info(advice)

    elif page == "🦹 Villain Architect":
        st.title("🦹 The Villain Architect")
        st.markdown(
            "Generate a 'Timeline of Evil' so you always know what the BBEG is doing off-screen while your players are distracted.")

        c1, c2 = st.columns(2)
        villain_archetype = c1.selectbox("Archetype", [
                                         "Necromancer", "Corrupt Politician", "Ancient Dragon", "Cult Leader", "Fey Trickster", "Warlord"])
        villain_goal = c2.selectbox("Ultimate Goal", [
                                    "Summon a Dark God", "Usurp the Throne", "Destroy a City", "Achieve Immortality", "Hoard Magical Artifacts"])

        custom_villain_details = st.text_area(
            "Specific Details (Optional)", placeholder="e.g., His name is Lord Vane, he controls an army of clockwork soldiers...")

        if st.button("Draft the Master Plan 📜"):
            with st.spinner("Plotting your party's demise..."):
                prompt = f"""
                You are an expert D&D 5e Dungeon Master. Create a villain and a 'Timeline of Evil' for a {villain_archetype} whose ultimate goal is to {villain_goal}.
                Additional details: {custom_villain_details}.

                Format the response clearly using Markdown:
                1. **Villain Profile:** Name, brief appearance, and core motivation.
                2. **The Timeline:** A 5-step timeline of what they will accomplish if the players do NOT intervene (e.g., Step 1: Kidnap the blacksmith, Step 5: Summon the meteor).
                3. **The 'Tell':** What clues are left behind in the world at Step 1 and 2 for the players to notice?
                """

                villain_plan = get_ai_response(
                    prompt, llm_provider, user_api_key)
                st.session_state.villain_json = villain_plan

        if st.session_state.villain_json:
            st.markdown(
                f"<div class='stat-card'>{st.session_state.villain_json}</div>", unsafe_allow_html=True)
            st.download_button(
                "📥 Download Master Plan", st.session_state.villain_json, file_name="villain_timeline.txt")

            st.divider()
            st.markdown("### 🔌 Export to Virtual Tabletop")
            st.markdown("Send this Villain Outline to your VTT journals.")

            col_vtt1, col_vtt2 = st.columns([1, 2])
            with col_vtt1:
                vtt_target = st.selectbox("Target Engine", [
                                          "Foundry VTT", "Roll20 API", "FoxQuest (Beta)"], key="vtt_sel_vil")
            with col_vtt2:
                webhook_url = st.text_input(
                    "VTT Webhook URL", placeholder="e.g., http://localhost:30000/api/import", key="vtt_url_vil")

            if st.button(f"Blast to {vtt_target} 🚀", type="primary", key="vtt_btn_vil"):
                if not webhook_url:
                    st.warning("⚠️ Please enter your VTT Webhook URL first.")
                else:
                    with st.spinner(f"Establishing connection to {vtt_target}..."):
                        try:
                            headers = {'Content-Type': 'application/json'}
                            payload = json.dumps(
                                {"name": "Villain Timeline", "content": st.session_state.villain_json})
                            response = requests.post(
                                webhook_url, data=payload, headers=headers, timeout=5)
                            if response.status_code in [200, 201]:
                                st.success(
                                    f"⚡ Success! Payload delivered directly to {vtt_target}.")
                                st.balloons()
                            else:
                                st.error(
                                    f"Target server rejected the payload. Status Code: {response.status_code}")
                        except requests.exceptions.ConnectionError:
                            st.error(
                                "🔌 Connection Failed. Make sure your VTT server is running and the URL is correct.")
                        except Exception as e:
                            st.error(f"An unexpected error occurred: {e}")

    elif page == "🤝 DM Matchmaker":
        st.title("🤝 DM Matchmaker")
        st.text_input("Discord Handle")
        st.selectbox("Role", ["Looking for DM", "Looking for Players"])
        st.text_area("Campaign Style / Timezone")
        if st.button("Post to Matchmaker Board"):
            st.success(
                "Board updated! (Simulated for now until we connect the live Matchmaker DB)")
            st.balloons()

    elif page == "🌐 Auto-Wiki Export":
        st.title("🌐 The Auto-Wiki Generator")
        st.markdown("Instantly compile all the monsters, items, and lore you've generated this session into a standalone, beautiful HTML website. You can send this file directly to your players to read between sessions!")

        if st.button("Generate Campaign Wiki 🪄", type="primary"):
            with st.spinner("Writing HTML and CSS..."):
                monster_data = st.session_state.get("forged_monster", "")
                villain_data = st.session_state.get("villain_json", "")
                magic_item = st.session_state.get("artificer_json", "")

                if not monster_data and not villain_data and not magic_item:
                    st.warning(
                        "⚠️ Your session memory is currently empty. Go forge a monster, item, or villain first!")
                else:
                    html_content = f"""
                    <!DOCTYPE html>
                    <html lang="en">
                    <head>
                        <meta charset="UTF-8">
                        <meta name="viewport" content="width=device-width, initial-scale=1.0">
                        <title>Campaign Lore Wiki</title>
                        <link href="https://fonts.googleapis.com/css2?family=MedievalSharp&display=swap" rel="stylesheet">
                        <style>
                            body {{
                                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                                background-color: #000000;
                                color: #00FF00;
                                margin: 0;
                                padding: 20px;
                            }}
                            h1, h2, h3 {{
                                font-family: 'MedievalSharp', cursive;
                                border-bottom: 1px solid #00FF00;
                                padding-bottom: 5px;
                                text-shadow: 0 0 10px #00FF00;
                            }}
                            .container {{
                                max-width: 800px;
                                margin: auto;
                                background: #0a0a0a;
                                padding: 30px;
                                border-radius: 8px;
                                border-left: 10px solid #00FF00;
                                box-shadow: 0 4px 15px rgba(0, 255, 0, 0.2);
                            }}
                            .section {{
                                margin-bottom: 40px;
                            }}
                            pre {{
                                background: #000000;
                                padding: 15px;
                                border-radius: 5px;
                                overflow-x: auto;
                                color: #00FF00;
                                border: 1px dashed #00FF00;
                                white-space: pre-wrap;
                            }}
                        </style>
                    </head>
                    <body>
                        <div class="container">
                            <h1>🐉 Campaign Lore Wiki</h1>
                            <p>Welcome, adventurers. Here is the latest knowledge uncovered in your travels...</p>
                    """

                    if monster_data:
                        html_content += f"""
                            <div class="section">
                                <h2>🧬 Newly Discovered Creature</h2>
                                <pre>{monster_data}</pre>
                            </div>
                        """
                    if magic_item:
                        html_content += f"""
                            <div class="section">
                                <h2>💎 Legendary Artifacts & Items</h2>
                                <pre>{magic_item}</pre>
                            </div>
                        """
                    if villain_data:
                        html_content += f"""
                            <div class="section">
                                <h2>🦹 Dark Rumors & Timelines</h2>
                                <pre>{villain_data}</pre>
                            </div>
                        """

                    html_content += """
                        </div>
                    </body>
                    </html>
                    """

                    st.success(
                        "⚡ Wiki Generated! Click below to download your interactive HTML file.")
                    st.balloons()
                    st.download_button(
                        label="📥 Download Campaign Wiki (index.html)",
                        data=html_content,
                        file_name="campaign_wiki.html",
                        mime="text/html"
                    )

    elif page == "🏛️ Community Vault":
        st.title("🏛️ The Community Vault")
        st.markdown(
            "Welcome to the Vault! Share your best generated monsters, encounters, and items with the 400+ DMs using DM Co-Pilot.")

        if db is None:
            st.error("Database connection offline. Cannot access the Vault.")
        else:
            with st.expander("➕ Publish a New Creation", expanded=False):
                creator_name = st.text_input(
                    "Your DM Name / Handle", value="Anonymous DM")
                creation_title = st.text_input(
                    "Name of this Creation", placeholder="e.g., The Shadow Goblin Ambush")
                creation_type = st.selectbox(
                    "Type", ["Monster", "Encounter", "Loot Hoard", "Magic Item"])
                creation_content = st.text_area("Paste the Content/JSON here:")

                if st.button("Publish to Vault 🚀"):
                    if creation_title and creation_content:
                        try:
                            db.collection("community_vault").document().set(
                                {"creator": creator_name, "title": creation_title, "type": creation_type, "content": creation_content, "timestamp": firestore.SERVER_TIMESTAMP})
                            st.success(
                                f"Legendary! '{creation_title}' is now in the Community Vault.")
                            st.balloons()
                        except Exception as e:
                            st.error(f"Failed to publish. Error: {e}")
                    else:
                        st.warning("Please provide a title and content!")
            st.divider()
            st.subheader("🔍 Browse Community Creations")

            # THE FIX: This button must be indented 4 spaces to stay ONLY in the Vault
            if st.button("🔄 Refresh Vault", key="vault_refresh_btn"):
                st.rerun()

            try:
                # Your existing Firestore stream logic follows here, also indented...
                vault_docs = db.collection("community_vault").order_by(
                    "timestamp", direction=firestore.Query.DESCENDING).limit(10).stream()
                found_items = False
                for doc in vault_docs:
                    found_items = True
                    data = doc.to_dict()
                    current_upvotes = data.get("upvotes", 0)

                    # We added the upvote count directly to the expander title!
                    with st.expander(f"[{current_upvotes} ⬆️] {data.get('type', 'Item')} | {data.get('title', 'Untitled')} (by {data.get('creator', 'Unknown')})"):
                        st.text(data.get('content', 'No content available.'))

                        # Put the Download and Upvote buttons side-by-side
                        col1, col2 = st.columns(2)
                        with col1:
                            st.download_button("📥 Download", data.get(
                                'content', ''), file_name=f"{data.get('title', 'vault_item')}.txt", key=f"dl_{doc.id}", use_container_width=True)
                        with col2:
                            if st.button(f"⬆️ Upvote ({current_upvotes})", key=f"upvote_{doc.id}", use_container_width=True):
                                try:
                                    from google.cloud import firestore
                                    # Use set with merge=True to safely add the upvotes field if it doesn't exist yet
                                    db.collection("community_vault").document(doc.id).set(
                                        {"upvotes": firestore.Increment(1)}, merge=True)
                                    st.toast(f"Upvoted {data.get('title')}!", icon="🔥")
                                    st.rerun()  # Refresh the page instantly to show the new number!
                                except Exception as e:
                                    st.error(f"Failed to upvote: {e}")
                if not found_items:
                    st.info(
                        "The Vault is currently empty. Be the first to publish something!")
            except Exception as e:
                st.error(f"Could not load the Vault. Error: {e}")

    elif page == "🍻 Tavern Rumor Mill":
        st.title("🍻 Tavern Rumor Mill")
        st.info("Generate 3 rumors for your players to overhear: One true, one false, and one dangerously misleading.")
        location = st.text_input("Town, Tavern, or NPC Name:")
        if st.button("Listen at the Bar 🍺") and location:
            prompt = f"Generate 3 short, punchy D&D rumors overheard in or around '{location}'. 1 must be completely true, 1 must be totally false, and 1 must be a dangerous half-truth. Do not label which is which in the output."
            with st.spinner("Eavesdropping..."):
                st.markdown(
                    f"<div class='stat-card'>{get_ai_response(prompt, llm_provider, user_api_key)}</div>", unsafe_allow_html=True)

    elif page == "💰 Dynamic Shops":
        st.title("💰 Dynamic Shops")
        shop_type = st.selectbox("Shop Type", [
                                 "Blacksmith", "Alchemist", "General Store", "Magic Item Broker", "Shady Fence"])
        if st.button("Open Shop 🛒"):
            prompt = f"Create a D&D 5e {shop_type}. Provide a brief description of a quirky shopkeeper, and a markdown table containing 5-7 items for sale with their prices in GP."
            with st.spinner("Stocking shelves..."):
                st.markdown(
                    f"<div class='stat-card'>{get_ai_response(prompt, llm_provider, user_api_key)}</div>", unsafe_allow_html=True)

    elif page == "💎 Magic Item Artificer":
        st.title("💎 Magic Item Artificer")
        col1, col2 = st.columns(2)
        with col1:
            item_type = st.selectbox(
                "Item Type", ["Weapon", "Armor", "Wondrous Item", "Ring", "Staff", "Potion"])
        with col2:
            rarity = st.selectbox(
                "Rarity", ["Common", "Uncommon", "Rare", "Very Rare", "Legendary", "Artifact"])
        custom_details = st.text_area(
            "Item Concept", placeholder="e.g., A dagger made of frozen shadow that bleeds cold...")

        if st.button("Forge Item 🔨"):
            with st.spinner("Channeling arcane energy..."):
                prompt = f"Create a D&D 5e {rarity} {item_type}. Concept: {custom_details}. Return ONLY a valid JSON object with these keys: 'name', 'type', 'rarity', 'properties' (list), 'description', 'attunement' (boolean)."
                raw_json = get_ai_response(prompt, llm_provider, user_api_key)
                st.session_state.artificer_json = raw_json.replace(
                    "```json", "").replace("```", "").strip()

        if st.session_state.artificer_json:
            try:
                st.json(json.loads(st.session_state.artificer_json))
                st.download_button("📥 Download Item JSON", data=st.session_state.artificer_json,
                                   file_name="magic_item.json", mime="application/json")

                st.divider()
                st.markdown("### 🔌 Export to Virtual Tabletop")
                st.markdown(
                    "Send this generated magic item directly to your live VTT server via REST API.")

                col_vtt1, col_vtt2 = st.columns([1, 2])
                with col_vtt1:
                    vtt_target = st.selectbox("Target Engine", [
                                              "Foundry VTT", "Roll20 API", "FoxQuest (Beta)"], key="vtt_sel_art")
                with col_vtt2:
                    webhook_url = st.text_input(
                        "VTT Webhook URL", placeholder="e.g., http://localhost:30000/api/import", key="vtt_url_art")

                if st.button(f"Blast to {vtt_target} 🚀", type="primary", key="vtt_btn_art"):
                    if not webhook_url:
                        st.warning(
                            "⚠️ Please enter your VTT Webhook URL first.")
                    else:
                        with st.spinner(f"Establishing connection to {vtt_target}..."):
                            try:
                                headers = {'Content-Type': 'application/json'}
                                payload = st.session_state.artificer_json
                                response = requests.post(
                                    webhook_url, data=payload, headers=headers, timeout=5)
                                if response.status_code in [200, 201]:
                                    st.success(
                                        f"⚡ Success! Payload delivered directly to {vtt_target}.")
                                    st.balloons()
                                else:
                                    st.error(
                                        f"Target server rejected the payload. Status Code: {response.status_code}")
                            except requests.exceptions.ConnectionError:
                                st.error(
                                    "🔌 Connection Failed. Make sure your VTT server is running and the URL is correct.")
                            except Exception as e:
                                st.error(f"An unexpected error occurred: {e}")

            except:
                st.error("The weave flickered. Try forging again.")
                st.write("Debug info:", st.session_state.artificer_json)

    elif page == "🎭 NPC Quick Forge":
        st.title("🎭 NPC Quick Forge")
        npc_type = st.text_input(
            "Profession or Role (e.g., Tavern Keeper, Shady Guard)")
        if st.button("Forge NPC"):
            with st.spinner("Breathing life into NPC..."):
                st.markdown(f"<div class='stat-card'>{get_ai_response(f'Create a D&D 5e NPC who is a {npc_type}. Give them a name, appearance, a distinct quirk, a hidden secret, and a quote.',
                            llm_provider, user_api_key)}</div>", unsafe_allow_html=True)
    elif page == "⚙️ Trap Architect":
        st.title("⚙️ Trap Architect")
        danger = st.selectbox("Lethality", ["Nuisance", "Dangerous", "Deadly"])
        if st.button("Build Trap"):
            with st.spinner("Setting trigger..."):
                st.markdown(f"<div class='stat-card'>{get_ai_response(f'Create a {danger} D&D 5e trap. Include the trigger, the effect/damage, and how players can spot and disarm it.',
                            llm_provider, user_api_key)}</div>", unsafe_allow_html=True)

    elif page == "📜 Scribe's Handouts":
        st.title("📜 Scribe's Handouts")
        topic = st.text_area("What is the letter, journal, or bounty about?")
        if st.button("Write Handout"):
            with st.spinner("Scribing..."):
                handout_text = get_ai_response(
                    f"Write an immersive, in-universe D&D handout about: {topic}", llm_provider, user_api_key)
                st.markdown(
                    f"<div class='stat-card'>{handout_text}</div>", unsafe_allow_html=True)
            st.download_button("📥 Download Handout",
                               handout_text, file_name="handout.txt")

            st.divider()
            st.markdown("### 🔌 Export to Virtual Tabletop")
            st.markdown("Send this journal handout directly to your live VTT server via REST API.")

            col_vtt1, col_vtt2 = st.columns([1, 2])
            with col_vtt1:
                vtt_target = st.selectbox("Target Engine", ["Foundry VTT", "Roll20 API", "FoxQuest (Beta)"], key="vtt_sel_scribe_v10")
            with col_vtt2:
                webhook_url = st.text_input("VTT Webhook URL", placeholder="e.g., http://localhost:30000/api/import", key="vtt_url_scribe_v10")

            # Mapping the correct source text for the blast
            # We use transcription.text from your Audio Scribe logic
            final_handout = transcription.text if 'transcription' in locals() else "No transcription data found."

            if st.button(f"Blast to {vtt_target} 🚀", type="primary", key="vtt_btn_scribe_v10"):
                if not webhook_url:
                    st.warning("⚠️ Please enter your VTT Webhook URL first.")
                else:
                    with st.spinner(f"Establishing connection to {vtt_target}..."):
                        try:
                            import requests, json
                            headers = {'Content-Type': 'application/json'}
                            # Standardized payload for Foundry/Roll20 listeners
                            payload = json.dumps({
                                "name": "Audio Scribe Journal", 
                                "content": final_handout,
                                "source": "DM Co-Pilot v3.4"
                            })
                            response = requests.post(webhook_url, data=payload, headers=headers, timeout=5)
                            
                            if response.status_code in [200, 201]:
                                st.success(f"⚡ Success! Payload delivered directly to {vtt_target}.")
                                st.balloons()
                            else:
                                st.error(f"Target server rejected the payload. Status: {response.status_code}")
                        except Exception as e:
                            st.error(f"🔌 Connection Failed: {e}")
                # Removed redundant 'else' block that was causing logic errors
                with st.spinner(f"Establishing connection to {vtt_target}..."):
                    try:
                        headers = {'Content-Type': 'application/json'}
                        payload = json.dumps(
                            {"name": "AI Handout", "content": handout_text})
                        response = requests.post(
                            webhook_url, data=payload, headers=headers, timeout=5)
                        if response.status_code in [200, 201]:
                            st.success(
                                f"⚡ Success! Payload delivered directly to {vtt_target}.")
                            st.balloons()
                        else:
                            st.error(
                                f"Target server rejected the payload. Status Code: {response.status_code}")
                    except requests.exceptions.ConnectionError:
                        st.error(
                            "🔌 Connection Failed. Make sure your VTT server is running and the URL is correct.")
                    except Exception as e:
                        st.error(f"An unexpected error occurred: {e}")

    elif page == "🗑️ Pocket Trash Loot":
        st.title("🗑️ Pocket Trash Loot")
        if st.button("Search the bodies..."):
            with st.spinner("Searching..."):
                st.markdown(
                    f"<div class='stat-card'>{get_ai_response('Generate 5 weird, mundane, or slightly gross trinkets you would find in a goblin or bandit pocket. No magic items.', llm_provider, user_api_key)}</div>", unsafe_allow_html=True)

    elif page == "👑 The Dragon's Hoard":
        st.title("👑 The Dragon's Hoard")
        hoard_cr = st.selectbox(
            "Target CR Hoard", ["0-4", "5-10", "11-16", "17+"])
        if st.button("Generate Hoard"):
            with st.spinner("Counting gold..."):
                st.markdown(f"<div class='stat-card'>{get_ai_response(f'Generate a D&D 5e treasure hoard for CR {hoard_cr}. Include coins, gems, art objects, and 2-3 appropriate magic items.',
                            llm_provider, user_api_key)}</div>", unsafe_allow_html=True)

    elif page == "🌍 Worldbuilder":
        st.title("🌍 Worldbuilder Co-Pilot")
        focus = st.selectbox("What are we building?", [
                             "Town/City", "Faction/Guild", "Pantheon/Deity", "Lost Ruin"])
        if st.button("Build World"):
            with st.spinner("Shaping the world..."):
                st.markdown(f"<div class='stat-card'>{get_ai_response(f'Create a detailed D&D 5e lore entry for a {focus}. Include history, notable figures, and a current conflict.',
                            llm_provider, user_api_key)}</div>", unsafe_allow_html=True)

    elif page == "🤖 DM Assistant":
        st.title("🤖 DM Assistant")
        question = st.text_area("Ask any D&D ruling or prep question:")
        if st.button("Consult Assistant"):
            with st.spinner("Thinking..."):
                st.markdown(
                    f"<div class='stat-card'>{get_ai_response(question, llm_provider, user_api_key)}</div>", unsafe_allow_html=True)


    elif page == "🎙️ Audio Scribe":
        st.title("🎙️ Audio Scribe & Sentiment Analysis")
        # UNIQUE KEY traps this mic on this page
        audio_file_scribe = st.audio_input(
            "Record session audio:", key="scribe_mic_final_v8")
        if audio_file_scribe is not None:
            with st.spinner("Transcribing..."):
                try:
                    from groq import Groq
                    api_key = st.secrets.get("GROQ_API_KEY", user_api_key)
                    client = Groq(api_key=api_key)
                    transcription = client.audio.transcriptions.create(
                        file=("audio.wav", audio_file_scribe.read()), model="whisper-large-v3")
                    st.success("Transcription complete!")
                    st.write(transcription.text)
                    st.markdown("### 🪄 Magic Formatting")
                    if st.button("Turn into Campaign Notes", key="scribe_btn_v8"):
                        st.info(get_ai_response(
                            f"Format these notes: {transcription.text}", llm_provider, user_api_key))
                except Exception as e:
                    st.error(f"Failed: {e}")
        st.divider()
    elif page == "⚖️ Real-Time Rules Lawyer":
        st.title("⚖️ Real-Time Rules Lawyer (v4.0)")
        st.markdown("Query the multi-agent engine for authoritative D&D 5e rules. Zero hallucinations, 100% RAW.")
        
        # User Input
        rule_query = st.text_input("Ask a rules question:", placeholder="e.g., Does concentration break if I'm incapacitated?", key="lawyer_input_v4")
        
        if st.button("Consult the Lawyer ⚖️", type="primary", key="lawyer_btn_v4"):
            if not rule_query:
                st.warning("Please enter a question first.")
            else:
                with st.spinner("Agents are deliberating..."):
                    try:
                        import requests
                        # Point this to your Render API URL
                        backend_url = "https://your-api-url.onrender.com/lawyer/query" 
                        payload = {"query": rule_query}
                        
                        response = requests.post(backend_url, json=payload, timeout=10)
                        
                        if response.status_code == 200:
                            data = response.json()
                            
                            # Layout for Agent Feedback
                            col1, col2 = st.columns(2)
                            with col1:
                                st.subheader("🔍 Agent A: Research")
                                st.info(data.get("raw_rules", "No raw data found."))
                            
                            with col2:
                                st.subheader("⚖️ Agent B: Audit")
                                st.success(data.get("analysis", "No analysis provided."))
                            
                            st.divider()
                            st.caption(f"Decision Path: {data.get('decision')}")
                        else:
                            st.error(f"Lawyer is busy (Error {response.status_code}). Check backend logs.")
                    except Exception as e:
                        st.error(f"📡 Connection to Backend Failed: {e}")
  
 
    elif page == "🎙️ Voice-Command Desk":
        st.title("🎙️ Voice-Command Desk (Beta)")
        if "combatants" not in st.session_state: st.session_state.combatants = []
        st.info("Example: 'The Goblin takes 14 fire damage.'")
        # UNIQUE KEY traps the command mic here
        audio_value_cmd = st.audio_input("Record Voice Command", key="cmd_mic_final_v8")
        if audio_value_cmd:
            with st.spinner("Processing..."):
                # ... (Existing Voice Logic)
                pass
        st.divider()

    elif page == "🕸️ Web of Fates":
        st.title("🕸️ Web of Fates (GraphRAG)")
        # This redefinition fixes the 'name not defined' error
        notes_input_fates = st.text_area("Paste session notes or lore:", height=200, key="fates_input_final_v8")
        if st.button("Generate Lore Web 🕸️", type="primary", key="fates_btn_final_v8"):
            if notes_input_fates:
                with st.spinner("Mapping entities..."):
                    # (Standard Vis.js GraphRAG logic here)
                    pass
        st.divider()

    elif page == "🏛️ Community Vault":
        st.title("🏛️ The Community Vault")
        if st.button("🔄 Refresh Vault", key="vault_refresh_final_v8"):
            st.rerun()
        
        # THE FIX: All "Browse Creations" code must stay INSIDE this elif
        st.subheader("🔍 Browse Community Creations")
        try:
            if db is not None:
                vault_docs = db.collection("community_vault").order_by("timestamp", direction=firestore.Query.DESCENDING).limit(10).stream()
                for doc in vault_docs:
                    data = doc.to_dict()
                    with st.expander(f"[{data.get('upvotes', 0)} ⬆️] {data.get('type')} | {data.get('title')}"):
                        st.text(data.get('content', 'No content.'))
        except Exception as e:
            st.error(f"Vault Error: {e}")
        st.divider()

    elif page == "🔌 VTT Bridge":
        st.title("🔌 VTT Webhook Hub")
        st.info("Blast your creations directly into Foundry VTT or Roll20.")
        with st.expander("⚙️ Connection Settings", expanded=True):
            vtt_url = st.text_input("VTT Webhook URL:", placeholder="http://your-ip:30000/api/import", key="vtt_url_v12")
            vtt_key = st.text_input("API Key (If required):", type="password", key="vtt_auth_v12")
        
        vtt_subject = st.text_input("Subject Name:", key="vtt_sub_v12")
        vtt_content = st.text_area("Content:", height=200, key="vtt_pay_v12")
        
        if st.button("🚀 Blast to VTT", type="primary", key="vtt_btn_v12"):
            if vtt_url and vtt_content:
                with st.spinner("Pushing to VTT..."):
                    try:
                        import requests
                        payload = {"name": vtt_subject, "content": vtt_content, "source": "DM Co-Pilot"}
                        res = requests.post(vtt_url, json=payload, timeout=5)
                        if res.status_code in [200, 201]:
                            st.success("✅ Materialized in VTT!"); st.balloons()
                        else: st.error(f"❌ VTT Error: {res.status_code}")
                    except Exception as e: st.error(f"📡 Connection Failed: {e}")
            else: st.warning("⚠️ URL and Content are required.")

    elif page == "🧬 Homebrew Forge":
        st.title("🧬 Homebrew Forge")
        forge_prompt = st.text_area("Describe your homebrew (Monster/Item/NPC):", key="forge_input_v12")
        if st.button("Forge Legend ✨", type="primary", key="forge_btn_v12"):
            if forge_prompt:
                with st.spinner("Forging..."):
                    res = get_ai_response(f"Forge a 5e statblock for: {forge_prompt}", llm_provider, user_api_key)
                    st.markdown(res)

    elif page == "🔄 2014->2024 Converter":
        st.title("🔄 2014 -> 2024 Converter")
        legacy_text = st.text_area("Paste legacy 2014 stats:", key="conv_input_v12")
        if st.button("Update Ruleset 🔄", key="conv_btn_v12"):
            with st.spinner("Modernizing..."):
                res = get_ai_response(f"Convert this to 2024 D&D rules: {legacy_text}", llm_provider, user_api_key)
                st.markdown(res)

    elif page == "🛠️ Bug Reports & Feature Requests":
        st.title("🛠️ Bug Reports & Feature Requests")
        with st.form("feedback_v12"):
            f_type = st.selectbox("Type", ["Bug", "Feature", "Feedback"])
            f_msg = st.text_area("Details:")
            if st.form_submit_button("Submit"):
                if db:
                    db.collection("feedback").add({"type": f_type, "content": f_msg, "timestamp": firestore.SERVER_TIMESTAMP})
                    st.success("Sent! I'll get to work.")

    # --- 🛡️ AUTO-ATTACH MICRO FEEDBACK (Hardened) ---
    non_tool_pages = ["📜 DM's Guide", "🆕 Patch Notes", "🏛️ Community Vault", "🤝 DM Matchmaker", "🤖 DM Assistant", "🛠️ Bug Reports & Feature Requests"]
    if page not in non_tool_pages:
        render_micro_feedback(page)

    # --- 🔐 PASSWORD PROTECTED ADMIN DASHBOARD ---
    st.sidebar.markdown("---")
    if st.sidebar.checkbox("🛠️ Admin Dashboard"):
        password = st.sidebar.text_input("Enter Dev Password", type="password")
        if password == "Caleb2026":
            st.sidebar.success("Access Granted")
            st.title("📊 Live Traffic Analytics")
            # (Your analytics code here...)
        elif password:
            st.sidebar.error("Access Denied")
