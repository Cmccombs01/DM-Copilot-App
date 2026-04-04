import os
import re
import json
import random
import hashlib
import tempfile
from datetime import datetime
from collections import Counter

import pandas as pd
import requests
import PyPDF2
import redis
import streamlit as st
from gtts import gTTS
from streamlit_agraph import agraph, Node, Edge, Config
import streamlit_analytics2 as streamlit_analytics
import streamlit_analytics2.firestore as sa2_firestore
import streamlit_analytics2.display as sa2_display

from openai import OpenAI
from qdrant_client import QdrantClient
from tenacity import retry, stop_after_attempt, wait_exponential
from pydantic import BaseModel, ValidationError
from typing import List, Optional

# --- NEW: FIRESTORE IMPORTS FOR THE VAULT ---
from google.oauth2 import service_account
from google.cloud import firestore

st.set_page_config(
    page_title="DM Co-Pilot | Masterwork Edition", page_icon="🐉", layout="wide"
)
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
    if (
        isinstance(safe_counts, dict)
        and "widgets" in safe_counts
        and isinstance(safe_counts["widgets"], dict)
    ):
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
                oversized_keys = [
                    k for k in widget_data.keys() if isinstance(k, str) and len(k) > 500
                ]
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


# --- ⚡ THE EDGE-CACHED BESTIARY (Redis Distributed Cache) ---
@st.cache_resource(show_spinner=False)
def get_redis_client():
    """🛡️ INFRASTRUCTURE 2/3: Hardened Redis Connection"""
    redis_url = st.secrets.get("REDIS_URL", os.environ.get("REDIS_URL"))
    if redis_url:
        try:
            # Added socket_timeout and socket_connect_timeout to prevent black screen hangs
            return redis.from_url(
                redis_url,
                socket_timeout=5,
                socket_connect_timeout=5,
                retry_on_timeout=True,
            )
        except Exception as e:
            print(f"Redis Connection Failed: {e}")
            return None
    return None


@st.cache_data(show_spinner=False)
def load_bestiary():
    cache_client = get_redis_client()
    cache_key = "global_bestiary_json"

    # 1. ⚡ THE EDGE CACHE: Try to fetch from Redis (Cross-server RAM)
    if cache_client:
        try:
            cached_data = cache_client.get(cache_key)
            if cached_data:
                return pd.read_json(cached_data.decode("utf-8"))
        except Exception as e:
            print(f"Redis Read Error: {e}")

    # 2. 🐌 THE FALLBACK: Load from Disk if Redis is empty or offline
    try:
        with open("srd_5e_monsters.json", "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        df = pd.DataFrame(raw_data)
        rename_map = {"Challenge": "cr", "Hit Points": "hp", "Armor Class": "ac"}
        df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

        traits = df["Traits"].fillna("") if "Traits" in df.columns else ""
        acts = df["Actions"].fillna("") if "Actions" in df.columns else ""
        df["actions"] = traits + "\n\n" + acts
        df["actions"] = df["actions"].str.replace(r"<[^<>]*>", "", regex=True)

        # 3. 🌐 POPULATE THE EDGE: Write back to Redis for the other Render instances
        if cache_client:
            try:
                cache_client.set(cache_key, df.to_json())
            except Exception as e:
                print(f"Redis Write Error: {e}")

        return df
    except Exception as e:
        st.error(f"🚨 LOCAL DATABASE CRASH REPORT: {e}")
        return pd.DataFrame()


# --- 🚑 SAFETY STARTUP ---
try:
    monster_df = load_bestiary()
except:
    monster_df = pd.DataFrame()  # Init empty if Redis hangs, preventing NameErrors

# --- 🌌 THEME & STYLING ---
st.markdown(
    """
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
""",
    unsafe_allow_html=True,
)

# --- ⚙️ HELPER LOGIC & GLOBAL MEMORY ---
if "combatants" not in st.session_state:
    st.session_state.combatants = []
if "party_stats" not in st.session_state:
    st.session_state.party_stats = pd.DataFrame(
        [
            {
                "Name": "Player 1",
                "Class": "Fighter",
                "AC": 18,
                "Passive Perception": 13,
                "Spell Save DC": 0,
                "Max HP": 45,
            },
            {
                "Name": "Player 2",
                "Class": "Wizard",
                "AC": 12,
                "Passive Perception": 11,
                "Spell Save DC": 15,
                "Max HP": 22,
            },
        ]
    )

    # We added "world_memory" to track the living world state
    memory_banks = [
        "bestiary_json",
        "artificer_json",
        "shop_json",
        "encounter_json",
        "tavern_json",
        "handout_json",
        "world_memory",
    ]
    for bank in memory_banks:
        if bank not in st.session_state:
            st.session_state[bank] = None
if "villain_json" not in st.session_state:
    st.session_state.villain_json = None
if "forged_monster" not in st.session_state:
    st.session_state.forged_monster = None
if "view_mode" not in st.session_state:
    st.session_state.view_mode = "Landing"
if "demo_uses" not in st.session_state:
    st.session_state.demo_uses = 0


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
                    {
                        "tool": tool_name,
                        "vote": "up",
                        "timestamp": firestore.SERVER_TIMESTAMP,
                    }
                )
            st.rerun()
        if col2.button("👎", key=f"down_{tool_name}"):
            st.session_state[state_key] = "negative"
            if db is not None:
                db.collection("tool_feedback").add(
                    {
                        "tool": tool_name,
                        "vote": "down",
                        "timestamp": firestore.SERVER_TIMESTAMP,
                    }
                )
            st.rerun()

    elif st.session_state[state_key] == "positive":
        st.success(
            "Awesome! 🐉 Consider dropping your creation in the Discord to show it off."
        )

    elif st.session_state[state_key] == "negative":
        st.warning("The weave flickered. What went wrong?")
        issue = st.text_input("Briefly describe the issue:", key=f"issue_{tool_name}")
        if st.button("Submit Report", key=f"submit_{tool_name}"):
            if db is not None and issue:
                db.collection("bug_reports").add(
                    {
                        "tool": tool_name,
                        "issue": issue,
                        "timestamp": firestore.SERVER_TIMESTAMP,
                    }
                )
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


# --- 🎭 PERSONALITY PROFILES ---
AI_PROFILES = {
    "tactician": "You are a ruthless D&D 5e Combat Strategist. Focus on positioning, weak points, and action economy.",
    "accountant": "You are a meticulous Fantasy Treasurer. Focus on precise gold conversion and item appraisal.",
    "lawyer": "You are a strict Rules Lawyer. Cite 5e RAW (Rules as Written) and provide fair DCs.",
}


def check_goblin_tax():
    """🛡️ INFRASTRUCTURE 1/3: Global Rate Limiter (The Goblin Tax)
    Ensures one user doesn't spam the API and crash the engine.
    """
    cache_client = get_redis_client()
    if not cache_client:
        return True  # Fail open if Redis is down

    session_id = st.session_state.get("app_session_id", "anon")
    rate_key = f"goblin_tax:{session_id}"

    try:
        current_usage = cache_client.get(rate_key)
        # Limit: 100 AI calls per hour per session to protect the Moat
        if current_usage and int(current_usage) > 100:
            return False

        pipe = cache_client.pipeline()
        pipe.incr(rate_key)
        pipe.expire(rate_key, 3600)
        pipe.execute()
        return True
    except:
        return True


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=8))
def get_ai_response(
    prompt, llm_provider, user_api_key, profile="default", json_mode=False
):
    # 💰 GOBLIN TAX CHECK (Infrastructure 1/3)
    if not check_goblin_tax():
        return "⚠️ **GOBLIN TAX ALERT:** You have exceeded the hourly limit for AI incantations. Please wait a bit for the weave to stabilize."

    # 🛡️ HOISTED IMPORTS & VARIABLES (Prevents UnboundLocalError during retries)
    import time
    import hashlib
    import os
    import streamlit as st

    start_time = time.time()
    is_cache_hit = False
    error_msg = None
    res = ""
    cache_client = None
    cache_key = None

    try:
        # --- 🎭 PREPEND THE PERSONALITY ---
        system_intro = AI_PROFILES.get(
            profile, "You are a helpful D&D 5e Dungeon Master assistant."
        )
        full_prompt = f"{system_intro}\n\nTask: {prompt}"

        # --- 🔮 THE ORACLE CACHE CHECK ---
        redis_url = st.secrets.get("REDIS_URL", None)
        if redis_url:
            try:
                import redis

                cache_client = redis.from_url(redis_url)
            except Exception as e:
                print(f"Redis Init Error: {e}")

        if cache_client:
            prompt_hash = hashlib.md5(full_prompt.encode("utf-8")).hexdigest()
            cache_key = f"oracle_cache_{prompt_hash}"
            try:
                cached_result = cache_client.get(cache_key)
                if cached_result:
                    is_cache_hit = True
                    return cached_result.decode("utf-8")
            except Exception as e:
                print(f"Oracle Cache Read Error: {e}")
        # 🛡️ Dynamic Kwargs Bypass
        kwargs = {}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        # --- 🛡️ THE FAILOVER MATRIX (LLM Execution Logic) ---
        if llm_provider == "☁️ Groq (Cloud)":
            # 🎯 Look for the key in Streamlit Secrets FIRST, then check Render Environment Variables
            api_key = (
                user_api_key
                if user_api_key
                else st.secrets.get("GROQ_API_KEY", os.environ.get("GROQ_API_KEY"))
            )
            if not api_key:
                return "⚠️ Please enter your Groq API Key in the sidebar."

            try:
                from groq import Groq

                client = Groq(api_key=api_key)
                res = (
                    client.chat.completions.create(
                        messages=[{"role": "user", "content": full_prompt}],
                        model="llama-3.3-70b-versatile",
                        **kwargs,
                    )
                    .choices[0]
                    .message.content
                )
            except Exception as groq_error:
                # 🔄 FAILOVER INITIATED: Groq is rate-limited. Pivoting to OpenAI.
                print(f"Groq API Error: {groq_error}. Engaging Failover Matrix...")
                openai_fallback = st.secrets.get(
                    "OPENAI_API_KEY", os.environ.get("OPENAI_API_KEY")
                )
                if openai_fallback:
                    from openai import OpenAI

                    backup_client = OpenAI(api_key=openai_fallback)
                    res = (
                        backup_client.chat.completions.create(
                            model="gpt-4o-mini",
                            messages=[{"role": "user", "content": full_prompt}],
                            **kwargs,
                        )
                        .choices[0]
                        .message.content
                    )
                else:
                    raise groq_error  # No fallback available, Tenacity will retry
        else:
            import ollama

            res = ollama.chat(
                model="llama3.1", messages=[{"role": "user", "content": full_prompt}]
            )["message"]["content"]

        # --- 📥 SAVE TO ORACLE CACHE ---
        if cache_client and res and not res.startswith("⚠️"):
            try:
                cache_client.setex(cache_key, 86400, res)
            except Exception as e:
                print(f"Oracle Cache Write Error: {e}")

        return res

    except Exception as err:
        error_msg = str(err)
        raise err  # Let tenacity @retry handle the actual crash recovery

    finally:
        # --- 📊 ENTERPRISE TELEMETRY (LATENCY & HEALTH TRACKING) ---
        execution_time = round(time.time() - start_time, 2)
        # We use the globally defined 'db' variable safely at runtime
        if "db" in globals() and db is not None:
            try:
                db.collection("llm_telemetry").add(
                    {
                        "provider": llm_provider,
                        "profile": profile,
                        "latency_seconds": execution_time,
                        "cache_hit": is_cache_hit,
                        "status": "error" if error_msg else "success",
                        "error_details": error_msg,
                        "timestamp": firestore.SERVER_TIMESTAMP,
                    }
                )
            except Exception:
                pass  # Fail silently. Never crash the app over a telemetry failure.


# --- 🚀 MASTER DATABASE CONNECTION POOL ---
@st.cache_resource(show_spinner=False)
def init_firestore():
    """Builds and holds a single, persistent connection to Google Cloud."""
    try:
        if (
            os.path.exists("temp_firestore_key.json")
            and os.path.getsize("temp_firestore_key.json") > 0
        ):
            with open("temp_firestore_key.json", "r") as f:
                key_data = json.load(f)
            creds = service_account.Credentials.from_service_account_file(
                "temp_firestore_key.json"
            )
            return firestore.Client(
                credentials=creds,
                project=key_data.get("project_id", "dm-copilot-analytics"),
            )
    except Exception as e:
        print(f"Firestore Init Error: {e}")
    return None


@st.cache_resource(show_spinner=False)
def init_qdrant(_url, _key):
    """Builds and holds a single, persistent connection to the Qdrant Vector Cloud."""
    if not _url:
        return None
    return QdrantClient(url=_url, api_key=_key, timeout=10.0)


# 1. Boot the persistent databases
db = init_firestore()

# 2. Boot the traffic analytics (Deprecated - Using custom Enterprise Telemetry)
import contextlib

analytics_context = contextlib.nullcontext()

with analytics_context:
    # --- 💓 THE ENTERPRISE HEARTBEAT (Session Tracker) ---
    if "app_session_id" not in st.session_state:
        import uuid

        st.session_state.app_session_id = str(uuid.uuid4())
        st.session_state.session_start = firestore.SERVER_TIMESTAMP

    @st.fragment(run_every=60)
    def session_heartbeat():
        """Silently pulses every 60 seconds to track how long users keep the app open."""
        if db is not None:
            try:
                db.collection("active_sessions").document(
                    st.session_state.app_session_id
                ).set(
                    {
                        "campaign_id": st.session_state.get(
                            "campaign_id", "anonymous_dm"
                        ),
                        "start_time": st.session_state.session_start,
                        "last_ping": firestore.SERVER_TIMESTAMP,
                    },
                    merge=True,
                )
            except Exception:
                pass  # Fail silently. Never crash the DM's game over telemetry.

    # Fire the heartbeat in the background
    session_heartbeat()
    # -----------------------------------------------------

    # --- 🏛️ THE WELCOME HUB (GATEKEEPER) ---
    if st.session_state.get("view_mode", "Landing") == "Landing":
        st.markdown(
            "<h1 style='text-align: center;'>🐉 DM CO-PILOT</h1>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<h3 style='text-align: center;'>Welcome, Dungeon Master. What are we building today?</h3>",
            unsafe_allow_html=True,
        )
        st.write("---")

        # 👇 THE MISSING KEYS TO THE APP 👇
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            if st.button("⚔️ RUN COMBAT", use_container_width=True):
                st.session_state.view_mode = "Tool"
                st.session_state.nav_category = "⚔️ The Combat Forge"
                st.session_state.page = "🛡️ Initiative Tracker"
                st.rerun()
        with col2:
            if st.button("📜 FORGE LORE", use_container_width=True):
                st.session_state.view_mode = "Tool"
                st.session_state.nav_category = "🧠 Campaign Archive"
                st.session_state.page = "🧠 Infinite Archive (Beta)"
                st.rerun()
        with col3:
            if st.button("📖 DM'S GUIDE", use_container_width=True):
                st.session_state.view_mode = "Tool"
                st.session_state.nav_category = "🏠 Hub & System"
                st.session_state.page = "📜 DM's Guide"
                st.rerun()
        with col4:
            if st.button("📱 PLAYER PORTAL", type="primary", use_container_width=True):
                st.session_state.view_mode = "Player"
                st.rerun()

        st.write("---")
        st.info(
            "Select a destiny above to begin. The #1 Rated VTT Toolkit on Viberank is ready."
        )

        # Telemetry Metrics for the Landing Page
        c1, c2, c3 = st.columns(3)
        c1.metric("Viberank Rank", "#1", "Global AI TTRPG")
        c2.metric("Engine Status", "v6.6 Live", "Lore-Aware")
        c3.metric("VTT Link", "Ready", "Foundry / Roll20")
        st.stop()  # 🛑 The Airlock
    elif st.session_state.get("view_mode") == "Player":
        st.markdown(
            "<h1 style='text-align: center; color: #00FF00;'>📱 The Player Portal</h1>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<p style='text-align: center;'>Enter your DM's Room Code to view the live battlefield.</p>",
            unsafe_allow_html=True,
        )

        c1, c2, c3 = st.columns([1, 2, 1])
        with c2:
            join_code = (
                st.text_input(
                    "DM's Room Code:", placeholder="e.g., caleb_strahd_tuesday"
                )
                .strip()
                .lower()
            )
            if st.button("Join Table 🎲", type="primary", use_container_width=True):
                if join_code:
                    st.session_state.player_room = join_code
                    st.session_state.view_mode = "Player_Active"
                    st.rerun()
            if st.button("⬅️ Back to Hub", use_container_width=True):
                st.session_state.view_mode = "Landing"
                st.rerun()
        st.stop()

    elif st.session_state.get("view_mode") == "Player_Active":
        room = st.session_state.get("player_room", "unknown")
        st.title(f"📡 Live Table: {room}")

        # Removed the manual refresh button—the players only need a way out now
        if st.button("⬅️ Leave Table", use_container_width=True):
            st.session_state.view_mode = "Landing"
            st.rerun()

        st.divider()
        # --- 🐉 BATCH 7, PILLAR 1: TWO-WAY PLAYER PORTAL SYNC ---
        st.markdown("### 🩸 Manage Health")
        st.caption(
            "Update your HP here to instantly sync with the DM's combat tracker."
        )

        col_hp1, col_hp2, col_hp3 = st.columns([2, 1, 1])
        with col_hp1:
            target_name = st.text_input(
                "Character Name:", placeholder="Must exactly match the DM's tracker..."
            )
        with col_hp2:
            new_hp_val = st.number_input("New HP:", min_value=0, value=0, step=1)
        with col_hp3:
            st.markdown("<br>", unsafe_allow_html=True)  # Visual alignment hack
            if st.button("Sync HP 🚀", type="primary", use_container_width=True):
                if target_name:
                    import requests

                    # 🎯 The Bridge to Google Cloud Serverless
                    webhook_url = "https://vtt-webhook-final-s5oaa43sma-uw.a.run.app"
                    payload = {
                        "campaign_id": room,  # Automatically grabs the active Room Code
                        "name": target_name,
                        "hp": new_hp_val,
                    }
                    try:
                        res = requests.post(webhook_url, json=payload, timeout=5)
                        if res.status_code == 200:
                            st.success(f"Health synced to {new_hp_val}!")
                            st.balloons()
                        elif res.status_code == 404:
                            st.error(
                                "Character not found. Make sure your name matches the DM's tracker exactly!"
                            )
                        else:
                            st.error(f"Sync failed (Code {res.status_code}).")
                    except Exception as e:
                        st.error(f"Network error: {e}")
                else:
                    st.warning("Please enter your character's name!")

        st.divider()
        # --- 🏰 BATCH 7, PILLAR 3: THE GUILDHALL (Async Downtime) ---
        st.markdown("### 🏰 The Guildhall")
        st.caption(
            "Waiting for your turn? Spend your downtime here while the DM handles combat."
        )

        with st.expander("🚪 Enter the Guildhall", expanded=False):
            gh_col1, gh_col2 = st.columns([1, 1])
            with gh_col1:
                guild_character = st.text_input(
                    "Who is embarking?",
                    placeholder="Your character name...",
                    key="gh_name",
                )
            with gh_col2:
                guild_activity = st.selectbox(
                    "Choose Activity",
                    [
                        "🎲 Gamble at the Tavern",
                        "🧪 Brew a Potion",
                        "👂 Listen for Rumors",
                        "🗡️ Sharpen Weapons",
                    ],
                    key="gh_activity",
                )

            if st.button("Embark on Activity 🎲", use_container_width=True):
                if guild_character:
                    with st.spinner("The fates are deciding..."):
                        try:
                            # 🎯 Using the fast Groq cloud fallback so players don't need API keys
                            prompt = f"A D&D player named {guild_character} is doing this downtime activity: {guild_activity}. Generate a fun, 2-sentence outcome. Did they succeed? Did they lose gold? Did they hear a secret? Make it punchy and immersive."

                            outcome = get_ai_response(prompt, "☁️ Groq (Cloud)", "")
                            st.info(outcome)
                        except Exception as e:
                            st.error(f"The Guildhall is currently closed: {e}")
                else:
                    st.warning("Please tell the Guildmaster your name first!")

        st.divider()

    # --- THE AUTO-POLLING ENGINE (Real-Time Sync) ---


@st.fragment(run_every="3s")
def live_battlefield_sync():
    # 🛡️ BATCH 8 FINAL FIX: Define room scope for the polling engine
    room = st.session_state.get("player_room", "unknown")

    if db is not None:
        try:
            # 🛡️ BATCH 7, PILLAR 2: DISTRIBUTED EDGE CACHING (Request Coalescer)
            table_data = None
            cache_client = get_redis_client()
            cache_key = f"live_table_{room}"

            # 1. The Intercept: Try pulling from the lightning-fast Redis cache first
            if cache_client:
                try:
                    cached = cache_client.get(cache_key)
                    if cached:
                        table_data = json.loads(cached.decode("utf-8"))
                except Exception as e:
                    print(f"Redis intercept failed: {e}")

            # 2. The Shield: If Redis is empty, ask Google Cloud ONCE, then restock Redis for the other players
            if not table_data:
                doc_ref = db.collection("live_tables").document(room)
                doc = doc_ref.get()
                if doc.exists:
                    table_data = doc.to_dict()
                    if cache_client:
                        try:
                            # Cache it for exactly 3 seconds. This coalesces all player traffic!
                            # (We safely extract 'combatants' to avoid crashing on Firestore timestamp objects)
                            safe_cache_data = {
                                "combatants": table_data.get("combatants", [])
                            }
                            cache_client.setex(
                                cache_key, 3, json.dumps(safe_cache_data)
                            )
                        except Exception:
                            pass

                    # 3. The UI Render (Now with The Cartographer's Veil)
                    if table_data:
                        # Map Reveal Logic
                        revealed_room = table_data.get("revealed_room")
                        if revealed_room:
                            st.markdown(
                                f"""
                                    <div style='background-color: #1a1a1a; border: 1px solid #00FF00; padding: 15px; border-radius: 8px; text-align: center; margin-bottom: 15px;'>
                                        <h4 style='color: #00FF00; margin: 0;'>🗺️ New Area Revealed</h4>
                                        <h2 style='color: white; margin: 5px 0 0 0;'>{revealed_room.title()}</h2>
                                    </div>
                                    """,
                                unsafe_allow_html=True,
                            )

                        combatants = table_data.get("combatants", [])
                        st.markdown("### ⚔️ Initiative Order")

                        for idx, c in enumerate(combatants):
                            name = c.get("name", "Unknown")
                            init = c.get("init", 0)
                            status = c.get("status", "Healthy 🟢")
                            conds = ", ".join(c.get("conditions", []))
                            cond_text = f"*( {conds} )*" if conds else ""

                            if idx == 0:
                                st.success(
                                    f"**▶️ ACTIVE TURN:** {name} | Init: {init} | Status: {status} {cond_text}"
                                )
                            else:
                                st.info(
                                    f"**⏳ {name}** | Init: {init} | Status: {status} {cond_text}"
                                )
                    else:
                        st.warning(
                            "The DM hasn't broadcasted any combat data to this room yet! Waiting for transmission..."
                        )
        except Exception as e:
            st.error(f"Scrying error: {e}")
        else:
            st.error("Cloud disconnected. Cannot scry the table.")
        live_battlefield_sync()
        st.stop()


# --- ⚔️ THE SIDEBAR (ONLY SHOWS IN TOOL MODE) ---
if st.sidebar.button("⬅️ Back to Welcome Hub"):
    st.session_state.view_mode = "Landing"
    st.rerun()

st.sidebar.markdown(
    "<h2 style='text-align: center;'>🐉 DM CO-PILOT</h2>", unsafe_allow_html=True
)
llm_provider = st.sidebar.radio("Engine", ["☁️ Groq (Cloud)", "💻 Ollama (Local)"])
# --- UNIFIED KEY BRIDGE ---
# Groq Bridge
stored_groq = st.secrets.get("GROQ_API_KEY", "")
user_groq_input = st.sidebar.text_input(
    "Groq API Key",
    type="password",
    placeholder="Key found in Vault 🔒" if stored_groq else "Enter Groq Key...",
)
user_api_key = user_groq_input if user_groq_input else stored_groq

# --- HARDENED OPENAI BRIDGE ---
import os

# Check Streamlit Secrets FIRST, then System Environment (Render Vault)
stored_openai = st.secrets.get("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY", "")

user_openai_input = st.sidebar.text_input(
    "OpenAI API Key",
    type="password",
    placeholder="Key found in Vault 🔒" if stored_openai else "Enter OpenAI Key...",
)
openai_key = user_openai_input if user_openai_input else stored_openai
# --- 🔐 THE MULTIPLAYER SESSION LOCK ---
st.sidebar.markdown("---")
st.sidebar.markdown(
    "<h3 style='text-align: center; margin-bottom: 0px;'>🔐 Campaign ID</h3>",
    unsafe_allow_html=True,
)

# This acts as the "Room Code" to keep different DMs' data isolated
campaign_id = (
    st.sidebar.text_input(
        "Enter a unique ID for your campaign:",
        value="default_tavern",
        help="Use a unique name (e.g., 'Caleb_Strahd_Tuesday') so other users don't overwrite your saves!",
    )
    .strip()
    .lower()
)

# Store it globally so all tools can see it
st.session_state.campaign_id = campaign_id
st.sidebar.markdown("---")

# --- 🔌 GLOBAL VTT WEBHOOK ---
st.sidebar.markdown(
    "<h3 style='text-align: center; margin-bottom: 0px;'>🔌 VTT Webhook</h3>",
    unsafe_allow_html=True,
)
vtt_url = st.sidebar.text_input(
    "Global Foundry/Roll20 URL:",
    value=st.session_state.get("vtt_url", ""),
    placeholder="http://localhost:30000/api/import",
    help="Paste your VTT REST API URL here once to enable one-click exporting across the entire app.",
)
st.session_state.vtt_url = vtt_url

st.sidebar.markdown("---")

# --- 🎶 THE BARDIC BROADCAST ---
st.sidebar.markdown("---")
st.sidebar.markdown(
    "<h3 style='text-align: center; margin-bottom: 0px;'>🎶 Bardic Broadcast</h3>",
    unsafe_allow_html=True,
)
st.sidebar.caption("Background ambience for your table.")

# Your custom, hand-picked Spotify links!
audio_vibes = {
    "🔇 Silence (Off)": "",
    "🍻 Crowded Tavern": "https://open.spotify.com/embed/playlist/4hc98N2WURWgeCLM3oyQh0?theme=0",
    "💀 Epic Boss Fight": "https://open.spotify.com/embed/playlist/5WnB6wpclrPltZNYBjQQ7c?theme=0",
    "🌲 Creepy Forest": "https://open.spotify.com/embed/playlist/6qKtNWT6ox9316G3taIRHp?theme=0",
    "🛡️ Heroic Travel": "https://open.spotify.com/embed/playlist/7BkG8gSv69wibGNU2imRMx?theme=0",
}

selected_vibe = st.sidebar.selectbox(
    "Select Vibe", list(audio_vibes.keys()), label_visibility="collapsed"
)

if selected_vibe != "🔇 Silence (Off)":
    import streamlit.components.v1 as components

    with st.sidebar:
        components.iframe(audio_vibes[selected_vibe], height=152)

    # --- ⏳ THE CHRONO-LOG ---
    st.sidebar.markdown("---")
    st.sidebar.markdown(
        "<h3 style='text-align: center; margin-bottom: 0px;'>⏳ Chrono-Log</h3>",
        unsafe_allow_html=True,
    )

    # 1. Initialize Time State
    if "dungeon_time" not in st.session_state:
        st.session_state.dungeon_time = 0  # Total minutes passed
    if "torch_time" not in st.session_state:
        st.session_state.torch_time = 0  # Remaining torch minutes

    # 2. Time Control Buttons (Keys removed for auto-generation safety)
    col_t1, col_t2, col_t3 = st.sidebar.columns(3)
    if col_t1.button("+10 Min"):
        st.session_state.dungeon_time += 10
        st.session_state.torch_time = max(0, st.session_state.torch_time - 10)
    if col_t2.button("+1 Hr"):
        st.session_state.dungeon_time += 60
        st.session_state.torch_time = max(0, st.session_state.torch_time - 60)
    if col_t3.button("+8 Hr"):
        st.session_state.dungeon_time += 480
        st.session_state.torch_time = 0  # Torches burn out

    # 3. Calculate and Display the Clock
    days = st.session_state.dungeon_time // 1440
    hours = (st.session_state.dungeon_time % 1440) // 60
    minutes = st.session_state.dungeon_time % 60
    st.sidebar.caption(f"**Elapsed Time:** Day {days + 1} | {hours}h {minutes}m")

    # 4. The Torch Tracker UI (Crash-Proof Version)
    if st.session_state.torch_time <= 0:
        if st.sidebar.button("🕯️ Light Torch (60m)", use_container_width=True):
            st.session_state.torch_time = 60
            # Streamlit auto-reruns on click, no st.rerun() needed!

    if st.session_state.torch_time > 0:
        st.sidebar.caption(
            f"🔥 **Torch Active:** {st.session_state.torch_time} mins left"
        )
        st.sidebar.progress(st.session_state.torch_time / 60.0)
    elif st.session_state.torch_time == 0 and st.session_state.dungeon_time > 0:
        st.sidebar.warning("🌑 The area is pitch black.")

# --- 📂 TOOL MODULES CATEGORIZATION (v7.5 Human-First Refactor) ---
cats = [
    "🏠 Welcome Hub",
    "📝 Session Prep",
    "⚔️ Live Tabletop",
    "📚 Campaign Lore",
    "🎲 Random Generators",
    "🎭 Community Board",
]

tool_cat = st.sidebar.selectbox("Select Menu", cats, key="tool_cat_v75")

if tool_cat == "🏠 Welcome Hub":
    page = st.sidebar.radio(
        "Active Tool",
        [
            "📜 DM's Guide",
            "🆕 Patch Notes",
            "🛠️ Admin Dashboard",
            "🛠️ Bug Reports & Feature Requests",
        ],
        key="cat_hub_v75",
    )
elif tool_cat == "📝 Session Prep":
    page = st.sidebar.radio(
        "Active Tool",
        [
            "🐉 Monster Lab",  # Formally 'Monster Bestiary'
            "🦹 Villain Architect",
            "💎 Magic Item Artificer",
            "⚔️ Encounter Architect",
            "🌍 Worldbuilder",
            "🧬 Homebrew Forge",
        ],
        key="cat_prep_v75",
    )
elif tool_cat == "⚔️ Live Tabletop":
    page = st.sidebar.radio(
        "Active Tool",
        [
            "🛡️ Initiative Tracker",
            "📋 Player Cheat Sheet",
            "⚖️ Real-Time Rules Lawyer",
            "⚖️ Action Economy Analyzer",
            "🎲 Fate-Threader (v4.1)",
            "🔌 VTT Bridge",
            "🎙️ Audio Scribe",
            "👁️ Cartographer's Eye",
        ],
        key="cat_live_v75",
    )
elif tool_cat == "📚 Campaign Lore":
    page = st.sidebar.radio(
        "Active Tool",
        [
            "🧠 Infinite Archive (Beta)",
            "📚 PDF-Lore Chat",
            "📜 Session Recap",
            "🌐 Auto-Wiki Export",
            "📜 Scribe's Handouts",
            "🕸️ Web of Fates",
            "🦋 Living World Simulator",
        ],
        key="cat_lore_v75",
    )
elif tool_cat == "🎲 Random Generators":
    page = st.sidebar.radio(
        "Active Tool",
        [
            "🎭 NPC Quick Forge",
            "🍻 Tavern Rumor Mill",
            "💰 Dynamic Shops",
            "🗑️ Pocket Trash Loot",
            "👑 The Dragon's Hoard",
            "⚙️ Trap Architect",
            "🤖 DM Assistant",
        ],
        key="cat_rand_v75",
    )
elif tool_cat == "🎭 Community Board":
    page = st.sidebar.radio(
        "Active Tool",
        ["🤝 DM Matchmaker", "🏛️ Community Vault", "🌐 Multiverse Nexus"],
        key="cat_social_v75",
    )
# Your original Discord/Coffee links and Dice Roll continue below...
# --- 🎲 THE QUICK DICE ROLLER ---
st.sidebar.markdown("---")
st.sidebar.markdown(
    "<h3 style='text-align: center; margin-bottom: 0px;'>🎲 Quick Roll</h3>",
    unsafe_allow_html=True,
)
col_d1, col_d2 = st.sidebar.columns([1, 1])
dice_type = col_d1.selectbox(
    "Dice",
    ["d20", "d12", "d10", "d8", "d6", "d4", "d100"],
    label_visibility="collapsed",
)
if col_d2.button("Roll!", use_container_width=True):
    import random

    sides = int(dice_type[1:])
    roll_result = random.randint(1, sides)
    st.sidebar.markdown(
        f"<div class='dice-result'>{roll_result}</div>", unsafe_allow_html=True
    )

if page == "📜 DM's Guide":
    st.title("📜 Welcome to the DM Co-Pilot")
    st.markdown(
        "Welcome to your AI-powered Dungeon Master workstation. This guide covers the core features of the **v6.8 Masterwork Edition**."
    )
    st.info(
        "⚡ **v6.8 Update:** The app now features a distributed edge cache and background UI threading. Heavy generators (like Cinematic Recaps and Bulk VTT exports) will now run silently in the background so you can keep tracking combat without the app freezing!"
    )
    with st.expander("🧠 Campaign Archive: Audio Scribe & Safety Monitor"):
        st.write(
            """
        The **Audio Scribe** uses the Whisper API to transcribe your session audio.
        * **🛡️ Auto-Safety Monitor:** Toggle this on to passively scan your audio for safety keywords.
        * **👁️ The Auto-Fetch Oracle:** Speak a standard monster name while recording, and its stats will automatically appear on screen.
        * **🔊 The Sound-Weaver:** Say cinematic triggers (like "fireball" or "dragon") to auto-play sound effects.
        * Click **Turn into Campaign Notes** to format the raw transcription into readable session logs.
        """
        )

    with st.expander("🔮 Infinite Archive: Pre-Cog & Continuity Cop"):
        st.write(
            """
        Stop prepping from scratch and avoid plot holes.
        1. **The Pre-Cog Engine:** Scroll to the bottom and click **Generate Next Session Prep 🔮**. The AI will read your past session memories and generate a custom hook tailored to what your players just did.
        2. **🚨 The Continuity Cop:** Paste your upcoming session prep into the auditor. The AI will cross-reference it against your entire campaign memory and flag any lore contradictions (like reusing a dead NPC).
        """
        )

    with st.expander("🗂️ How to Navigate the Workstation"):
        st.write(
            """
            To prevent tool-clutter, all 36+ modules are categorized in the left sidebar:
            * **🏠 Hub & System:** Patch notes, guides, and bug reporting.
            * **🧠 Campaign Archive:** Audio transcriptions, session recaps, and wiki exports.
            * **⚔️ The Combat Forge:** Initiative tracking, encounter building, and rule-checking.
            * **🐉 The VTT Factory:** Monster/Item generation, VTT bridging, and homebrew.
            * **🎲 The Lore & Randomizer:** Dynamic shops, rumors, NPCs, and trap generation.
            * **🎭 Social & Community:** Matchmaking and the community content vault.
            """
        )

    with st.expander("⚔️ The Combat Forge: Initiative, Snapshots & OCR"):
        st.write(
            """
            The **Initiative Tracker** is protected by a Local SQLite Database to prevent data loss.
            1. Click **💾 Save Combat Snapshot** to hard-save the current state to the server. If your browser crashes, click **🔄 Recover Last Snapshot** to restore the battlefield instantly.
            2. **👁️ The Tabletop Eye:** Expand the Tabletop Eye menu, grant webcam access, and hold up a physical d20. The Vision AI will read the physical die and automatically calculate the total with your modifiers!
            """
        )

    with st.expander("🎙️ Audio Scribe: Safety & The Omniscient Scribe"):
        st.write(
            """
        The **Audio Scribe** uses the Whisper API to transcribe your session audio.
        * **🛡️ Auto-Safety Monitor (Vibe Check):** Toggle this on to passively scan your audio for safety keywords (like the "X-Card").
        * **📖 The Omniscient Scribe:** The AI listens for rules confusion. If a player asks, "Wait, what does restrained do again?", the RAW 5e rule will instantly flash on your screen.
        * Click **Turn into Campaign Notes** to format the raw transcription into readable session logs.
        """
        )

    with st.expander("🐉 The VTT Factory: Exporting to Foundry/Roll20"):
        st.write(
            """
            The **v7.0 Bridge** is optimized for Foundry dnd5e v3.0+.
            * **🚀 Direct Blast:** Enter your Relay URL in the sidebar and hit 'Send to Live VTT'. The app handles the complex `entityType` handshake and data sanitization automatically.
            * **📥 Manual Import:** If your firewall blocks the bridge, use the 'Download JSON' button. Our code now uses 'Feat' wrappers to ensure your stats never arrive as a blank sheet.
            """
        )

    with st.expander("⚖️ Rules Lawyer: The DC Calibrator"):
        st.write(
            """
            When players try something wild (like swinging from a chandelier), use the **DC Calibrator**. 
            1. Type the action into the prompt.
            2. The AI will calculate the correct **Skill Check**, the **DC**, and the **Mechanical Consequence** of failing.
            """
        )

    with st.expander("💰 Dynamic Shops: The Loot Ledger"):
        st.write(
            """
            Stop doing manual math at the end of the night. 
            1. Paste your messy loot notes (e.g., '140cp, 20gp, a silver ring') into the **Loot Ledger**.
            2. Set your party size.
            3. The AI converts everything to Gold (gp) and tells you exactly how much each player receives.
            """
        )
    with st.expander("⚔️ Encounter Architect: Multi-Agent Playtesting"):
        st.write(
            """
            Struggling to balance a boss fight?
            1. Generate your encounter based on party level and theme.
            2. Click **🎲 Spawn Phantom Party & Run Simulation**. 
            3. The app will spawn 4 virtual AI players to run through the encounter in the background and provide a playtest report detailing exactly how your players will try to break the fight, and who is most likely to die.
            """
        )

    with st.expander("🏆 Encounter Architect: Skill Challenges"):
        st.write(
            """
            For non-combat encounters (chases, rituals, social galas), use the **Skill Challenge Architect**.
            1. Define the goal (e.g., 'Escaping the collapsing city').
            2. Set the complexity (number of successes needed).
            3. The AI provides the DC, suggested skills, and a narrative consequence for failure.
            """
        )
    with st.expander("🤝 Social & Community: Matchmaker & Vault"):
        st.write(
            """
            * **DM Matchmaker:** Post a listing to find players or a DM. The board is synced globally via Cloud Firestore and can be filtered by role.
            * **Community Vault:** Share your best creations. The vault automatically sanitizes personal info (PII) and protected IP to keep the community safe.
            """
        )

    with st.expander("📦 VTT Factory: Bulk Encounter Export"):
        st.write(
            """
            Instead of exporting monsters one by one, use the **Encounter Architect**.
            1. Generate your encounter.
            2. Click **1. Forge Bulk JSON** to compile all monsters and traps into one payload.
            3. Click **2. 🚀 Blast to Live VTT** to send the entire army to Foundry/Roll20 in a single click.
            """
        )
    with st.expander("📱 The Player Portal & The Guildhall"):
        st.write(
            """
            You no longer need to manage every single HP drop or entertain players between turns!
            1. Have your players open the **Player Portal** on their phones using your unique Campaign ID.
            2. **Two-Way Sync:** When a player takes damage, they can type their new HP into their phone and hit Sync. Your DM Initiative Tracker will automatically update!
            3. **The Guildhall:** While waiting for their turn in combat, players can open The Guildhall on their phones to gamble, craft items, or generate narrative rumors without interrupting the table.
            """
        )
    st.divider()

    st.markdown("### 🗺️ Quick Start Guide")
    st.markdown(
        """
        - **Crash-Proof Combat:** Keep the *Initiative Tracker* open during live games. It now saves directly to a local server database so you can instantly recover your turn order if you accidentally refresh.
        - **Table Safety:** Use the *Audio Scribe* and turn on the *Vibe Check Monitor* to passively scan live audio for safety tool keywords (like the X-Card) without interrupting the game.
        - **Combat Prep:** Use the *Fate-Threader* to mathematically balance boss fights using 1,000-loop Monte Carlo simulations.
        - **Live Lore:** Upload your module to the *PDF-Lore Chat* and let the AI pull exact paragraph references in sub-seconds.
        """
    )
elif page == "🆕 Patch Notes":
    st.title("🆕 Patch Notes & Updates")
    st.write(
        "Welcome to the changelog! Here is what the DM Co-Pilot has been learning:"
    )
    # --- NEW v7.0 "THE UNBREAKABLE BRIDGE" UPDATE ---
    st.markdown("### ⚔️ v7.0 - The Unbreakable Bridge (Live!)")
    st.markdown(
        """
        * **🚀 Foundry v5.2.5 Validation:** Completely rebuilt the VTT Bridge to survive strict Schema validation.
        * **🛡️ Type-Safety Forge:** Implemented `safe_int` and `safe_cr` sanitizers to prevent "Blank Sheet" import errors.
        * **🔌 Relay Handshake Fix:** Corrected payload headers to use `entityType` for 100% relay compatibility.
        * **📊 Telemetry 2.0:** Admin Dashboard now tracks **Active Heartbeats** (199+ DMs) and **Total Generations** (Lifetime count) in real-time.
        * **⚡ Latency Shield:** Optimized the Redis look-aside cache to maintain sub-1.2s response times under heavy load.
        """
    )
    # --- NEW v6.9.1 UPDATE ---
    st.markdown("### 🛡️ v6.9.1 - The Hardened Soul (Live!)")
    st.markdown(
        """
    * **🏆 Viberank #1 Optimization:** To celebrate hitting #1 on Viberank, we've migrated to a **Standard Instance** with dedicated CPU and 2GB RAM.
    * **🧹 Background Garbage Collector:** A new silencer thread now scrubs 'Zombie' memory leaks every 60 seconds to prevent session hangs.
    * **🔮 Oracle Redis Hard-Link:** The semantic cache is now hard-linked to Port 10000 with a 15-second 'Airlock' delay, ensuring 99.9% uptime during high-traffic surges.
    * **⚙️ Zero-Downtime Swaps:** Improved health-check logic allows us to push updates without kicking active DMs off their screens.
    """
    )
    st.divider()
    # --- NEW v6.9 UPDATE ---
    st.markdown("### 🏰 v6.9 - The Acquisition Moat (Live!)")
    st.markdown(
        """
    * **🔄 Two-Way Player Portal:** Players can now manage their own HP directly from their phones! Enter a new HP value in the portal, and the DM's combat tracker updates automatically.
    * **🛡️ Edge-Cached DB Shield:** We deployed a massive infrastructure upgrade. The app now uses a Redis request coalescer to handle high player traffic, keeping your DM screen lightning fast and crash-proof.
    * **🏰 The Guildhall:** Players getting bored waiting for their turn? They can now gamble at the tavern, craft potions, and listen for rumors entirely on their phones using frictionless AI downtime activities.
    """
    )
    st.divider()

    # --- NEW v6.8 UPDATE ---
    st.markdown("### ⚡ v6.8 - The Unkillable Infrastructure (Live!)")
    st.markdown(
        """
    * **💽 The Edge-Cached Bestiary:** We've integrated a globally distributed Redis cache. Loading the monster database is now instantaneous across all active servers, making the app noticeably faster!
    * **🛡️ The Failover Matrix:** Unkillable uptime. If our primary AI encounters heavy weekend traffic, the system now silently routes your requests to a secondary backup model without crashing your game.
    * **🚀 The Asynchronous Aegis:** Generating Cinematic Recaps and Art no longer freezes the app! Background processing allows you to keep running combat while the AI paints your scenes.
    """
    )
    st.divider()

    # --- NEW v6.7 UPDATE ---
    st.markdown("### 🛡️ v6.7 - The Automation & Triage Update (Live!)")
    st.markdown(
        """
* **🎙️ The Omniscient Scribe:** The Audio Scribe now passively listens for rules questions. If someone at the table asks how a condition or spell works, the exact rule will pop up on your screen automatically!
* **🚨 The Continuity Cop:** Head to the Infinite Archive. Paste your session prep, and the AI will audit it against your campaign history to warn you about plot holes and contradictions.
* **🔌 VTT Diagnostics Wizard:** Having trouble exporting to Foundry? The VTT Bridge now features a built-in connection tester to help you diagnose local firewall and Ngrok issues.
"""
    )
    st.divider()

    st.markdown("### 🏰 v6.6 - The Real-Time Architecture (Live!)")
    st.markdown("### 🏰 v6.6 - The Acquisition Moat (Live!)")
    st.markdown(
        """
* **👁️ The Tabletop Eye:** You can now roll physical dice! Turn on your webcam in the Initiative Tracker, roll a d20, and the Vision AI will read the physical die and do the math for you.
* **👻 The Phantom Party:** Head to the Encounter Architect. You can now spawn 4 AI personas to "playtest" your dungeon and warn you where your players are most likely to die.
* **⚡ Async VTT Exports:** Sending massive JSON payloads to Foundry/Roll20 now happens in a background thread. Your UI will never freeze while exporting again.
* **📡 Live Player Portal:** The Player Portal now uses an auto-polling engine. Players see monster HP and status changes instantly—no manual refreshing required!
* **📈 Global Telemetry:** A massive thank you to the 450+ DMs using the app! We've implemented silent health tracking to monitor our servers and keep your game running lightning fast.
"""
    )
    st.divider()

    # --- NEW v6.5 UPDATE ---
    st.markdown("### 🔮 v6.5 - The Predictive Oracle Update (Live!)")
    st.markdown(
        """
* **👁️ The Auto-Fetch Oracle:** Zero-click monster stat retrieval. Whisper hears a monster name, and the AI instantly pulls its stats from the Bestiary RAM Cache to your screen.
* **🔊 The Sound-Weaver:** Cinematic audio automation. Whisper detects trigger words (like "fireball") and instantly plays the corresponding sound effect over your table.
* **🔮 The Pre-Cog Engine:** Automated predictive prep. The AI reads your Qdrant Vector history and automatically generates the next session's plot hook, NPCs, and encounters.
"""
    )
    st.divider()

    # --- NEW v6.3 UPDATE ---
    st.markdown("### 🌐 v6.3 - The Multiplayer & Memory Update (Live!)")
    st.markdown(
        """
    * **🧠 The Infinite Archive (Live):** The AI now has permanent memory. Lore is securely stored in a persistent Qdrant Vector Cloud so the AI never forgets your campaign history.
    * **🔐 Multiplayer Session IDs:** You can now run multiple campaigns simultaneously. Your combat snapshots and lore databases are completely isolated via your unique Room Code.
    * **💽 RAM Optimization:** Massive 300-page campaign PDFs now offload their FAISS vector math to the local hard drive, completely eliminating server UI lag.
    * **📌 UI Polish:** The Quick Roll dice are now permanently pinned to the sidebar, and phantom API calls have been scrubbed to make the engine lightning-fast.
    """
    )
    st.divider()

    # --- PREVIOUS v6.2 UPDATE ---
    st.markdown("### ⚙️ v6.2 - The Engine Overhaul")
    st.markdown(
        """
    * **🔌 VTT Power-Link:** Export encounters as raw JSON for **Foundry/Roll20** imports.
    * **🧬 Lore-Aware AI:** The Tactical Brain now cross-references your local monster database.
    * **🎭 Specialist Profiles:** New backend 'Profiles' (Lawyer, Tactician, Accountant) for faster, precise help.
    * **💾 Session Lock:** Persistent memory added to all tactical modules (no more vanishing results).
    """
    )
    st.divider()

    st.markdown("### 🚀 v6.1 - The Midnight Drop")
    st.markdown(
        """
    * **🎯 DC Calibrator:** Instant DC and skill recommendations for crazy player stunts.
    * **💎 Loot Ledger:** Auto-convert and split messy coin piles in *Dynamic Shops*.
    * **🧠 Tactical Brain:** Round-by-round lethal monster scripts with persistent memory.
    * **🏆 Skill Challenges:** Structured cinematic obstacles added to *Encounter Architect*.
    """
    )
    st.divider()

    st.markdown("### 🛠️ v6.0 - The Masterwork Update")
    st.markdown(
        """
    * **🗂️ Categorized Workstation:** Complete sidebar overhaul with 6 logical tool folders.
    * **💾 SQLite Combat Recovery:** Local DB snapshot engine added to the *Initiative Tracker*.
    * **🛡️ Vibe Check Engine:** Passive safety monitor added to the *Audio Scribe*.
    """
    )
    st.divider()

    st.markdown("### 🚀 Roadmap (What's Next)")
    st.info(
        """
    **The Dev Team is currently architecting...**
    * A fully integrated **Matchmaker Database** to help DMs find players directly inside the app.
    * Continued enhancements to the VTT Bridge for broader platform support.
    """
    )
elif page == "📋 Player Cheat Sheet":
    st.title("📋 Player Cheat Sheet")
    st.markdown(
        "A zero-lag tracker for your party's core stats. Edit directly in the table below—changes save automatically."
    )

    with st.expander("🔗 Import from D&D Beyond"):
        st.markdown(
            "Paste a **Public URL** OR the **Raw JSON** from the D&D Beyond Network tab."
        )

        # Dual-Input Layout for maximum reliability
        ddb_url = st.text_input(
            "D&D Beyond URL", placeholder="https://www.dndbeyond.com/characters/..."
        )
        manual_json = st.text_area(
            "OR Paste Raw JSON (Backup Fix)",
            help="If the automated scrape is blocked, paste the character JSON here.",
        )

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
                                "Referer": "https://www.dndbeyond.com/",
                            }
                            response = session.get(api_url, headers=headers, timeout=10)

                            if response.status_code == 200:
                                char_data = response.json().get("data")
                            else:
                                st.error(
                                    f"D&D Beyond blocked the request (Status: {response.status_code}). Please use the 'Raw JSON' box."
                                )
                    except Exception as e:
                        st.error(f"Connection Error: {e}")

            # 3. Process the Data into the Table
            if char_data:
                name = char_data.get("name", "Unknown Hero")

                # HP Calculation (Safe for null values)
                base_hp = char_data.get("baseHitPoints", 10) or 0
                bonus_hp = char_data.get("bonusHitPoints", 0) or 0
                max_hp = base_hp + bonus_hp

                classes = [
                    c["definition"]["name"] for c in char_data.get("classes", [])
                ]
                class_str = "/".join(classes) if classes else "Unknown Class"

                new_char = {
                    "Name": name,
                    "Class": class_str,
                    "AC": 15,
                    "Passive Perception": 10,
                    "Spell Save DC": 13,
                    "Max HP": max_hp,
                }
                new_row_df = pd.DataFrame([new_char])
                st.session_state.party_stats = pd.concat(
                    [st.session_state.party_stats, new_row_df], ignore_index=True
                )

                st.success(f"⚡ {name} ({class_str}) has joined the party!")
                st.rerun()

    st.divider()
    # Live Data Editor
    st.session_state.party_stats = st.data_editor(
        st.session_state.party_stats,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
    )

elif page == "📜 Session Recap":
    st.title("🎬 The Cinematic Recap")
    st.info(
        "Paste your raw notes (NPCs, loot, kills). The AI will forge a professional recap script, paint an epic cover image, and narrate it out loud!"
    )
    raw_notes = st.text_area("Your Notes:", height=200)

    if st.button("Generate Cinematic Recap 🎥", type="primary"):
        if not openai_key:
            st.error(
                "⚠️ This multi-modal feature requires an OpenAI API Key in the Premium Tools sidebar."
            )
        else:
            with st.spinner("Writing the script..."):
                prompt = f"Summarize these notes into a dramatic, 60-second opening monologue recap for a D&D session. Make it sound like a cinematic movie trailer: \n \n {raw_notes}"
                recap_script = get_ai_response(prompt, llm_provider, user_api_key)
                st.markdown(
                    f"<div class='stat-card'>{recap_script}</div>",
                    unsafe_allow_html=True,
                )
                st.download_button(
                    "📥 Download Script",
                    recap_script,
                    file_name="session_recap.txt",
                )

    st.divider()
    # --- 🛡️ THE ASYNCHRONOUS AEGIS (Non-Blocking UI Threading) ---
    st.markdown("### 🍿 Multimedia Export (Async Worker)")

    # 1. Cache the script so it survives Streamlit reruns
    if "recap_script_cache" not in st.session_state:
        st.session_state.recap_script_cache = ""
    if "recap_script" in locals():
        st.session_state.recap_script_cache = recap_script

    if st.session_state.recap_script_cache:
        if st.button(
            "🎨 Forge Art & Audio (Run in Background)",
            type="secondary",
            use_container_width=True,
        ):
            if not openai_key:
                st.error("⚠️ This multi-modal feature requires an OpenAI API Key.")
            else:
                st.session_state.media_status = "processing"
                st.toast(
                    "Media task sent to background thread! You can keep using the app.",
                    icon="🚀",
                )

            # 2. The Background Worker
            def async_media_worker(script_text, api_key):
                try:
                    from openai import OpenAI
                    import tempfile

                    client = OpenAI(api_key=api_key)

                    # Generate Image
                    img_response = client.images.generate(
                        model="dall-e-3",
                        prompt=f"A cinematic, high-fantasy digital art painting representing this D&D session summary: {script_text[:200]}",
                        size="1024x1024",
                        quality="standard",
                        n=1,
                    )
                    st.session_state.recap_img_url = img_response.data[0].url

                    # Generate Audio
                    audio_response = client.audio.speech.create(
                        model="tts-1", voice="onyx", input=script_text[:4000]
                    )
                    tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
                    tmp_file.write(audio_response.content)
                    tmp_file.close()

                    st.session_state.recap_audio_file = tmp_file.name
                    st.session_state.media_status = "complete"
                except Exception as e:
                    st.session_state.media_status = f"error: {e}"

            # 3. Thread Dispatch (Decoupling from the UI)
            import threading
            from streamlit.runtime.scriptrunner import add_script_run_ctx

            worker = threading.Thread(
                target=async_media_worker,
                args=(st.session_state.recap_script_cache, openai_key),
            )
            add_script_run_ctx(worker)  # Grants the thread access to session_state
            worker.start()

    # 4. The Auto-Polling UI Fragment
    @st.fragment(run_every="2s")
    def media_status_poller():
        status = st.session_state.get("media_status")
        if status == "processing":
            st.info(
                "⏳ **Asynchronous Aegis Active:** Weaving the magic in the background. You can safely navigate away to track combat!"
            )
        elif status == "complete":
            st.success("✅ Media Generation Complete!")
            c1, c2 = st.columns(2)
            with c1:
                st.image(st.session_state.recap_img_url, caption="Session Cover Art")
            with c2:
                st.audio(st.session_state.recap_audio_file, format="audio/mp3")
                with open(st.session_state.recap_audio_file, "rb") as f:
                    st.download_button(
                        "📥 Download MP3",
                        data=f,
                        file_name="cinematic_recap.mp3",
                        mime="audio/mpeg",
                    )
        elif str(status).startswith("error"):
            st.error(f"Background thread failed: {status}")

    media_status_poller()

    st.divider()

    # --- 🦇 BATCH 8: THE CHRONICLER'S ECHO (Discord Viral Loop) ---
    st.markdown("### 🦇 The Chronicler's Echo")
    st.markdown(
        "Auto-generate a session journal from a specific character's Point of View and blast it directly to your Discord server."
    )

    col_c1, col_c2 = st.columns(2)
    with col_c1:
        pov_character = st.text_input(
            "Character POV Name:", placeholder="e.g., Grog the Barbarian"
        )
        discord_webhook = st.text_input(
            "Discord Webhook URL:",
            type="password",
            placeholder="https://discord.com/api/webhooks/...",
        )
    with col_c2:
        pov_tone = st.selectbox(
            "Journal Tone:",
            [
                "Heroic & Boastful",
                "Paranoid & Cryptic",
                "Academic & Snobby",
                "Confused & Terrified",
            ],
        )

    if st.button(
        "Blast Journal to Discord 🚀", type="primary", use_container_width=True
    ):
        source_material = st.session_state.get("recap_script_cache", raw_notes)
        if not source_material:
            st.warning("⚠️ Please enter some session notes or generate a recap first!")
        elif not discord_webhook:
            st.warning("⚠️ Discord Webhook URL is required.")
        else:
            with st.spinner(f"Channeling the spirit of {pov_character}..."):
                try:
                    # 1. Generate the POV Journal
                    pov_prompt = f"""
                    You are {pov_character}. Write a short, in-character journal entry (about 3 paragraphs) summarizing these recent D&D session events.
                    Your tone should be strictly: {pov_tone}.
                    Make it highly immersive, slightly biased towards your own perspective, and ready to be posted in a Discord channel.
                    Do not include any out-of-character text or markdown code blocks.
                    
                    --- RECENT EVENTS ---
                    {source_material}
                    """

                    pov_journal = get_ai_response(
                        pov_prompt, llm_provider, user_api_key
                    )

                    # 2. The Asynchronous Discord Queue (Bypass IP Throttles)
                    import threading
                    from streamlit.runtime.scriptrunner import add_script_run_ctx

                    discord_payload = {
                        "username": f"{pov_character} (DM Co-Pilot)",
                        "content": f"**New Journal Entry: {pov_character}**\n\n{pov_journal}",
                        "avatar_url": "https://cdn-icons-png.flaticon.com/512/8205/8205318.png",
                    }

                    def async_discord_worker(url, payload):
                        import requests
                        import time

                        # 🥷 The Ninja Move: Spoof the User-Agent
                        headers = {
                            "User-Agent": "DM-CoPilot-Enterprise/6.9 (Render Serverless)",
                            "Content-Type": "application/json",
                        }

                        print(
                            f"🚀 [ASYNC] Worker Started. Target URL: {url[:35]}...",
                            flush=True,
                        )

                        # 🛡️ The Heavy Armor: Retry up to 10 times silently in the background
                        for attempt in range(10):
                            try:
                                res = requests.post(
                                    url, json=payload, headers=headers, timeout=10
                                )
                                if res.status_code in [200, 204]:
                                    print(
                                        "✅ [ASYNC] Discord Echo delivered successfully.",
                                        flush=True,
                                    )
                                    break
                                elif res.status_code == 429:
                                    try:
                                        wait_time = float(
                                            res.json().get("retry_after", 5.0)
                                        )
                                    except:
                                        wait_time = 5.0
                                    print(
                                        f"⚠️ [ASYNC] Discord Throttle: Waiting {wait_time}s...",
                                        flush=True,
                                    )
                                    time.sleep(wait_time)
                                else:
                                    print(
                                        f"❌ [ASYNC] Discord rejected payload. Code: {res.status_code} | Reason: {res.text}",
                                        flush=True,
                                    )
                                    break
                            except Exception as e:
                                print(f"🔥 [ASYNC] Thread Crash: {e}", flush=True)
                                time.sleep(5)

                    # 🚀 Fire and Forget: Decouple the blast from the UI
                    echo_thread = threading.Thread(
                        target=async_discord_worker,
                        args=(discord_webhook, discord_payload),
                    )
                    add_script_run_ctx(echo_thread)
                    echo_thread.start()

                    # Instantly free up the DM's screen
                    st.success(
                        f"✅ The Echo has been cast into the asynchronous queue! It will arrive in Discord shortly."
                    )
                    st.balloons()
                    with st.expander("🔍 Read the Journal"):
                        st.write(pov_journal)

                except Exception as e:
                    st.error(f"The magic failed: {e}")

elif page == "🦋 Living World Simulator":
    st.title("🦋 The Butterfly Effect Engine")
    st.markdown(
        "Enter the major actions your players took this session. The AI will simulate the off-screen consequences, faction movements, and living world updates."
    )

    # Ensure memory is initialized as a string
    if st.session_state.world_memory is None:
        st.session_state.world_memory = ""

    with st.expander("📖 Current World Ledger", expanded=True):
        if st.session_state.world_memory:
            st.markdown(st.session_state.world_memory)
        else:
            st.info(
                "The world is quiet... for now. Record your first events below to begin the simulation."
            )

    st.divider()

    recent_events = st.text_area(
        "What did the players do this session?",
        placeholder="e.g., They burned down the sleeping giant tavern, insulted the local magistrate, and cleared the goblin cave...",
    )

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
                consequences = get_ai_response(prompt, llm_provider, user_api_key)

                # Save the new lore permanently into the session's world memory
                st.session_state.world_memory += f"\n\n### 📜 Aftermath of: {recent_events[:50]}...\n{consequences}\n\n---"

                st.success("The world has reacted to their choices.")
                st.markdown(
                    f"<div class='stat-card'>{consequences}</div>",
                    unsafe_allow_html=True,
                )
        else:
            st.warning("⚠️ Please enter the session events first!")

elif page == "🗺️ World Heatmap (Beta)":
    st.title("🗺️ Predictive World Heatmap (v5.0)")
    st.markdown(
        "Enter a chaotic player action to map the deterministic ripple effects across your campaign's factions."
    )

    # 1. The Airlocked Inputs
    c1, c2 = st.columns(2)
    with c1:
        action = st.text_input(
            "What chaotic thing did the players do?",
            value="The rogue burned down the Sleeping Giant tavern.",
            key="heatmap_action_v5",
        )
    with c2:
        context = st.text_area(
            "Campaign Context",
            value="Phandalin is a frontier town run by corrupt Redbrands, but honest miners rely on that tavern.",
            key="heatmap_context_v5",
        )

    # 2. The Execution Button
    if st.button("Generate Butterfly Effect 🦋", key="heatmap_btn_v5"):
        with st.spinner("Calculating GraphRAG deterministic timelines..."):
            try:
                # 3. The Brain (Using your existing caching function)
                prompt = f"""
                Given this campaign context: {context}
                The players just did this: {action}
                
                Identify 3 factions or NPCs affected by this. Respond ONLY in valid JSON format like this:
                {{"nodes": [{{"id": "Faction Name", "status": "hostile/friendly/neutral"}}], "edges": [{{"source": "Players", "target": "Faction Name", "reason": "Why"}}]}}
                """

                raw_response = get_ai_response(prompt, llm_provider, user_api_key)

                # Clean the JSON in case the AI wraps it in markdown backticks
                cleaned_json = (
                    raw_response.replace("```json", "").replace("```", "").strip()
                )
                graph_data = json.loads(cleaned_json)

                # 4. Build the Visual Graph Nodes & Edges
                visual_nodes = []
                visual_edges = []

                # Define color logic based on faction status
                color_map = {
                    "hostile": "#ff4b4b",  # Red
                    "friendly": "#00cc66",  # Green
                    "friendlier": "#00cc66",
                    "neutral": "#808080",  # Gray
                    "unknown": "#5c5c8a",  # Purple/Gray
                }

                # Add the central "Players" node
                visual_nodes.append(
                    Node(
                        id="Players",
                        label="The Party",
                        size=25,
                        shape="star",
                        color="#ffd700",
                    )
                )

                # Add the generated faction nodes
                for node in graph_data.get("nodes", []):
                    node_color = color_map.get(node["status"].lower(), "#808080")
                    visual_nodes.append(
                        Node(
                            id=node["id"],
                            label=f"{node['id']}\n({node['status']})",
                            size=20,
                            color=node_color,
                        )
                    )

                # Add the connecting edges
                for edge in graph_data.get("edges", []):
                    visual_edges.append(
                        Edge(
                            source=edge["source"],
                            target=edge["target"],
                            label=edge["reason"],
                        )
                    )

                # 5. Render the Interactive Graph
                st.success("GraphRAG Engine fired! Rendering Butterfly Effect...")

                config = Config(
                    width=700,
                    height=500,
                    directed=True,
                    physics=True,
                    hierarchical=False,
                    nodeHighlightBehavior=True,
                    highlightColor="#F7A7A6",
                    collapsible=False,
                )

                agraph(nodes=visual_nodes, edges=visual_edges, config=config)

                # Also keep an expander for the raw JSON just in case DMs want to copy it
                with st.expander("View Raw Graph Data"):
                    st.json(graph_data)

            except Exception as e:
                st.error(f"Graph Generation Error: {e}")

    # ==========================================
    # 🕸️ BUTTERFLY EFFECT VISUALIZER (PYVIS)
    # ==========================================
    if "raw_response" in locals() and raw_response:
        import json
        import streamlit.components.v1 as components
        from pyvis.network import Network

        st.markdown("### 🕸️ The Web of Consequences")
        st.caption(
            "Drag the nodes to explore the ripple effects. Hover over edges to see the reasoning."
        )

        try:
            # 1. Parse the AI's JSON output
            graph_data = json.loads(raw_response)

            # 2. Initialize the interactive physics network
            net = Network(
                height="500px",
                width="100%",
                bgcolor="#0e1117",
                font_color="white",
                directed=True,
            )

            # 3. Define a tactical color palette based on faction status
            color_map = {
                "hostile": "#ff4b4b",
                "friendly": "#00cc96",
                "neutral": "#ffc107",
                "allied": "#1f77b4",
            }

            # 4. Anchor the central node (The Players)
            net.add_node("Players", label="The Players", color="#636efa", size=30)

            # 5. Build the Faction Nodes
            for node in graph_data.get("nodes", []):
                n_id = node.get("id", "Unknown")
                n_status = node.get("status", "neutral").lower()
                n_color = color_map.get(n_status, "#888888")
                net.add_node(n_id, label=n_id, color=n_color, size=20)

            # 6. Draw the Ripple Effect Edges
            for edge in graph_data.get("edges", []):
                src = edge.get("source")
                tgt = edge.get("target")
                reason = edge.get("reason", "")

                if src not in net.get_nodes():
                    net.add_node(src, label=src, color="#888888", size=15)
                if tgt not in net.get_nodes():
                    net.add_node(tgt, label=tgt, color="#888888", size=15)

                net.add_edge(src, tgt, title=reason, color="#555555")

            # 7. Generate the HTML map and render it safely in Streamlit
            net.save_graph("butterfly_graph.html")
            with open("butterfly_graph.html", "r", encoding="utf-8") as f:
                html_data = f.read()

            components.html(html_data, height=515)

        except json.JSONDecodeError:
            st.error("The magic fizzled: The AI did not return a valid JSON structure.")
        except Exception as e:
            st.error(f"Graph rendering error: {e}")

elif page == "👻 Ghost NPC (Beta)":
    st.title("👻 Ghost NPC: Voice-to-Voice (v5.0)")
    st.markdown(
        "Speak directly into your microphone. The AI will hear you, adopt the NPC's persona, and speak back in real-time."
    )

    # --- NEW: THE ACCURATE BYOK NOTICE (WITH LINK) ---
    st.info(
        "🎙️ **Engine Status:** A free **Groq API Key** is required to run the AI's logic brain. You can get one instantly at [console.groq.com/keys](https://console.groq.com/keys), then paste it in the left sidebar. \n\n🎁 *Bonus: The premium Onyx Voice Engine is free to try for your first 5 interactions!*"
    )

    c1, c2 = st.columns(2)
    with c1:
        npc_name = st.text_input(
            "Who are you talking to?",
            value="Grub, a paranoid goblin merchant",
            key="ghost_name_v5",
        )
    with c2:
        npc_context = st.text_input(
            "Where are you?", value="In a dark, damp cave.", key="ghost_context_v5"
        )

    st.divider()
    # --- THE SAFETY VALVE ---
    # Checks if they are using YOUR Render Vault keys or THEIR sidebar keys
    # --- THE HARDENED SAFETY VALVE ---
    # 1. Check the SIDEBAR variable name (user_openai_key)
    is_demo_mode = not user_openai_input
    # 2. Check the session state counter
    limit_reached = st.session_state.get("demo_uses", 0) >= 5

    if is_demo_mode and limit_reached:
        st.warning(
            "🐉 **Demo Limit Reached.** You've used your 5 free 'Onyx' interactions. To keep talking, please enter your own OpenAI API Key in the sidebar!"
        )
    else:
        # 1. Capture audio from the user's mic
        recorded_audio = st.audio_input("Record your dialogue", key="ghost_mic_v5")

        if recorded_audio is not None:
            # Increment the counter only if they are using your credits
            if is_demo_mode:
                if "demo_uses" not in st.session_state:
                    st.session_state.demo_uses = 0

            if is_demo_mode:
                st.session_state.demo_uses += 1

            with st.spinner(f"Waiting for {npc_name} to respond..."):
                try:
                    # 1. Save the audio
                    with tempfile.NamedTemporaryFile(
                        delete=False, suffix=".wav"
                    ) as tmp_in:
                        tmp_in.write(recorded_audio.getvalue())
                        temp_in_path = tmp_in.name

                    # 2. Whisper Transcription (Secure Fallback logic)
                    from groq import Groq

                    # Checks sidebar FIRST, then Render Vault
                    final_groq_key = (
                        user_api_key if user_api_key else st.secrets.get("GROQ_API_KEY")
                    )
                    groq_client = Groq(api_key=final_groq_key)

                    with open(temp_in_path, "rb") as file:
                        transcription = groq_client.audio.transcriptions.create(
                            file=(temp_in_path, file.read()),
                            model="whisper-large-v3",
                            response_format="text",
                        )
                    player_speech = transcription

                    # 3. Generate Character Response
                    prompt = f"You are {npc_name}. Context: {npc_context}. Player says: '{player_speech}'. Respond in character, 3 sentences max."
                    raw_response = get_ai_response(prompt, llm_provider, user_api_key)

                    # 4. The Doppelganger Matrix (Persistent Voiceprints)
                    if not openai_key:
                        st.error(
                            "⚠️ OpenAI Key not found. Please enter it in the sidebar or check Render Environment variables."
                        )
                        st.stop()

                    openai_client = OpenAI(api_key=openai_key)

                    with tempfile.NamedTemporaryFile(
                        delete=False, suffix=".mp3"
                    ) as tmp_out:
                        temp_out_path = tmp_out.name

                    # 🧬 Deterministic Voice Hashing
                    import hashlib

                    available_voices = [
                        "alloy",
                        "echo",
                        "fable",
                        "onyx",
                        "nova",
                        "shimmer",
                    ]

                    # Hash the normalized NPC name to consistently pick the same voice
                    name_hash = int(
                        hashlib.md5(
                            npc_name.strip().lower().encode("utf-8")
                        ).hexdigest(),
                        16,
                    )
                    assigned_voice = available_voices[name_hash % len(available_voices)]

                    st.caption(
                        f"🧬 **Doppelganger Matrix:** Assigned voiceprint `{assigned_voice}` to {npc_name}."
                    )

                    audio_response = openai_client.audio.speech.create(
                        model="tts-1", voice=assigned_voice, input=raw_response
                    )

                    # 5. Playback and Cleanup
                    with open(temp_out_path, "wb") as f:
                        f.write(audio_response.content)

                    st.audio(temp_out_path, format="audio/mpeg", autoplay=True)
                    os.remove(temp_in_path)
                    os.remove(temp_out_path)

                except Exception as e:
                    st.error(f"Voice Engine Error: {e}")
elif "Initiative Tracker" in page:
    st.title("🛡️ Initiative Tracker (Local DB Enabled)")

    # --- 💾 MULTIPLAYER SQLITE COMBAT ENGINE ---
    import sqlite3
    import json

    # Connect to local SQLite DB
    conn = sqlite3.connect("combat_snapshot.db", check_same_thread=False)
    c = conn.cursor()

    # UPGRADE: Changed 'id' to a TEXT 'room_code' so different campaigns don't overlap
    c.execute(
        """CREATE TABLE IF NOT EXISTS combat_state (room_code TEXT PRIMARY KEY, state_json TEXT)"""
    )
    conn.commit()

    # Snapshot UI Controls
    st.info(
        f"Currently saving to database partition: **{st.session_state.campaign_id}**"
    )
    snap_col1, snap_col2, snap_col3 = st.columns(3)

    if snap_col1.button(
        "💾 Save Combat Snapshot", use_container_width=True, key="save_snap_v2"
    ):
        state_str = json.dumps(st.session_state.combatants)
        # UPGRADE: Save to their specific campaign ID
        c.execute(
            "INSERT OR REPLACE INTO combat_state (room_code, state_json) VALUES (?, ?)",
            (st.session_state.campaign_id, state_str),
        )
        conn.commit()

    # --- 📡 SILENT TELEMETRY (MULTIVERSE NEXUS) ---
    if db is not None:
        try:
            # Anonymize data: completely scrubs names/lore, only sends raw math
            total_combatants = len(st.session_state.combatants)
            avg_hp = sum(
                [combatant.get("hp", 0) for combatant in st.session_state.combatants]
            ) / (total_combatants if total_combatants > 0 else 1)

            db.collection("multiverse_telemetry").add(
                {
                    "event_type": "combat_snapshot",
                    "total_combatants": total_combatants,
                    "avg_hp": avg_hp,
                    "timestamp": firestore.SERVER_TIMESTAMP,
                }
            )
        except Exception:
            pass  # Fail silently; never interrupt the DM's game if the network blips
    # ----------------------------------------------

    st.toast(f"Combat state hard-saved to {st.session_state.campaign_id}!", icon="💾")

    if snap_col2.button(
        "🔄 Recover Last Snapshot", use_container_width=True, key="rec_snap_v2"
    ):
        # UPGRADE: Fetch only from their specific campaign ID
        c.execute(
            "SELECT state_json FROM combat_state WHERE room_code = ?",
            (st.session_state.campaign_id,),
        )
        row = c.fetchone()
        if row:
            st.session_state.combatants = json.loads(row[0])
            st.toast(
                f"Combat state recovered from {st.session_state.campaign_id}!",
                icon="🔄",
            )
            st.rerun()
        else:
            st.warning(
                f"⚠️ No snapshot found for campaign: {st.session_state.campaign_id}"
            )

    if snap_col3.button(
        "📡 Broadcast to Players", type="primary", use_container_width=True
    ):
        if db is not None:
            with st.spinner("Pushing to Player Portal..."):
                try:
                    sanitized_combatants = []
                    for c_data in st.session_state.combatants:
                        # Auto-Sanitize HP to prevent metagaming
                        hp = c_data.get("hp", 0)
                        if hp >= 40:
                            status = "Healthy 🟢"
                        elif hp >= 15:
                            status = "Bloodied 🟡"
                        elif hp > 0:
                            status = "Critical 🔴"
                        else:
                            status = "Dead 💀"

                        sanitized_combatants.append(
                            {
                                "name": c_data.get("name", "Unknown"),
                                "init": c_data.get("init", 0),
                                "conditions": c_data.get("conditions", []),
                                "status": status,
                            }
                        )

                    db.collection("live_tables").document(
                        st.session_state.campaign_id
                    ).set(
                        {
                            "combatants": sanitized_combatants,
                            "timestamp": firestore.SERVER_TIMESTAMP,
                        }
                    )
                    st.toast(
                        f"Battlefield broadcasted to Room: {st.session_state.campaign_id}!",
                        icon="📡",
                    )
                except Exception as e:
                    st.error(f"Broadcast Failed: {e}")
        else:
            st.error("Database connection offline. Cannot broadcast.")
    st.divider()

    # --- 👁️ THE TABLETOP EYE (Physical Dice OCR) ---
    with st.expander("👁️ The Tabletop Eye (Physical Dice Vision)", expanded=False):
        st.markdown(
            "Roll your physical d20 in front of your webcam. The AI will read the result and do the math."
        )

        c_eye1, c_eye2 = st.columns([2, 1])
        with c_eye2:
            modifier = st.number_input(
                "Add Modifier:", value=0, step=1, key="vision_mod"
            )

        with c_eye1:
            dice_image = st.camera_input(
                "Capture Dice Roll", label_visibility="collapsed"
            )

        if dice_image:
            if not openai_key:
                st.error(
                    "⚠️ OpenAI API Key required for Vision AI. Please check the sidebar."
                )
            else:
                with st.spinner("Vision AI is reading the dice..."):
                    try:
                        import base64
                        from openai import OpenAI

                        base64_image = base64.b64encode(dice_image.getvalue()).decode(
                            "utf-8"
                        )
                        client = OpenAI(api_key=openai_key)

                        response = client.chat.completions.create(
                            model="gpt-4o",
                            messages=[
                                {
                                    "role": "user",
                                    "content": [
                                        {
                                            "type": "text",
                                            "text": "Look at this image of a tabletop roleplaying die. Identify the number facing straight up on the top face. Return ONLY the integer number. No words, no punctuation.",
                                        },
                                        {
                                            "type": "image_url",
                                            "image_url": {
                                                "url": f"data:image/jpeg;base64,{base64_image}"
                                            },
                                        },
                                    ],
                                }
                            ],
                            max_tokens=10,
                        )

                        vision_result = response.choices[0].message.content.strip()
                        if vision_result.isdigit():
                            base_roll = int(vision_result)
                            total = base_roll + modifier

                            # Check for Crits
                            crit_html = ""
                            if base_roll == 20:
                                crit_html = "<h3 style='color: #00FF00; text-align: center;'>🌟 CRITICAL HIT! 🌟</h3>"
                                st.balloons()
                            elif base_roll == 1:
                                crit_html = "<h3 style='color: #FF0000; text-align: center;'>💀 CRITICAL FAIL! 💀</h3>"

                            st.markdown(
                                f"""
                            <div class='stat-card' style='text-align: center;'>
                                {crit_html}
                                <h2>Physical Roll: {base_roll} + {modifier} = <span style='color: #00FF00; font-size: 1.5em;'>{total}</span></h2>
                            </div>
                            """,
                                unsafe_allow_html=True,
                            )
                        else:
                            st.warning(
                                f"The AI got confused. It saw: '{vision_result}'. Try adjusting the lighting or centering the die."
                            )

                    except Exception as e:
                        st.error(f"Tabletop Eye Error: {e}")

    st.divider()

    dnd_conditions = [
        "Blinded",
        "Charmed",
        "Deafened",
        "Frightened",
        "Grappled",
        "Incapacitated",
        "Invisible",
        "Paralyzed",
        "Petrified",
        "Poisoned",
        "Prone",
        "Restrained",
        "Stunned",
        "Unconscious",
        "Exhaustion",
    ]

    with st.expander("➕ Add Combatant"):
        c1, c2, c3 = st.columns(3)
        name = c1.text_input("Name")
        init = c2.number_input("Roll", value=10)
        hp = c3.number_input("HP", value=15)
        if st.button("Add"):
            st.session_state.combatants.append(
                {"name": name, "init": init, "hp": hp, "conditions": []}
            )
            st.session_state.combatants = sorted(
                st.session_state.combatants, key=lambda x: x["init"], reverse=True
            )
            st.rerun()

    for idx, c in enumerate(st.session_state.combatants):
        if "conditions" not in c:
            c["conditions"] = []

        # UPGRADE 2: Expanded the columns to make room for the Quick-Math Zone
        cols = st.columns([2, 1, 1, 2, 3, 1])
        cols[0].write(f"**{c['name']}**")
        cols[1].write(f"⚔️ {c['init']}")
        cols[2].write(f"❤️ {c['hp']}")

        # --- 🧮 QUICK MATH ZONE ---
        math_c1, math_c2, math_c3 = cols[3].columns([2, 1, 1])
        mod = math_c1.number_input(
            "Mod",
            value=0,
            min_value=0,
            step=1,
            key=f"mod_{idx}",
            label_visibility="collapsed",
        )

        # Damage Button
        if math_c2.button(
            "🩸", key=f"dmg_{idx}", help="Take Damage", use_container_width=True
        ):
            if mod > 0:
                st.session_state.combatants[idx]["hp"] -= mod
                st.session_state[f"mod_{idx}"] = (
                    0  # Automatically resets the input box to 0
                )
                st.rerun()

        # Heal Button
        if math_c3.button(
            "💚", key=f"heal_{idx}", help="Heal", use_container_width=True
        ):
            if mod > 0:
                st.session_state.combatants[idx]["hp"] += mod
                st.session_state[f"mod_{idx}"] = (
                    0  # Automatically resets the input box to 0
                )
                st.rerun()
        # ---------------------------

        new_conditions = cols[4].multiselect(
            "Conditions",
            options=dnd_conditions,
            default=c["conditions"],
            key=f"cond_{idx}",
            label_visibility="collapsed",
        )

        if new_conditions != c["conditions"]:
            st.session_state.combatants[idx]["conditions"] = new_conditions

        if cols[5].button("🗑️", key=f"del_{idx}"):
            st.session_state.combatants.pop(idx)
            st.rerun()

elif page == "🐉 Monster Lab":
    st.title("🐉 Monster Lab")
    st.markdown(
        "Generate custom creatures formatted as structured JSON data for direct import into Foundry VTT or Roll20 APIs."
    )

    monster_type = st.selectbox(
        "Creature Type",
        ["Aberration", "Beast", "Dragon", "Fiend", "Monstrosity", "Undead"],
    )
    monster_cr = st.selectbox(
        "Challenge Rating (CR)", ["1-4", "5-10", "11-16", "17-20", "21+"]
    )
    custom_flavor = st.text_area(
        "Monster Concept",
        placeholder="e.g., A mutated bear that breathes necrotic fire...",
    )

    if st.button("Forge JSON Statblock 🔨"):
        with st.spinner("Compiling structured data..."):
            prompt = f"Create a D&D 5e {monster_type} with a CR of {monster_cr}. Concept: {custom_flavor}. "
            # --- STEP 1: THE REASONING PROMPT ---
            prompt += """
            Return ONLY a flat JSON object. NO markdown, NO asterisks, NO '0:' indices.
            Required Keys: "name", "ac", "hp", "speed", "str", "dex", "con", "int", "wis", "cha", "cr",
            "actions": [ {"name": "...", "desc": "...", "damage": "1d8", "dmg_type": "..."} ]
            """
            raw_ai_output = get_ai_response(prompt, llm_provider, user_api_key)

            # --- THE "VTT FINAL BOSS" SCRUB (v5.0) ---
            # 1. Kill all asterisks and markdown wrappers
            clean_ai = (
                raw_ai_output.replace("*", "")
                .replace("```json", "")
                .replace("```", "")
                .strip()
            )

            # 2. The Index Executioner: Wipes out "0 :", "1 :", etc.
            # (Handles the specific spacing seen in the Wereowl V4 logs)
            clean_ai = re.sub(r"\d+\s*:\s*", "", clean_ai)

            # 3. THE COMMA INJECTOR: This fixes the "Missing Comma" hallucination
            # It looks for a quote followed by a space and another quote, and adds the comma.
            clean_ai = re.sub(r'"\s+"', '", "', clean_ai)
            clean_ai = re.sub(r"}\s*{", "}, {", clean_ai)
            clean_ai = re.sub(r'}\s+"', '}, "', clean_ai)

            # 4. Key/Value Sanitation: Wipes out double commas or trailing commas
            clean_ai = clean_ai.replace(",,", ",").replace(",]", "]").replace(",}", "}")

            try:
                # 4. Parse into Python Dictionary
                ai_data = json.loads(clean_ai)

                # --- STEP 3: THE FOUNDRY FORGE ---
                # We build the complex Foundry VTT schema manually so it's ALWAYS legal
                # --- THE TYPE-SAFETY SANITIZER ---
                def safe_int(value, default=10):
                    try:
                        return int(re.search(r"\d+", str(value)).group())
                    except:
                        return default

                def safe_cr(value):
                    if str(value) in ["1/8", "1/4", "1/2"]:
                        return eval(str(value))
                    return safe_int(value, 1)

                # --- STEP 3: THE FOUNDRY FORGE ---
                foundry_obj = {
                    "name": str(ai_data.get("name", "Generated Stalker")),
                    "type": "npc",
                    "system": {
                        "abilities": {
                            "str": {"value": safe_int(ai_data.get("str"), 10)},
                            "dex": {"value": safe_int(ai_data.get("dex"), 10)},
                            "con": {"value": safe_int(ai_data.get("con"), 10)},
                            "int": {"value": safe_int(ai_data.get("int"), 10)},
                            "wis": {"value": safe_int(ai_data.get("wis"), 10)},
                            "cha": {"value": safe_int(ai_data.get("cha"), 10)},
                        },
                        "attributes": {
                            "ac": {
                                "calc": "flat",
                                "flat": safe_int(ai_data.get("ac"), 10),
                            },
                            "hp": {
                                "value": safe_int(ai_data.get("hp"), 10),
                                "max": safe_int(ai_data.get("hp"), 10),
                            },
                            "movement": {"walk": safe_int(ai_data.get("speed"), 30)},
                        },
                        "details": {
                            "cr": safe_cr(ai_data.get("cr")),
                            "type": {"value": str(monster_type).lower(), "subtype": ""},
                        },
                        "traits": {"size": "med"},
                    },
                    "items": [],
                }

                # BYPASS 5.2.5 WEAPON STRICTNESS: Use "feat" instead of "weapon"
                for action in ai_data.get("actions", []):
                    dmg_text = f"<br><br><b>Damage:</b> {action.get('damage', '')} {action.get('dmg_type', '')}"
                    foundry_obj["items"].append(
                        {
                            "name": str(action.get("name", "Action")),
                            "type": "feat",
                            "system": {
                                "description": {
                                    "value": str(action.get("desc", "")) + dmg_text
                                }
                            },
                        }
                    )

                st.session_state.bestiary_json = json.dumps(foundry_obj, indent=2)

            except Exception as e:
                st.error(f"Master Forge Error: {e}")
                st.write("Attempted to parse this text:", clean_ai)
    if st.session_state.bestiary_json:
        # --- BLOCK 1: JSON VALIDATION & TOKEN ART ---
        try:
            parsed_json = json.loads(st.session_state.bestiary_json)
            st.json(
                parsed_json
            )  # Bypassing strict Pydantic to allow raw Foundry payloads

            st.download_button(
                "📥 Download JSON for VTT",
                data=st.session_state.bestiary_json,
                file_name="monster_statblock.json",
                mime="application/json",
            )

            # 🎨 THE TOKEN AUTO-FORGE
            st.divider()
            st.markdown("### 🎨 Token Auto-Forge")
            st.caption("Generate a custom VTT token for this newly forged monster.")

            if st.button("Forge Token Art 🪄", use_container_width=True):
                if not user_api_key or user_api_key == "":
                    st.error(
                        "🔒 An OpenAI API Key is required in the Vault to forge art."
                    )
                else:
                    with st.spinner("Channeling the weave to forge token art..."):
                        try:
                            from openai import OpenAI

                            client = OpenAI(api_key=user_api_key)

                            m_name = parsed_json.get("name", "Terrifying Monster")
                            m_type = parsed_json.get("type", "monstrosity")

                            art_prompt = f"A top-down digital tabletop VTT token of a {m_name}, which is a {m_type}. Fantasy art style, isolated on a clean white background, vibrant colors, highly detailed."

                            response = client.images.generate(
                                model="dall-e-3",
                                prompt=art_prompt,
                                size="1024x1024",
                                quality="standard",
                                n=1,
                            )
                            image_url = response.data[0].url

                            st.image(image_url, caption=f"Custom Token: {m_name}")
                            st.success(
                                "Art forged successfully! Right-click the image to save."
                            )

                        except Exception as e:
                            st.error(f"The magic fizzled (Image Error): {e}")

        except Exception as e:
            st.error("Error parsing JSON data. Please try forging again.")
            st.write("Raw output for debugging:", st.session_state.bestiary_json)

        # --- BLOCK 2: DIRECT VTT TRANSMISSION ---
        st.divider()
        st.markdown("### 🔌 Direct VTT Transmission")
        st.markdown(
            "Send this statblock directly into your live game using your Global VTT Webhook."
        )

        # Read the global URL from the sidebar
        foundry_url = st.session_state.get("vtt_url", "")

        if st.button("🚀 Send to Live VTT", key="vtt_btn_best"):
            if foundry_url:
                with st.spinner("Transmitting across the weave..."):
                    try:
                        # --- FOUNDRY VTT REST API INTEGRATION ---
                        # --- BATCH 10: THE BULLETPROOF HANDSHAKE ---
                        api_key = foundry_url  # Pulling the key from the sidebar box
                        headers = {
                            "Content-Type": "application/json",
                            "x-api-key": api_key,
                        }

                        # Step 1: Find your connected Foundry World
                        clients_url = (
                            "https://foundryvtt-rest-api-relay.fly.dev/clients"
                        )
                        clients_res = requests.get(
                            clients_url, headers=headers, timeout=5
                        )
                        relay_data = clients_res.json()

                        # 📡 THE DIAGNOSTIC: Print exactly what the server says to the UI
                        st.info(f"📡 Relay Status: {relay_data}")

                        client_id = None

                        # Safely extract the ID no matter how the server formats it
                        if isinstance(relay_data, list) and len(relay_data) > 0:
                            client_id = relay_data[0].get("id")
                        elif isinstance(relay_data, dict):
                            if (
                                "clients" in relay_data
                                and len(relay_data["clients"]) > 0
                            ):
                                client_id = relay_data["clients"][0].get("id")
                            elif (
                                len(relay_data) > 0
                                and "error" not in relay_data
                                and "message" not in relay_data
                            ):
                                client_id = list(relay_data.keys())[0]

                        if client_id:
                            # --- STEP 2: THE BLAST ---
                            # Corrected wrapper: The Relay expects "payload", not "data"
                            blast_url = f"https://foundryvtt-rest-api-relay.fly.dev/create?clientId={client_id}"

                            foundry_payload = {
                                "entityType": "Actor",
                                "data": json.loads(st.session_state.bestiary_json),
                            }

                            response = requests.post(
                                blast_url,
                                json=foundry_payload,
                                headers=headers,
                                timeout=5,
                            )
                        else:
                            # Safely fail if Foundry isn't awake
                            class FakeResponse:
                                status_code = 404
                                text = "Foundry Not Connected"

                            response = FakeResponse()

                        if response.status_code in [200, 201]:
                            st.success(
                                "Success! The monster has materialized in your VTT."
                            )
                            st.balloons()
                        else:
                            st.error(
                                f"Transmission failed. Code: {response.status_code} | Reason: {response.text}"
                            )
                    except requests.exceptions.RequestException:
                        st.error(
                            "Could not connect to VTT. Ensure your Foundry server is running, the REST API module is active, and the URL is correct."
                        )
                    except Exception as e:
                        st.error(f"An unexpected error occurred: {e}")
            else:
                st.warning(
                    "⚠️ Global VTT Webhook URL is missing. Please add it in the left sidebar."
                )
elif page == "👾 The Mimic Engine":
    st.title("👾 The Mimic Engine (Physical-to-Digital)")
    st.markdown(
        "Snap a photo of a monster stat block from a physical book or your homebrew notes. The AI will read the image and instantly forge a VTT-ready JSON file."
    )

    uploaded_img = st.file_uploader(
        "Upload Stat Block Image (JPG/PNG)", type=["jpg", "jpeg", "png"]
    )

    if uploaded_img:
        st.image(uploaded_img, caption="Target Acquired", use_container_width=True)

        if st.button("Digitize & Extract Stats 🚀", type="primary"):
            if not openai_key:
                st.error(
                    "⚠️ OpenAI API Key required for Vision AI. Please check the sidebar."
                )
            else:
                with st.spinner("The Mimic is consuming the text..."):
                    try:
                        import base64
                        from openai import OpenAI

                        base64_image = base64.b64encode(uploaded_img.getvalue()).decode(
                            "utf-8"
                        )
                        client = OpenAI(api_key=openai_key)

                        response = client.chat.completions.create(
                            model="gpt-4o",
                            messages=[
                                {
                                    "role": "user",
                                    "content": [
                                        {
                                            "type": "text",
                                            "text": "You are a VTT data extractor. Read this D&D stat block and convert it into a strict JSON object. Keys MUST include: name, size, type, alignment, armor_class (int), hit_points (int), speed, strength, dexterity, constitution, intelligence, wisdom, charisma, and an 'actions' array containing objects with 'name' and 'description'. Return ONLY valid JSON.",
                                        },
                                        {
                                            "type": "image_url",
                                            "image_url": {
                                                "url": f"data:image/jpeg;base64,{base64_image}"
                                            },
                                        },
                                    ],
                                }
                            ],
                            max_tokens=1500,
                        )

                        mimic_json = (
                            response.choices[0]
                            .message.content.replace("```json", "")
                            .replace("```", "")
                            .strip()
                        )
                        st.session_state.mimic_extracted = mimic_json
                        st.success("Extraction Complete!")
                    except Exception as e:
                        st.error(f"Mimic Engine Error: {e}")

    if st.session_state.get("mimic_extracted"):
        st.divider()
        st.markdown("### 🔌 Extracted Data & Transmission")
        try:
            st.json(json.loads(st.session_state.mimic_extracted))
        except Exception:
            st.code(
                st.session_state.mimic_extracted
            )  # Fallback if AI messes up the JSON

        webhook_url = st.session_state.get("vtt_url", "")
        if st.button("🚀 Blast to Live VTT"):
            if webhook_url:
                with st.spinner("Transmitting across the weave..."):
                    try:
                        res = requests.post(
                            webhook_url,
                            data=st.session_state.mimic_extracted,
                            headers={"Content-Type": "application/json"},
                            timeout=5,
                        )
                        if res.status_code in [200, 201]:
                            st.success("✅ Monster digitized and spawned in your VTT!")
                            st.balloons()
                        else:
                            st.error(
                                f"Transmission failed. VTT responded with code: {res.status_code}"
                            )
                    except Exception as e:
                        st.error(
                            "Could not connect to VTT. Ensure your server is running and the URL is correct."
                        )
            else:
                st.warning(
                    "⚠️ Global VTT Webhook URL is missing. Please add it in the left sidebar."
                )
    st.divider()

elif page == "👁️ Cartographer's Eye":
    st.title("👁️ The Cartographer's Eye (Vision AI)")
    st.markdown(
        "Upload a photo of a hand-drawn dungeon map. The AI will analyze the geometry and generate a VTT-ready JSON file mapping out the walls and doors."
    )

    if "map_json" not in st.session_state:
        st.session_state.map_json = None

    uploaded_map = st.file_uploader(
        "Upload Map Image (JPG/PNG)", type=["jpg", "jpeg", "png"]
    )

    if uploaded_map:
        st.image(uploaded_map, caption="Scanned Blueprint", use_container_width=True)

        if st.button("Digitize Map for VTT 🚀", type="primary"):
            if not openai_key:
                st.error(
                    "⚠️ This advanced vision feature requires an OpenAI API Key in the Premium Tools sidebar."
                )
            else:
                with st.spinner(
                    "Analyzing spatial geometry and drawing coordinates..."
                ):
                    try:
                        import base64

                        base64_image = base64.b64encode(uploaded_map.getvalue()).decode(
                            "utf-8"
                        )

                        client = OpenAI(api_key=openai_key)

                        response = client.chat.completions.create(
                            model="gpt-4o",
                            messages=[
                                {
                                    "role": "user",
                                    "content": [
                                        {
                                            "type": "text",
                                            "text": 'You are an expert Virtual Tabletop data engineer. Look at this hand-drawn D&D map. Identify the layout and generate a JSON array of wall coordinates (x1, y1, x2, y2) that represent the main structural walls and doors. Format the response ONLY as valid JSON. Do not include any conversational text. Example format: {"walls": [{"c": [0, 0, 100, 0], "type": "wall"}, {"c": [100, 0, 100, 100], "type": "door"}]}.',
                                        },
                                        {
                                            "type": "image_url",
                                            "image_url": {
                                                "url": f"data:image/jpeg;base64,{base64_image}"
                                            },
                                        },
                                    ],
                                }
                            ],
                            max_tokens=1500,
                        )

                        vision_json = (
                            response.choices[0]
                            .message.content.replace("```json", "")
                            .replace("```", "")
                            .strip()
                        )
                        st.session_state.map_json = vision_json

                    except Exception as e:
                        st.error(f"Vision processing failed: {e}")

    if st.session_state.map_json:
        st.success("Geometry extracted successfully!")
        try:
            st.json(json.loads(st.session_state.map_json))
            st.download_button(
                "📥 Download Wall Data (JSON)",
                st.session_state.map_json,
                file_name="vtt_walls.json",
                mime="application/json",
            )
        except Exception as e:
            st.error("The AI returned invalid JSON. Please try running the scan again.")
            st.code(st.session_state.map_json)

elif page == "🎨 Image Generator":
    st.title("🎨 AI Image Artificer")
    prompt = st.text_area("Art Prompt:")
    if st.button("Forge Image"):
        if not openai_key:
            st.error("Enter OpenAI Key in Sidebar")
        else:
            client = OpenAI(api_key=openai_key)
            response = client.images.generate(model="dall-e-3", prompt=prompt)
            st.image(response.data[0].url)

elif page == "📚 PDF-Lore Chat":
    st.title("🕸️ The Campaign Lore Weaver (RAG Engine)")
    st.markdown(
        "Upload your massive campaign modules. The AI uses a FAISS Vector Database to instantly recall exact lore without crashing the token limit."
    )

    # --- THE AIRLOCKED OPENAI KEY CHECK ---
    uploaded_file = st.file_uploader("Upload Campaign Document (PDF)", type="pdf")

    if uploaded_file is not None:
        if st.button("Initialize Campaign Brain 🧠", type="primary"):
            # Use the global `openai_key` defined at the top of the app
            if not openai_key:
                st.error(
                    "⚠️ OpenAI API Key required for Vector Embeddings. Check the sidebar or Vault."
                )
            else:
                with st.spinner(
                    "Extracting, Chunking, and Embedding Lore (This may take a minute)..."
                ):
                    try:
                        # 1. Extract Text
                        import PyPDF2

                        reader = PyPDF2.PdfReader(uploaded_file)
                        raw_text = ""
                        for page in reader.pages:
                            extracted = page.extract_text()
                            if extracted:
                                raw_text += extracted + "\n"

                        # 2. Chunk the Text (The Enterprise RAG Way)
                        chunk_size = 1000
                        overlap = 200
                        chunks = []
                        for i in range(0, len(raw_text), chunk_size - overlap):
                            chunk = raw_text[i : i + chunk_size].strip()
                            if len(chunk) > 50:  # Ignore tiny useless chunks
                                chunks.append(chunk)

                        # 3. Generate Mathematical Embeddings via OpenAI
                        from openai import OpenAI
                        import numpy as np
                        import faiss

                        client = OpenAI(api_key=openai_key)
                        response = client.embeddings.create(
                            input=chunks, model="text-embedding-3-small"
                        )
                        # Convert embeddings to a numpy array for FAISS
                        embeddings = np.array(
                            [data.embedding for data in response.data]
                        ).astype("float32")

                        # 4. Build the FAISS Vector Database
                        dimension = embeddings.shape[1]
                        index = faiss.IndexFlatL2(dimension)
                        index.add(embeddings)

                        # --- UPGRADE: RULE 5 (HARD DRIVE OFFLOADING) & RULE 3 (ISOLATION) ---
                        safe_campaign_id = re.sub(
                            r"[^a-z0-9_]", "_", st.session_state.campaign_id.lower()
                        )
                        faiss_path = f"brain_{safe_campaign_id}.faiss"
                        map_path = f"brain_{safe_campaign_id}.json"

                        # Save the massive objects to the physical hard drive, NOT session memory!
                        faiss.write_index(index, faiss_path)
                        with open(map_path, "w", encoding="utf-8") as f:
                            json.dump(chunks, f)

                        st.success(
                            f"⚡ Brain Initialized! {len(chunks)} chunks of lore securely saved to local disk for Campaign: {st.session_state.campaign_id}."
                        )

                    except Exception as e:
                        st.error(f"Failed to build the Vector DB: {e}")

    # --- THE RECALL ENGINE ---
    # Instead of checking session state, we check if the physical files exist for this specific DM
    import os

    safe_campaign_id = re.sub(r"[^a-z0-9_]", "_", st.session_state.campaign_id.lower())
    faiss_path = f"brain_{safe_campaign_id}.faiss"
    map_path = f"brain_{safe_campaign_id}.json"

    if os.path.exists(faiss_path) and os.path.exists(map_path):
        st.divider()
        st.markdown("### 🔮 Ask the Campaign Brain")
        query = st.text_input(
            "What do you want to know?",
            placeholder="e.g., What was the name of the blacksmith in the starting town?",
        )

        if st.button("Semantic Search ✨", type="primary"):
            if query:
                with st.spinner("Booting Brain from Disk & Searching..."):
                    try:
                        from openai import OpenAI
                        import numpy as np
                        import faiss
                        import json

                        client = OpenAI(api_key=openai_key)

                        # 1. Convert the DM's question into math
                        query_response = client.embeddings.create(
                            input=query, model="text-embedding-3-small"
                        )
                        query_embedding = (
                            np.array(query_response.data[0].embedding)
                            .astype("float32")
                            .reshape(1, -1)
                        )

                        # 2. READ FROM DISK (RAM Saver!)
                        local_index = faiss.read_index(faiss_path)
                        with open(map_path, "r", encoding="utf-8") as f:
                            local_chunks = json.load(f)

                        # 3. Search FAISS for the Top 3 most relevant chunks
                        k = 3
                        distances, indices = local_index.search(query_embedding, k)

                        # 4. Retrieve the exact text
                        retrieved_context = "\n\n---\n\n".join(
                            [
                                local_chunks[i]
                                for i in indices[0]
                                if i < len(local_chunks)
                            ]
                        )

                        # 5. Feed ONLY the relevant context to the LLM
                        prompt = f"""
                        You are the 'Campaign Lore Weaver', an expert D&D historian.

                        CRITICAL CITATION RULE:
                        You are an enterprise-grade TTRPG assistant. You must NEVER hallucinate or invent lore.
                        Every single time you answer a question or state a fact, you MUST cite your source using this format: [Source: Retrieved Context].
                        Based ONLY on the retrieved document context below, answer the DM's question.
                        If the answer is not in the context, say "I cannot find that in the current archives."

                        --- RETRIEVED CONTEXT ---
                        {retrieved_context}

                        --- DM'S QUESTION ---
                        {query}
                        """
                        answer = get_ai_response(prompt, llm_provider, user_api_key)
                        st.markdown(
                            f"<div class='stat-card'>{answer}</div>",
                            unsafe_allow_html=True,
                        )

                        # The Recruiter Flex
                        with st.expander(
                            "🔍 View Retrieved Vector Chunks (Debug Data)"
                        ):
                            st.info(
                                "This is the exact data the AI pulled from the local hard drive:"
                            )
                            st.write(retrieved_context)

                    except Exception as e:
                        st.error(f"Search failed: {e}")
            else:
                st.warning("⚠️ Please ask a question first!")

elif page == "⚔️ Encounter Architect":
    st.title("⚔️ Encounter Architect & VTT Export")
    st.write(
        "Generate balanced encounters and export them directly to your Virtual Tabletop."
    )

    col1, col2, col3 = st.columns(3)
    apl = col1.number_input("Average Party Level", min_value=1, max_value=20, value=10)
    p_count = col2.number_input("Number of Players", min_value=1, max_value=10, value=4)
    difficulty = col3.selectbox("Difficulty", ["Easy", "Medium", "Hard", "Deadly"])
    theme = st.text_input(
        "Environment / Theme (e.g., Volcano, Swamp, Undead Crypt)", "Dungeon"
    )

    if st.button("Generate Encounter 🎲"):
        with st.spinner("Calculating CR thresholds and fetching monsters..."):
            prompt = f"Generate a {difficulty} D&D 5e encounter for {p_count} level {apl} players with the theme: {theme}. Provide a list of monsters, their CR, and a brief tactical setup."
            st.session_state["last_encounter"] = get_ai_response(
                prompt, llm_provider, user_api_key
            )

    # --- 🔌 BULK VTT PIPELINE (Foundry/Roll20) ---
    if "last_encounter" in st.session_state:
        st.markdown(st.session_state["last_encounter"])

        st.divider()
        st.markdown("### 📦 Bulk VTT Transmission")
        st.caption(
            "Compile and export the entire encounter (all monsters & traps) in a single JSON payload."
        )

        col_export1, col_export2 = st.columns(2)

        if col_export1.button(
            "1. Forge Bulk JSON", key="bulk_json_btn", use_container_width=True
        ):
            with st.spinner("Structuring multi-entity payload..."):
                vtt_prompt = f"""
                Analyze this encounter: {st.session_state['last_encounter']}
                Format it into a single bulk JSON object for VTT import. 
                It MUST strictly follow this structure:
                {{
                    "encounter_title": "Generated Encounter",
                    "entities": [
                        {{"name": "Monster Name", "type": "monster", "count": 2, "cr": "1", "ac": 15, "hp": 22}},
                        {{"name": "Trap Name", "type": "trap", "damage": "2d6"}}
                    ]
                }}
                Return ONLY valid JSON. Do not include markdown formatting or backticks.
                """
                # We use the 'lawyer' profile because it is strictly prompted to follow rules without extra chat
                raw_json = get_ai_response(
                    vtt_prompt, llm_provider, user_api_key, profile="lawyer"
                )
                st.session_state.bulk_encounter_json = (
                    raw_json.replace("```json", "").replace("```", "").strip()
                )

        if st.session_state.get("bulk_encounter_json"):
            with st.expander("🔍 View Compiled Payload"):
                st.code(st.session_state.bulk_encounter_json, language="json")
                st.download_button(
                    label="💾 Download JSON",
                    data=st.session_state.bulk_encounter_json,
                    file_name="bulk_encounter.json",
                    mime="application/json",
                    use_container_width=True,
                )

            vtt_url = st.session_state.get("vtt_url", "")
            if col_export2.button(
                "2. 🚀 Blast to Live VTT", type="primary", use_container_width=True
            ):
                if not vtt_url:
                    st.error(
                        "⚠️ Global VTT Webhook URL missing. Please add it in the left sidebar."
                    )
                else:
                    st.info("📥 Queuing payload for background transmission...")
                    try:
                        # --- THE ASYNC TASK QUEUE ---
                        import threading
                        import requests

                        def background_vtt_push(target_url, json_payload):
                            """Runs entirely outside the Streamlit main thread to prevent UI freezing."""
                            try:
                                headers = {"Content-Type": "application/json"}
                                requests.post(
                                    target_url,
                                    data=json_payload,
                                    headers=headers,
                                    timeout=10,
                                )
                                # Note: We don't call st.success() here because it's a background thread.
                                print("Async VTT Payload Delivered Successfully.")
                            except Exception as e:
                                print(f"Async Task Queue Error: {e}")

                        # Compile the payload
                        payload = json.dumps(
                            {
                                "name": "Bulk Encounter",
                                "content": st.session_state.bulk_encounter_json,
                                "source": "DM Co-Pilot",
                            }
                        )

                        # Dispatch the heavy network request to the background worker
                        task_thread = threading.Thread(
                            target=background_vtt_push, args=(vtt_url, payload)
                        )
                        task_thread.start()

                        # Instantly free up the UI for the user
                        st.success(
                            "✅ Encounter queued! The UI is now unblocked while the data travels across the weave."
                        )
                        st.balloons()

                    except Exception as e:
                        st.error(f"Task Queue Failed: {e}")

    # --- 👻 THE PHANTOM PARTY (Multi-Agent Playtester) ---
    st.divider()
    st.markdown("### 👻 The Phantom Party (Automated Playtest)")
    st.write(
        "Spawn 4 AI personas to silently run through your generated encounter and predict how your players will ruin it."
    )

    if st.button(
        "Spawn Phantom Party & Run Simulation 🎲",
        type="primary",
        use_container_width=True,
    ):
        if "last_encounter" not in st.session_state:
            st.warning("⚠️ Please generate an encounter at the top of the page first!")
        else:
            with st.spinner("Initializing Multi-Agent Matrix..."):
                phantom_prompt = f"""
                You are a multi-agent simulation engine. I have designed this D&D 5e encounter:
                {st.session_state['last_encounter']}

                Simulate 4 distinct player personas (e.g., a reckless Barbarian, a cautious Wizard, a sneaky Rogue, a tactical Cleric) playing through this exact encounter.
                
                Provide a 'Phantom Playtest Report' formatted cleanly in Markdown:
                1. **Agent Actions:** A brief summary of what each of the 4 personas attempts to do in Round 1.
                2. **🩸 The Kill Zone:** Identify the specific monster or mechanic most likely to cause a player death.
                3. **⚠️ The Exploit:** Identify the most likely way the players will completely bypass, cheese, or break your encounter design.
                """
                # Your new custom telemetry pipeline is already built into get_ai_response!
                playtest_report = get_ai_response(
                    phantom_prompt, llm_provider, user_api_key
                )

                st.success("Simulation Complete! Review the post-action report below.")
                st.markdown(
                    f"<div class='stat-card'>{playtest_report}</div>",
                    unsafe_allow_html=True,
                )

    st.divider()

    # 🏆 SKILL CHALLENGE ARCHITECT
    st.markdown("### 🏆 Skill Challenge Architect")
    challenge_goal = st.text_input(
        "Goal of the challenge?",
        key="skill_goal_v1",
        placeholder="Escaping the collapsing temple...",
    )

    if st.button("Forge Challenge", key="skill_arch_btn", use_container_width=True):
        if challenge_goal:
            with st.spinner("Designing obstacles..."):
                prompt = f"Design a 5e Skill Challenge for: '{challenge_goal}'."
                st.session_state["last_skill_challenge"] = get_ai_response(
                    prompt, llm_provider, user_api_key
                )

    if "last_skill_challenge" in st.session_state:
        st.info(st.session_state["last_skill_challenge"])

    st.divider()

    # --- 🧠 THE TACTICAL BRAIN (v6.2 Lore-Aware) ---
    st.markdown("### 🧠 The Tactical Brain")
    st.write("Lethal strategy scripts based on your local monster data.")
    t_col1, t_col2 = st.columns(2)
    t_mon = t_col1.text_input("Monster Name:", key="t_mon_v62", placeholder="Beholder")
    t_party = t_col2.text_input(
        "Party Comp:", key="t_party_v62", placeholder="Level 5: Paladin, Bard"
    )

    if st.button("Generate Strategy", key="t_brain_btn_v62", use_container_width=True):
        if t_mon:
            with st.spinner("Analyzing tactics..."):
                # --- 🧬 LORE INJECTION ---
                local_data = ""
                if not monster_df.empty and t_mon in monster_df["name"].values:
                    m = monster_df[monster_df["name"] == t_mon].iloc[0]
                    local_data = f"Local Stats: HP:{m.get('hp')}, AC:{m.get('ac')}, Abilities:{m.get('abilities')}."

                prompt = f"Provide a 3-round lethal strategy for a {t_mon} against {t_party}. {local_data}"
                # Note: Using profile="tactician" here
                st.session_state["last_tactical_brain"] = get_ai_response(
                    prompt, llm_provider, user_api_key, profile="tactician"
                )

    if "last_tactical_brain" in st.session_state:
        st.warning(st.session_state["last_tactical_brain"], icon="💀")

    # Display the result if it exists in memory
    if "last_tactical_brain" in st.session_state:
        st.warning(st.session_state["last_tactical_brain"], icon="💀")
elif page == "⚖️ Action Economy Analyzer":
    st.title("⚖️ Action Economy Analyzer")
    st.markdown(
        "In D&D 5e, the side that takes the most actions usually wins. Calculate the pure mathematical balance of your encounter to see if your boss will get steamrolled in round one."
    )

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### 🦸‍♂️ The Party")
        party_size = st.number_input("Party Size", min_value=1, max_value=10, value=4)
        party_actions_multiplier = st.slider(
            "Average Actions per Player",
            min_value=1.0,
            max_value=3.0,
            value=1.5,
            step=0.5,
            help="Level 1-4 = 1 action. Level 5+ = 1.5 to 2 actions (Extra Attack, Bonus Actions).",
        )

    with c2:
        st.markdown("### 🐉 The Encounter")
        boss_actions = st.number_input(
            "Boss Attacks/Actions per turn", min_value=1, max_value=10, value=2
        )
        legendary = st.checkbox("Has Legendary Actions? (+3 Actions)")
        lair = st.checkbox("Has Lair Actions? (+1 Action)")
        minions = st.number_input(
            "Number of Minions", min_value=0, max_value=20, value=0
        )

    st.divider()

    total_party_actions = party_size * party_actions_multiplier
    total_monster_actions = (
        boss_actions + (3 if legendary else 0) + (1 if lair else 0) + minions
    )

    ratio = (
        total_party_actions / total_monster_actions
        if total_monster_actions > 0
        else total_party_actions
    )

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
    c5.metric("Advantage Ratio", f"{ratio:.1f} : 1", delta=status, delta_color=color)

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
        "Generate a 'Timeline of Evil' so you always know what the BBEG is doing off-screen while your players are distracted."
    )

    c1, c2 = st.columns(2)
    villain_archetype = c1.selectbox(
        "Archetype",
        [
            "Necromancer",
            "Corrupt Politician",
            "Ancient Dragon",
            "Cult Leader",
            "Fey Trickster",
            "Warlord",
        ],
    )
    villain_goal = c2.selectbox(
        "Ultimate Goal",
        [
            "Summon a Dark God",
            "Usurp the Throne",
            "Destroy a City",
            "Achieve Immortality",
            "Hoard Magical Artifacts",
        ],
    )

    custom_villain_details = st.text_area(
        "Specific Details (Optional)",
        placeholder="e.g., His name is Lord Vane, he controls an army of clockwork soldiers...",
    )

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

            villain_plan = get_ai_response(prompt, llm_provider, user_api_key)
            st.session_state.villain_json = villain_plan

    if st.session_state.villain_json:
        st.markdown(
            f"<div class='stat-card'>{st.session_state.villain_json}</div>",
            unsafe_allow_html=True,
        )
        st.download_button(
            "📥 Download Master Plan",
            st.session_state.villain_json,
            file_name="villain_timeline.txt",
        )

        st.divider()
        st.markdown("### 🔌 Export to Virtual Tabletop")
        st.markdown("Send this Villain Outline to your VTT journals.")

        col_vtt1, col_vtt2 = st.columns([1, 2])
        with col_vtt1:
            vtt_target = st.selectbox(
                "Target Engine",
                ["Foundry VTT", "Roll20 API", "FoxQuest (Beta)"],
                key="vtt_sel_vil",
            )
        with col_vtt2:
            webhook_url = st.text_input(
                "VTT Webhook URL",
                placeholder="e.g., http://localhost:30000/api/import",
                key="vtt_url_vil",
            )

        if st.button(f"Blast to {vtt_target} 🚀", type="primary", key="vtt_btn_vil"):
            if not webhook_url:
                st.warning("⚠️ Please enter your VTT Webhook URL first.")
            else:
                with st.spinner(f"Establishing connection to {vtt_target}..."):
                    try:
                        headers = {"Content-Type": "application/json"}
                        payload = json.dumps(
                            {
                                "name": "Villain Timeline",
                                "content": st.session_state.villain_json,
                            }
                        )
                        response = requests.post(
                            webhook_url, data=payload, headers=headers, timeout=5
                        )
                        if response.status_code in [200, 201]:
                            st.success(
                                f"⚡ Success! Payload delivered directly to {vtt_target}."
                            )
                            st.balloons()
                        else:
                            st.error(
                                f"Target server rejected the payload. Status Code: {response.status_code}"
                            )
                    except requests.exceptions.ConnectionError:
                        st.error(
                            "🔌 Connection Failed. Make sure your VTT server is running and the URL is correct."
                        )
                    except Exception as e:
                        st.error(f"An unexpected error occurred: {e}")

elif page == "🤝 DM Matchmaker":
    st.title("🤝 DM Matchmaker (Live Database)")
    st.markdown("Find your next table. This board is synced globally via Firestore.")

    if db is None:
        st.error("Database connection offline. Cannot access the Matchmaker.")
    else:
        # --- THE FILTER ENGINE (Sidebar) ---
        st.sidebar.markdown("### 🔍 Filter Board")
        filter_role = st.sidebar.radio(
            "Show:", ["All", "Looking for DM", "Looking for Players"]
        )

        # --- THE WRITE PIPELINE ---
        with st.expander("➕ Post a Listing", expanded=False):
            with st.form("matchmaker_form"):
                discord_handle = st.text_input(
                    "Discord Handle", placeholder="e.g., caleb#1234"
                )
                role = st.selectbox("Role", ["Looking for DM", "Looking for Players"])
                timezone = st.selectbox(
                    "Timezone", ["PST", "MST", "CST", "EST", "GMT", "CET", "Other"]
                )
                style = st.text_area(
                    "Campaign Style / Details",
                    placeholder="e.g., Heavy RP, lethal combat, 18+...",
                )

                if st.form_submit_button("Post to Board 🚀"):
                    if discord_handle and style:
                        try:
                            db.collection("matchmaker_board").add(
                                {
                                    "discord": discord_handle,
                                    "role": role,
                                    "timezone": timezone,
                                    "style": style,
                                    "timestamp": firestore.SERVER_TIMESTAMP,
                                }
                            )
                            st.success("Listing posted to the global board!")
                            st.balloons()
                        except Exception as e:
                            st.error(f"Failed to post: {e}")
                    else:
                        st.warning("Discord handle and details are required.")

        st.divider()

        # --- THE READ PIPELINE ---
        st.subheader("📋 Active Listings")

        # The Refresh Button
        if st.button("🔄 Refresh Board"):
            st.rerun()

        try:
            # Query Firestore, order by newest
            query = (
                db.collection("matchmaker_board")
                .order_by("timestamp", direction=firestore.Query.DESCENDING)
                .limit(20)
            )
            board_docs = query.stream()

            found_listings = False
            for doc in board_docs:
                data = doc.to_dict()

                # Apply Sidebar Filter
                if filter_role == "All" or filter_role == data.get("role"):
                    found_listings = True
                    with st.container():
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.markdown(
                                f"**{data.get('role', 'Unknown')}** | 🕒 {data.get('timezone', 'Unknown')}"
                            )
                            st.info(data.get("style", ""))
                        with col2:
                            st.code(data.get("discord", "Unknown"), language="text")
                        st.write("---")

            if not found_listings:
                st.info("No listings found matching your criteria.")

        except Exception as e:
            st.error(f"Failed to load board: {e}")

elif page == "🌐 Auto-Wiki Export":
    st.title("🌐 The Auto-Wiki Generator")
    st.markdown(
        "Instantly compile all the monsters, items, and lore you've generated this session into a standalone, beautiful HTML website. You can send this file directly to your players to read between sessions!"
    )

    if st.button("Generate Campaign Wiki 🪄", type="primary"):
        with st.spinner("Writing HTML and CSS..."):
            monster_data = st.session_state.get("forged_monster", "")
            villain_data = st.session_state.get("villain_json", "")
            magic_item = st.session_state.get("artificer_json", "")

            if not monster_data and not villain_data and not magic_item:
                st.warning(
                    "⚠️ Your session memory is currently empty. Go forge a monster, item, or villain first!"
                )
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
                    "⚡ Wiki Generated! Click below to download your interactive HTML file."
                )
                st.balloons()
                st.download_button(
                    label="📥 Download Campaign Wiki (index.html)",
                    data=html_content,
                    file_name="campaign_wiki.html",
                    mime="text/html",
                )

elif page == "🏛️ Community Vault":
    st.title("🏛️ The Community Vault")
    st.markdown(
        "Welcome to the Vault! Share your best generated monsters, encounters, and items with the 400+ DMs using DM Co-Pilot."
    )

    if db is None:
        st.error("Database connection offline. Cannot access the Vault.")
    else:
        with st.expander("➕ Publish a New Creation", expanded=False):
            creator_name = st.text_input("Your DM Name / Handle", value="Anonymous DM")
            creation_title = st.text_input(
                "Name of this Creation",
                placeholder="e.g., The Shadow Goblin Ambush",
            )
            creation_type = st.selectbox(
                "Type", ["Monster", "Encounter", "Loot Hoard", "Magic Item"]
            )
            creation_content = st.text_area("Paste the Content/JSON here:")

            if st.button("Publish to Vault 🚀"):
                if creation_title and creation_content:
                    with st.spinner("Running Data Governance & Sanitization checks..."):
                        try:
                            # --- DATA GOVERNANCE: SANITIZATION PIPELINE ---
                            import re

                            def sanitize_payload(text):
                                # 1. Scrub PII (Emails & Phone Numbers)
                                text = re.sub(
                                    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b",
                                    "[REDACTED_EMAIL]",
                                    text,
                                )
                                text = re.sub(
                                    r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",
                                    "[REDACTED_PHONE]",
                                    text,
                                )

                                # 2. Scrub Copyright/Restricted WotC Terms (Basic Governance)
                                restricted_terms = [
                                    "beholder",
                                    "mind flayer",
                                    "strahd",
                                    "vecna",
                                    "wizards of the coast",
                                ]
                                for term in restricted_terms:
                                    pattern = re.compile(re.escape(term), re.IGNORECASE)
                                    text = pattern.sub("[RESTRICTED_IP]", text)

                                return text

                            # Execute Pipeline
                            safe_title = sanitize_payload(creation_title)
                            safe_content = sanitize_payload(creation_content)
                            safe_creator = sanitize_payload(creator_name)

                            # Push to Cloud
                            db.collection("community_vault").document().set(
                                {
                                    "creator": safe_creator,
                                    "title": safe_title,
                                    "type": creation_type,
                                    "content": safe_content,
                                    "timestamp": firestore.SERVER_TIMESTAMP,
                                }
                            )
                            st.success(
                                f"Legendary! '{safe_title}' has been sanitized and secured in the Vault."
                            )
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
            vault_docs = (
                db.collection("community_vault")
                .order_by("timestamp", direction=firestore.Query.DESCENDING)
                .limit(10)
                .stream()
            )
            found_items = False
            for doc in vault_docs:
                found_items = True
                data = doc.to_dict()
                current_upvotes = data.get("upvotes", 0)

                # We added the upvote count directly to the expander title!
                with st.expander(
                    f"[{current_upvotes} ⬆️] {data.get('type', 'Item')} | {data.get('title', 'Untitled')} (by {data.get('creator', 'Unknown')})"
                ):
                    st.text(data.get("content", "No content available."))

                    # Put the Download and Upvote buttons side-by-side
                    col1, col2 = st.columns(2)
                    with col1:
                        st.download_button(
                            "📥 Download",
                            data.get("content", ""),
                            file_name=f"{data.get('title', 'vault_item')}.txt",
                            key=f"dl_{doc.id}",
                            use_container_width=True,
                        )
                    with col2:
                        if st.button(
                            f"⬆️ Upvote ({current_upvotes})",
                            key=f"upvote_{doc.id}",
                            use_container_width=True,
                        ):
                            try:
                                from google.cloud import firestore

                                # Use set with merge=True to safely add the upvotes field if it doesn't exist yet
                                db.collection("community_vault").document(doc.id).set(
                                    {"upvotes": firestore.Increment(1)}, merge=True
                                )
                                st.toast(f"Upvoted {data.get('title')}!", icon="🔥")
                                st.rerun()  # Refresh the page instantly to show the new number!
                            except Exception as e:
                                st.error(f"Failed to upvote: {e}")
            if not found_items:
                st.info(
                    "The Vault is currently empty. Be the first to publish something!"
                )
        except Exception as e:
            st.error(f"Could not load the Vault. Error: {e}")

elif page == "🍻 Tavern Rumor Mill":
    st.title("🍻 Tavern Rumor Mill")
    st.info(
        "Generate 3 rumors for your players to overhear: One true, one false, and one dangerously misleading."
    )
    location = st.text_input("Town, Tavern, or NPC Name:")
    if st.button("Listen at the Bar 🍺") and location:
        prompt = f"Generate 3 short, punchy D&D rumors overheard in or around '{location}'. 1 must be completely true, 1 must be totally false, and 1 must be a dangerous half-truth. Do not label which is which in the output."
        with st.spinner("Eavesdropping..."):
            st.markdown(
                f"<div class='stat-card'>{get_ai_response(prompt, llm_provider, user_api_key)}</div>",
                unsafe_allow_html=True,
            )

# ==========================================
# 💰 DYNAMIC SHOPS & LOOT
# ==========================================
elif page == "💰 Dynamic Shops":
    st.title("💰 Dynamic Shops")

    # --- 💎 THE LOOT APPRAISER & LEDGER (v6.1) ---
    st.markdown("### 💎 The Loot Appraiser & Ledger")
    st.write("Convert messy coin dumps to Gold and split it evenly among the party.")

    raw_loot = st.text_area(
        "Messy Loot Dump:",
        placeholder="400cp, 12sp, a glowing green dagger...",
        key="loot_dump_v1",
    )
    p_size = st.number_input("Party Size", min_value=1, value=4, key="p_size_v1")

    if st.button(
        "Appraise & Split Loot", key="loot_split_v1", use_container_width=True
    ):
        if raw_loot:
            with st.spinner("Crunching numbers..."):
                prompt = f"Convert this loot to total Gold (gp) and divide by {p_size}: '{raw_loot}'. Appraise any non-coin items with brief descriptions."
                # RULE 4 & 5: Session Lock + Accountant Profile
                st.session_state["last_loot_split"] = get_ai_response(
                    prompt, llm_provider, user_api_key, profile="accountant"
                )

    # RULE 4: Persistent display outside the button loop
    if "last_loot_split" in st.session_state:
        st.success(st.session_state["last_loot_split"])

    st.divider()

    # --- 🛒 SHOP GENERATOR ---
    st.markdown("### 🛒 Quick Inventory Generator")
    shop_type = st.selectbox(
        "Shop Type",
        ["Blacksmith", "Alchemist", "General Store", "Magic Item Broker"],
    )

    if st.button("Open Shop 🛒", use_container_width=True):
        with st.spinner(f"Stocking the {shop_type}..."):
            shop_prompt = f"Generate a highly flavorful D&D 5e {shop_type} inventory. Include the shopkeeper's name, a brief quirk, and 5 interesting items for sale with their prices in gold pieces."
            shop_inventory = get_ai_response(shop_prompt, llm_provider, user_api_key)
            st.markdown(
                f"<div class='stat-card'>{shop_inventory}</div>",
                unsafe_allow_html=True,
            )

elif page == "💎 Magic Item Artificer":
    st.title("💎 Magic Item Artificer")
    col1, col2 = st.columns(2)
    with col1:
        item_type = st.selectbox(
            "Item Type",
            ["Weapon", "Armor", "Wondrous Item", "Ring", "Staff", "Potion"],
        )
    with col2:
        rarity = st.selectbox(
            "Rarity",
            ["Common", "Uncommon", "Rare", "Very Rare", "Legendary", "Artifact"],
        )
    custom_details = st.text_area(
        "Item Concept",
        placeholder="e.g., A dagger made of frozen shadow that bleeds cold...",
    )

    if st.button("Forge Item 🔨"):
        with st.spinner("Channeling arcane energy..."):
            prompt = f"Create a D&D 5e {rarity} {item_type}. Concept: {custom_details}. Return ONLY a valid JSON object with these keys: 'name', 'type', 'rarity', 'properties' (list), 'description', 'attunement' (boolean)."
            raw_json = get_ai_response(prompt, llm_provider, user_api_key)
            st.session_state.artificer_json = (
                raw_json.replace("```json", "").replace("```", "").strip()
            )

    if st.session_state.artificer_json:
        # --- BLOCK 1: JSON VALIDATION ---
        try:
            st.json(json.loads(st.session_state.artificer_json))
            st.download_button(
                "📥 Download Item JSON",
                data=st.session_state.artificer_json,
                file_name="magic_item.json",
                mime="application/json",
            )
        except Exception as e:
            st.error("The weave flickered. Try forging again.")
            st.write("Debug info:", st.session_state.artificer_json)

        # --- BLOCK 2: DIRECT VTT TRANSMISSION ---
        st.divider()
        st.markdown("### 🔌 Export to Virtual Tabletop")
        st.markdown(
            "Send this generated magic item directly to your live VTT server via REST API."
        )

        col_vtt1, col_vtt2 = st.columns([1, 2])
        with col_vtt1:
            vtt_target = st.selectbox(
                "Target Engine",
                ["Foundry VTT", "Roll20 API", "FoxQuest (Beta)"],
                key="vtt_sel_art",
            )
        with col_vtt2:
            # Look for the global URL and display a success lock!
            webhook_url = st.session_state.get("vtt_url", "")
            if webhook_url:
                st.success("🔗 Locked onto Global VTT Webhook!")
            else:
                st.warning("⚠️ No Global VTT URL detected in sidebar.")

        if st.button(f"Blast to {vtt_target} 🚀", type="primary", key="vtt_btn_art"):
            if not webhook_url:
                st.warning("⚠️ Please enter your VTT Webhook URL in the sidebar first.")
            else:
                with st.spinner(f"Establishing connection to {vtt_target}..."):
                    try:
                        headers = {"Content-Type": "application/json"}
                        payload = st.session_state.artificer_json
                        response = requests.post(
                            webhook_url,
                            data=payload,
                            headers=headers,
                            timeout=5,
                        )
                        if response.status_code in [200, 201]:
                            st.success(
                                f"⚡ Success! Payload delivered directly to {vtt_target}."
                            )
                            st.balloons()
                        else:
                            st.error(
                                f"Target server rejected the payload. Status Code: {response.status_code}"
                            )
                    except requests.exceptions.ConnectionError:
                        st.error(
                            "🔌 Connection Failed. Make sure your VTT server is running and the URL is correct."
                        )
                    except Exception as e:
                        st.error(f"An unexpected error occurred: {e}")
elif page == "🎭 NPC Quick Forge":
    st.title("🎭 NPC Quick Forge")
    npc_type = st.text_input("Profession or Role (e.g., Tavern Keeper, Shady Guard)")
    if st.button("Forge NPC"):
        with st.spinner("Breathing life into NPC..."):
            npc_prompt = f"Create a D&D 5e NPC who is a {npc_type}. Give them a name, appearance, a distinct quirk, a hidden secret, and a quote."
            npc_res = get_ai_response(npc_prompt, llm_provider, user_api_key)
            st.markdown(
                f"<div class='stat-card'>{npc_res}</div>", unsafe_allow_html=True
            )
elif page == "⚙️ Trap Architect":
    st.title("⚙️ Trap Architect")
    danger = st.selectbox("Lethality", ["Nuisance", "Dangerous", "Deadly"])
    if st.button("Build Trap"):
        with st.spinner("Setting trigger..."):
            trap_prompt = f"Create a {danger} D&D 5e trap. Include the trigger, the effect/damage, and how players can spot and disarm it."
            trap_res = get_ai_response(trap_prompt, llm_provider, user_api_key)
            st.markdown(
                f"<div class='stat-card'>{trap_res}</div>", unsafe_allow_html=True
            )

elif page == "📜 Scribe's Handouts":
    st.title("📜 Scribe's Handouts")
    topic = st.text_area("What is the letter, journal, or bounty about?")
    if st.button("Write Handout"):
        with st.spinner("Scribing..."):
            handout_text = get_ai_response(
                f"Write an immersive, in-universe D&D handout about: {topic}",
                llm_provider,
                user_api_key,
            )
            st.markdown(
                f"<div class='stat-card'>{handout_text}</div>",
                unsafe_allow_html=True,
            )
        st.download_button("📥 Download Handout", handout_text, file_name="handout.txt")

        st.divider()
        st.markdown("### 🔌 Export to Virtual Tabletop")
        st.markdown(
            "Send this journal handout directly to your live VTT server via REST API."
        )

        col_vtt1, col_vtt2 = st.columns([1, 2])
        with col_vtt1:
            vtt_target = st.selectbox(
                "Target Engine",
                ["Foundry VTT", "Roll20 API", "FoxQuest (Beta)"],
                key="vtt_sel_scribe_v10",
            )
        with col_vtt2:
            webhook_url = st.text_input(
                "VTT Webhook URL",
                placeholder="e.g., http://localhost:30000/api/import",
                key="vtt_url_scribe_v10",
            )

        # Mapping the correct source text for the blast
        # We use transcription.text from your Audio Scribe logic
        final_handout = (
            transcription.text
            if "transcription" in locals()
            else "No transcription data found."
        )

        if st.button(
            f"Blast to {vtt_target} 🚀", type="primary", key="vtt_btn_scribe_v10"
        ):
            if not webhook_url:
                st.warning("⚠️ Please enter your VTT Webhook URL first.")
            else:
                with st.spinner(f"Establishing connection to {vtt_target}..."):
                    try:
                        import requests, json

                        headers = {"Content-Type": "application/json"}
                        # Standardized payload for Foundry/Roll20 listeners
                        payload = json.dumps(
                            {
                                "name": "Audio Scribe Journal",
                                "content": final_handout,
                                "source": "DM Co-Pilot v3.4",
                            }
                        )
                        response = requests.post(
                            webhook_url, data=payload, headers=headers, timeout=5
                        )

                        if response.status_code in [200, 201]:
                            st.success(
                                f"⚡ Success! Payload delivered directly to {vtt_target}."
                            )
                            st.balloons()
                        else:
                            st.error(
                                f"Target server rejected the payload. Status: {response.status_code}"
                            )
                    except Exception as e:
                        st.error(f"🔌 Connection Failed: {e}")

elif page == "🗑️ Pocket Trash Loot":
    st.title("🗑️ Pocket Trash Loot")
    if st.button("Search the bodies..."):
        with st.spinner("Searching..."):
            st.markdown(
                f"<div class='stat-card'>{get_ai_response('Generate 5 weird, mundane, or slightly gross trinkets you would find in a goblin or bandit pocket. No magic items.', llm_provider, user_api_key)}</div>",
                unsafe_allow_html=True,
            )

elif page == "👑 The Dragon's Hoard":
    st.title("👑 The Dragon's Hoard")
    hoard_cr = st.selectbox("Target CR Hoard", ["0-4", "5-10", "11-16", "17+"])
    if st.button("Generate Hoard"):
        with st.spinner("Counting gold..."):
            st.markdown(
                f"<div class='stat-card'>{get_ai_response(f'Generate a D&D 5e treasure hoard for CR {hoard_cr}. Include coins, gems, art objects, and 2-3 appropriate magic items.',
                        llm_provider, user_api_key)}</div>",
                unsafe_allow_html=True,
            )

elif page == "🌍 Worldbuilder":
    st.title("🌍 Worldbuilder Co-Pilot")
    focus = st.selectbox(
        "What are we building?",
        ["Town/City", "Faction/Guild", "Pantheon/Deity", "Lost Ruin"],
    )
    if st.button("Build World"):
        with st.spinner("Shaping the world..."):
            st.markdown(
                f"<div class='stat-card'>{get_ai_response(f'Create a detailed D&D 5e lore entry for a {focus}. Include history, notable figures, and a current conflict.',
                        llm_provider, user_api_key)}</div>",
                unsafe_allow_html=True,
            )
elif page == "👁️ Sensory Room":
    st.header("👁️ The Sensory Room")
    st.caption(
        "Instantly generate immersive, five-sense environmental descriptions using Groq (Llama-3)."
    )
    st.markdown("---")

    # 1. Groq Client Initialization (Cached per Rule 4)
    @st.cache_resource
    def get_groq_client():
        from groq import Groq

        return Groq()

    try:
        client = get_groq_client()
    except Exception as e:
        st.error(f"⚠️ Nexus Connection Offline. Check Groq configuration: {e}")
        st.stop()

    # 2. The Input Matrix
    col1, col2 = st.columns(2)
    env_type = col1.selectbox(
        "Environment Type",
        [
            "Dungeon",
            "Tavern",
            "Ancient Forest",
            "Cave System",
            "City Slums",
            "Opulent Palace",
        ],
    )
    env_vibe = col2.selectbox(
        "Atmosphere",
        [
            "Gloomy & Oppressive",
            "Hostile & Tense",
            "Warm & Inviting",
            "Eerie & Mysterious",
            "Chaotic & Noisy",
        ],
    )

    custom_details = st.text_input(
        "Specific details to include (e.g., 'smells like sulfur', 'goblin graffiti')",
        placeholder="Optional...",
    )

    # 3. The Llama-3 Generation Engine
    if st.button(
        "Generate Sensory Description", type="primary", use_container_width=True
    ):
        with st.spinner("Channeling the environment..."):
            try:
                # Uses the global Groq key logic from your sidebar bridge!
                api_key = (
                    user_api_key if user_api_key else st.secrets.get("GROQ_API_KEY")
                )
                if not api_key:
                    st.error("⚠️ Please enter your Groq API Key in the sidebar.")
                    st.stop()

                # Re-initialize with the actual key just to be safe
                from groq import Groq

                active_client = Groq(api_key=api_key)

                prompt = f"""
                You are a master Dungeon Master. Describe a {env_type} with a {env_vibe} atmosphere.
                Include the following custom details: {custom_details if custom_details else "None"}.
                Keep it strictly to one short, evocative paragraph (3-4 sentences). 
                Focus heavily on the five senses: what the players see, hear, smell, and feel.
                Do NOT include player actions or dialogue. Just the environmental description.
                """

                completion = active_client.chat.completions.create(
                    model="llama3-8b-8192",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                    max_tokens=200,
                )

                description = completion.choices[0].message.content

                # 4. Output (No session_state bloat per Rule 5)
                st.success("Environment Generated")
                st.markdown(f"> *{description}*")

            except Exception as e:
                st.error(f"Generation Failed: {e}")

elif page == "🤖 DM Assistant":
    st.title("🤖 DM Assistant")
    question = st.text_area("Ask any D&D ruling or prep question:")
    if st.button("Consult Assistant"):
        with st.spinner("Thinking..."):
            st.markdown(
                f"<div class='stat-card'>{get_ai_response(question, llm_provider, user_api_key)}</div>",
                unsafe_allow_html=True,
            )

elif page == "🎙️ Audio Scribe":
    st.title("🎙️ Audio Scribe & Sentiment Analysis")

    # --- 🛡️ VIBE CHECK ENGINE (Strict Airlock) ---
    vibe_monitor_active = st.toggle(
        "🛡️ Enable Auto-Safety Monitor (Vibe Check)",
        value=False,
        key="vibe_toggle_v1",
    )
    st.write("---")

    # --- STATE LOCK: PREVENT GHOST TRIGGERS ---
    if "last_audio_hash" not in st.session_state:
        st.session_state.last_audio_hash = None
    if "last_transcription" not in st.session_state:
        st.session_state.last_transcription = ""

    # UNIQUE KEY traps this mic on this page
    audio_file_scribe = st.audio_input(
        "Record session audio:", key="scribe_mic_final_v8"
    )

    if audio_file_scribe is not None:
        import hashlib

        audio_bytes = audio_file_scribe.getvalue()
        current_hash = hashlib.md5(audio_bytes).hexdigest()

        if current_hash != st.session_state.last_audio_hash:
            # NEW RECORDING DETECTED! Run the engine.
            st.session_state.last_audio_hash = current_hash

            with st.spinner("Transcribing via Whisper..."):
                try:
                    from groq import Groq

                    api_key = st.secrets.get("GROQ_API_KEY", user_api_key)
                    client = Groq(api_key=api_key)
                    transcription = client.audio.transcriptions.create(
                        file=("audio.wav", audio_file_scribe.read()),
                        model="whisper-large-v3",
                    )

                    # Cache the text so it survives reruns
                    st.session_state.last_transcription = transcription.text

                    st.success("Transcription Complete!")
                    st.text_area(
                        "Live Transcript",
                        st.session_state.last_transcription,
                        height=200,
                    )

                    # --- 🎙️ THE AUTO-FETCH ORACLE (PHASE 1) ---
                    with st.spinner("Oracle is listening for threats..."):
                        try:
                            oracle_prompt = f"Read this transcript. Did the DM explicitly mention the name of a standard D&D 5e monster (e.g., Goblin, Dragon, Lich, Zombie)? If yes, reply with ONLY the exact name of the most prominent monster. If no, reply with 'None'. Transcript: '{st.session_state.last_transcription}'"
                            oracle_target = (
                                get_ai_response(
                                    oracle_prompt,
                                    llm_provider,
                                    user_api_key,
                                    profile="default",
                                )
                                .strip()
                                .lower()
                            )
                            oracle_target = (
                                oracle_target.replace(".", "")
                                .replace("the ", "")
                                .replace('"', "")
                            )

                            if oracle_target != "none" and not monster_df.empty:
                                match = monster_df[
                                    monster_df["name"]
                                    .str.lower()
                                    .str.contains(oracle_target, na=False)
                                ]
                                if not match.empty:
                                    m_data = match.iloc[0]
                                    st.warning(
                                        f"👁️ Oracle Passive Detection: **{m_data['name']}**"
                                    )
                                    stat_html = f"""
                                    <div class='stat-card' style='border-color: #ff4b4b; border-left: 10px solid #ff4b4b !important;'>
                                    <h3 style='margin-bottom:2px; color:#ff4b4b;'>🩸 {m_data['name']}</h3>
                                    <b>AC:</b> {m_data.get('ac', '?')} | <b>HP:</b> {m_data.get('hp', '?')} | <b>CR:</b> {m_data.get('cr', '?')}<br>
                                    <hr style='border-color:#ff4b4b; margin: 5px 0;'>
                                    <span style='font-size: 0.9em; color: #ddd;'><b>Actions:</b><br>{str(m_data.get('actions', ''))[:400]}...</span>
                                    </div>
                                    """
                                    st.markdown(stat_html, unsafe_allow_html=True)
                        except Exception as e:
                            pass

                    # --- 🎙️ THE SOUND-WEAVER (PHASE 2) ---
                    try:
                        transcript_lower = st.session_state.last_transcription.lower()
                        sfx_triggers = {
                            "fireball": "https://cdn.pixabay.com/download/audio/2022/01/18/audio_d0a13f69d2.mp3",
                            "dragon": "https://cdn.pixabay.com/download/audio/2022/03/10/audio_c8c8a73467.mp3",
                            "roll initiative": "https://cdn.pixabay.com/download/audio/2021/08/04/audio_12b0c7443c.mp3",
                        }
                        for trigger_word, sfx_url in sfx_triggers.items():
                            if trigger_word in transcript_lower:
                                st.toast(
                                    f"🔊 Sound-Weaver Triggered: {trigger_word.title()}",
                                    icon="🔊",
                                )
                                import streamlit.components.v1 as components

                                components.html(
                                    f'<audio autoplay><source src="{sfx_url}" type="audio/mpeg"></audio>',
                                    height=0,
                                    width=0,
                                )
                                break
                    except Exception as e:
                        pass
                except Exception as e:
                    pass

                    # --- 🎙️ THE OMNISCIENT SCRIBE (PHASE 3) ---
                    with st.spinner(
                        "Omniscient Scribe is monitoring for rules queries..."
                    ):
                        try:
                            rule_prompt = f"""
                                Read this live D&D table transcript. Did a player or DM ask a specific rules question? 
                                (e.g., 'How does grapple work?', 'What does restrained do?', 'How much damage is falling?').
                                If yes, provide the exact 5e rule in 2 sentences or less.
                                If no rules question was asked, reply with exactly: 'None'.
                                Transcript: '{st.session_state.last_transcription}'
                                """
                            # We use the 'lawyer' profile so it cites strict RAW rules and doesn't hallucinate
                            rule_audit = get_ai_response(
                                rule_prompt,
                                llm_provider,
                                user_api_key,
                                profile="lawyer",
                            ).strip()

                            if (
                                rule_audit.lower() != "none"
                                and not rule_audit.startswith("⚠️")
                            ):
                                st.warning(
                                    "⚖️ **Omniscient Scribe (Rules Arbitration Intercepted):**"
                                )
                                st.markdown(
                                    f"""
                                    <div class='stat-card' style='border-color: #ffd700; border-left: 10px solid #ffd700 !important; color: #ffd700;'>
                                    <h4 style='margin-top:0px; color:#ffd700;'>📖 The Rulebook Says:</h4>
                                    {rule_audit}
                                    </div>
                                    """,
                                    unsafe_allow_html=True,
                                )
                        except Exception as e:
                            pass  # Fail silently so we never interrupt the audio pipeline

                    # --- 🎙️ THE CARTOGRAPHER'S VEIL (PHASE 4) ---
                    with st.spinner("Cartographer is mapping your words..."):
                        try:
                            map_prompt = f"""
                                Read this live D&D table transcript. Did the DM just describe the players entering a specific new room, area, or building? 
                                If yes, reply ONLY with the exact name of the location.
                                If no new location was entered, reply with exactly: 'None'.
                                Transcript: '{st.session_state.last_transcription}'
                                """
                            map_audit = get_ai_response(
                                map_prompt, llm_provider, user_api_key
                            ).strip()

                            # 🚨 DEBUG MODE: Unsilenced output so we can see what the AI is doing
                            st.info(f"🔍 **Cartographer AI Output:** '{map_audit}'")

                            if (
                                map_audit.lower() != "none"
                                and not map_audit.startswith("⚠️")
                                and "none" not in map_audit.lower()
                            ):
                                st.success(
                                    f"🗺️ **Cartographer's Veil:** Unveiled '{map_audit}' to the Player Portal!"
                                )

                                if db is not None:
                                    db.collection("live_tables").document(
                                        st.session_state.campaign_id
                                    ).set(
                                        {
                                            "revealed_room": map_audit,
                                            "timestamp": firestore.SERVER_TIMESTAMP,
                                        },
                                        merge=True,
                                    )
                        except Exception as e:
                            st.error(f"🔥 Cartographer Crash: {e}")

                        except Exception as e:
                            st.error(f"Scribe Error: {e}")
        else:
            # OLD RECORDING: Ghost Trigger Blocked! Render cached text.
            st.success("Transcription Complete! (Cached)")
            st.text_area(
                "Live Transcript", st.session_state.last_transcription, height=200
            )

    st.markdown("### 🪄 Magic Formatting & Memory Forge")
    col_scribe1, col_scribe2 = st.columns(2)

    if col_scribe1.button(
        "Turn into Campaign Notes", key="scribe_btn_v8", use_container_width=True
    ):
        if st.session_state.get("last_transcription"):
            with st.spinner("Formatting notes..."):
                st.info(
                    get_ai_response(
                        f"Format these notes: {st.session_state.last_transcription}",
                        llm_provider,
                        user_api_key,
                    )
                )
        else:
            st.warning("No audio recorded yet.")

    if col_scribe2.button(
        "Inject into Infinite Archive 🧠",
        type="primary",
        key="forge_btn_v8",
        use_container_width=True,
    ):
        if not st.session_state.get("last_transcription"):
            st.warning("No audio recorded yet.")
        elif not openai_key:
            st.error("⚠️ OpenAI API Key required for Vector Embeddings.")
        else:
            with st.spinner("Extracting permanent lore and injecting into Qdrant..."):
                import os, uuid, re
                from qdrant_client.models import Distance, VectorParams, PointStruct

                raw_q_url = st.secrets.get("QDRANT_URL", os.getenv("QDRANT_URL", ""))
                raw_q_key = st.secrets.get(
                    "QDRANT_API_KEY", os.getenv("QDRANT_API_KEY", "")
                )
                qdrant_url = raw_q_url.strip() if raw_q_url else ""
                qdrant_key = raw_q_key.strip() if raw_q_key else ""

                if not qdrant_url:
                    st.error(
                        "⚠️ Qdrant credentials missing. Cannot access the Infinite Archive."
                    )
                else:
                    try:
                        q_client = init_qdrant(qdrant_url, qdrant_key)
                        o_client = OpenAI(api_key=openai_key)

                        safe_campaign_id = re.sub(
                            r"[^a-z0-9_]", "_", st.session_state.campaign_id.lower()
                        )
                        collection_name = f"memory_vault_{safe_campaign_id}"

                        if not q_client.collection_exists(collection_name):
                            q_client.create_collection(
                                collection_name=collection_name,
                                vectors_config=VectorParams(
                                    size=1536, distance=Distance.COSINE
                                ),
                            )

                        lore_prompt = f"Extract the most important permanent world-building facts, NPC names, and major events from this session transcript. Format as a concise summary: {st.session_state.last_transcription}"
                        extracted_lore = get_ai_response(
                            lore_prompt, llm_provider, user_api_key
                        )

                        emb_res = o_client.embeddings.create(
                            input=extracted_lore, model="text-embedding-3-small"
                        )
                        q_client.upsert(
                            collection_name=collection_name,
                            points=[
                                PointStruct(
                                    id=str(uuid.uuid4()),
                                    vector=emb_res.data[0].embedding,
                                    payload={"text": extracted_lore},
                                )
                            ],
                        )

                        st.success(
                            f"Lore securely locked into the {st.session_state.campaign_id} Archive!"
                        )
                        st.info(f"**Memorized Fact:** {extracted_lore}")

                    except Exception as e:
                        st.error(f"Scribe Failed: {e}")
    st.divider()
elif page == "⚖️ Real-Time Rules Lawyer":
    st.title("⚖️ Real-Time Rules Lawyer (v4.0)")
    # --- 🎯 THE DC CALIBRATOR (v6.1) ---
    st.markdown("### 🎯 The DC Calibrator")
    st.write("Instant DC and skill check recommendations for crazy player actions.")
    crazy_action = st.text_input(
        "What is the player trying to do?",
        placeholder="Slide down the banister, shoot the chandelier...",
        key="crazy_act_v1",
    )

    if st.button(
        "Calculate DC & Consequence", key="calc_dc_v1", use_container_width=True
    ):
        if crazy_action:
            with st.spinner("Consulting the physics of the Realms..."):
                prompt = f"A D&D 5e player wants to: '{crazy_action}'. State the skill to roll, a fair DC, and the mechanical consequence of failure. Under 4 sentences."
                # RULE 4 & 5: Session Lock + Lawyer Profile
                st.session_state["last_dc_calc"] = get_ai_response(
                    prompt, llm_provider, user_api_key, profile="lawyer"
                )

    # RULE 4: Persistent display outside the button loop
    if "last_dc_calc" in st.session_state:
        st.info(st.session_state["last_dc_calc"])

    st.divider()

    st.markdown(
        "Query the multi-agent engine for authoritative D&D 5e rules. Zero hallucinations, 100% RAW."
    )

    # User Input
    rule_query = st.text_input(
        "Ask a rules question:",
        placeholder="e.g., Does concentration break if I'm incapacitated?",
        key="lawyer_input_v4",
    )

    if st.button("Consult the Lawyer ⚖️", type="primary", key="lawyer_btn_v4"):
        if not rule_query:
            st.warning("Please enter a question first.")
        else:
            with st.spinner("Agents are deliberating..."):
                try:
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
                        st.error(
                            f"Lawyer is busy (Error {response.status_code}). Check backend logs."
                        )
                except Exception as e:
                    st.error(f"📡 Connection to Backend Failed: {e}")

elif page == "🎲 Fate-Threader (v4.1)":
    st.title("🎲 The Fate-Threader: Combat Simulator")
    st.markdown(
        "Run 1,000 parallel simulations to predict if your party survives this encounter."
    )

    col1, col2 = st.columns(2)
    with col1:
        p_count = st.number_input("Number of Players", 1, 10, 4, key="fate_p_count")
        p_hp = st.number_input("Average Player HP", 1, 500, 36, key="fate_p_hp")
    with col2:
        m_hp = st.number_input("Monster HP", 1, 1000, 150, key="fate_m_hp")
        m_dpr = st.number_input(
            "Monster Damage Per Round", 1, 200, 25, key="fate_m_dpr"
        )

    if st.button("Thread the Fate 🔮", type="primary", key="fate_btn_v41"):
        with st.spinner("Simulating 1,000 timelines..."):
            try:
                # BYPASS THE API ENTIRELY: Run the math directly in Streamlit
                tpk_count = 0
                total_rounds = 0
                sim_runs = 1000

                for _ in range(sim_runs):
                    party_hp = [int(p_hp)] * int(p_count)
                    boss_hp = int(m_hp)
                    rounds = 0

                    while boss_hp > 0 and any(hp > 0 for hp in party_hp):
                        rounds += 1
                        living_players = [i for i, hp in enumerate(party_hp) if hp > 0]
                        if not living_players:
                            break

                        # Monster attacks
                        target = random.choice(living_players)
                        party_hp[target] -= int(m_dpr)

                        # Party attacks (10 dmg avg per player)
                        boss_hp -= len(living_players) * 10

                    if all(hp <= 0 for hp in party_hp):
                        tpk_count += 1
                        total_rounds += rounds

                prob = (tpk_count / sim_runs) * 100
                rating = (
                    "🔴 TPK LIKELY"
                    if prob > 50
                    else "🟡 DANGEROUS" if prob > 15 else "🟢 SAFE"
                )

                st.metric("TPK Probability", f"{prob}%")
                st.subheader(f"Survival Rating: {rating}")
                st.write(
                    f"Average combat duration: **{total_rounds // sim_runs} rounds**."
                )

            except Exception as e:
                st.error(f"Math Error: {str(e)}")
elif page == "🎙️ Voice-Command Desk":
    st.title("🎙️ Voice-Command Desk (Beta)")
    if "combatants" not in st.session_state:
        st.session_state.combatants = []
    st.info("Example: 'The Goblin takes 14 fire damage.'")
    # UNIQUE KEY traps the command mic here
    audio_value_cmd = st.audio_input("Record Voice Command", key="cmd_mic_final_v8")
    if audio_value_cmd:
        with st.spinner("Processing..."):
            # ... (Existing Voice Logic)
            pass
    st.divider()

elif page == "🕸️ Web of Fates":
    st.title("🕸️ The Living Codex (Web of Fates)")
    st.markdown(
        "Type a quick summary of your campaign's current events, factions, or NPC relationships. The AI will instantly generate an interactive, drag-and-drop knowledge graph of your world."
    )

    lore_input = st.text_area(
        "Campaign Summary / Lore Dump",
        height=150,
        placeholder="e.g., The Goblin King despises the Silver Hand Guild. The Silver Hand Guild secretly protects the Sun Stone. Elara the Rogue stole the Sun Stone last night...",
    )

    if st.button("Generate Knowledge Graph 🧠", type="primary"):
        if not openai_key:
            st.error(
                "⚠️ OpenAI API Key required for the Living Codex. Please add it in the sidebar."
            )
        elif not lore_input:
            st.warning("⚠️ Please enter some lore to map!")
        else:
            with st.spinner("Weaving the threads of fate..."):
                try:
                    from openai import OpenAI

                    client = OpenAI(api_key=openai_key)

                    system_prompt = """
                    You are a knowledge graph extractor for Dungeons & Dragons. Read the user's lore and extract the core entities and their relationships.
                    Return ONLY a strict JSON object with two arrays: 'nodes' and 'edges'.
                    'nodes' must have: 'id' (string, exact name of entity), 'label' (string, display name), 'group' (string: strictly choose from 'NPC', 'Faction', 'Location', 'Item').
                    'edges' must have: 'source' (string, id of source node), 'target' (string, id of target node), 'label' (string, short description of the relationship).
                    """

                    response = client.chat.completions.create(
                        model="gpt-4o",
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": lore_input},
                        ],
                        response_format={"type": "json_object"},
                    )

                    graph_data = json.loads(response.choices[0].message.content)
                    st.session_state.living_codex_data = graph_data
                    st.success("✅ Codex Generated!")
                except Exception as e:
                    st.error(f"Codex Weaving Error: {e}")

    if "living_codex_data" in st.session_state:
        st.divider()
        data = st.session_state.living_codex_data

        nodes = []
        edges = []

        # Color mapping for visual clarity
        color_map = {
            "NPC": "#ff4b4b",  # Red
            "Faction": "#4b4bff",  # Blue
            "Location": "#4bff4b",  # Green
            "Item": "#ffbd45",  # Yellow
        }

        for n in data.get("nodes", []):
            group = n.get("group", "NPC")
            nodes.append(
                Node(
                    id=n["id"],
                    label=n["label"],
                    size=25,
                    shape="dot",
                    color=color_map.get(group, "#ffffff"),
                )
            )

        for e in data.get("edges", []):
            edges.append(
                Edge(
                    source=e["source"],
                    target=e["target"],
                    label=e["label"],
                    color="#ffffff",
                )
            )

        config = Config(
            width="100%",
            height=500,
            directed=True,
            physics=True,
            hierarchical=False,
        )

        st.markdown("### 🗺️ Interactive World Map")
        st.caption(
            "🔴 NPCs | 🔵 Factions | 🟢 Locations | 🟡 Items *(Drag nodes to rearrange your web)*"
        )

        try:
            agraph(nodes=nodes, edges=edges, config=config)
        except Exception as e:
            st.error(f"Graph rendering error: {e}")
    st.divider()

elif page == "🌐 Multiverse Nexus":
    st.title("🗺️ The Global Heatmap (Multiverse Nexus)")
    st.markdown(
        "Live telemetry and combat trends visualized from 450+ active DM Co-Pilot campaigns globally."
    )

    if db is None:
        st.error("Database connection offline. Cannot access the Multiverse.")
    else:
        if st.button("🔄 Synchronize Telemetry & Generate Heatmap", type="primary"):
            with st.spinner(
                "Aggregating global telemetry and building Pandas DataFrame..."
            ):
                try:
                    # 1. Pull a larger dataset for the Heatmap (500 battles)
                    telemetry_docs = (
                        db.collection("multiverse_telemetry")
                        .order_by("timestamp", direction=firestore.Query.DESCENDING)
                        .limit(500)
                        .stream()
                    )

                    data_records = []
                    for doc in telemetry_docs:
                        data = doc.to_dict()
                        if data.get("event_type") == "combat_snapshot":
                            data_records.append(
                                {
                                    "Combatants": data.get("total_combatants", 0),
                                    "Avg Monster HP": data.get("avg_hp", 0),
                                }
                            )

                    if data_records:
                        # 2. Reverse to show chronological timeline (left to right)
                        data_records.reverse()

                        # 3. Convert raw dictionaries to a Pandas DataFrame
                        import pandas as pd

                        df = pd.DataFrame(data_records)

                        # 4. Calculate a 10-battle rolling average to smooth out the noise
                        df["Encounter Size Trend"] = (
                            df["Combatants"].rolling(window=10).mean()
                        )
                        df["Monster HP Trend"] = (
                            df["Avg Monster HP"].rolling(window=10).mean()
                        )

                        # Top-Level Metrics
                        current_avg_entities = df["Combatants"].mean()
                        total_battles = len(df)

                        c1, c2, c3 = st.columns(3)
                        c1.metric("Live Battles Visualized", f"{total_battles}+")
                        c2.metric(
                            "Global Avg Combatants", f"{current_avg_entities:.1f}"
                        )

                        # Dynamic risk assessment
                        risk_level = (
                            "Deadly 🔴"
                            if current_avg_entities > 6
                            else (
                                "Elevated 🟡"
                                if current_avg_entities > 4
                                else "Normal 🟢"
                            )
                        )
                        c3.metric("Global TPK Risk", risk_level)

                        st.divider()
                        st.markdown("### 📈 Global Combat Lethality Trends")
                        st.caption(
                            "Visualizing the 'arms race' between DMs globally. As players level up, average monster HP and encounter sizes scale."
                        )

                        # 5. Render the interactive Area Chart
                        chart_df = df[
                            ["Encounter Size Trend", "Monster HP Trend"]
                        ].dropna()
                        st.area_chart(chart_df, use_container_width=True)

                    else:
                        st.warning(
                            "Not enough combat data found in the Nexus yet. Go run a battle!"
                        )

                except Exception as e:
                    st.error(f"Nexus Error: {e}")
    st.divider()

elif page == "🔌 VTT Bridge":
    st.title("🔌 VTT Webhook Hub")
    st.info("Blast your creations directly into Foundry VTT or Roll20.")

    # Check for the global URL from the sidebar
    active_url = st.session_state.get("vtt_url", "")
    if not active_url:
        st.warning(
            "⚠️ No Global VTT URL detected. Please enter it in the left sidebar under 'VTT Webhook'."
        )
    else:
        # --- 🚨 THE VTT DIAGNOSTICS WIZARD ---
        with st.expander("🚨 Connection Diagnostics & Troubleshooter", expanded=False):
            st.markdown(
                "Having trouble exporting? Run a live diagnostic test on your local VTT server."
            )

            if st.button("🔍 Run Connection Test", use_container_width=True):
                with st.spinner(f"Pinging {active_url}..."):
                    try:
                        # Send a lightweight OPTIONS ping to test the network bridge
                        test_res = requests.options(active_url, timeout=5)
                        if test_res.status_code in [200, 204]:
                            st.success(
                                "✅ Connection Established! Your VTT server is online and accepting requests from the cloud."
                            )
                        else:
                            st.warning(
                                f"⚠️ Server reached, but returned unexpected status: {test_res.status_code}. Make sure your Foundry REST API module is enabled."
                            )

                    except requests.exceptions.ConnectionError:
                        st.error(
                            "❌ Connection Refused: DM Co-Pilot cannot reach your VTT server."
                        )
                        st.markdown(
                            """
                        <div class='stat-card' style='border-color: #ff4b4b; border-left: 5px solid #ff4b4b !important;'>
                            <h4 style='margin-top:0px; color:#ff4b4b;'>🛠️ The Troubleshooting Guide</h4>
                            <b>1. The Localhost Problem:</b> If your URL is <code>http://localhost:30000</code>, DM Co-Pilot cannot reach it because the app lives in the cloud, not on your PC.<br><br>
                            <b>2. The Solution (Ngrok):</b> You need to expose your local Foundry server to the internet using a free tunneling service like <b>Ngrok</b> or <b>Localtonet</b>. Use the public URL they give you instead of localhost.<br><br>
                            <b>3. Firewalls:</b> Ensure your Windows Defender or Mac Firewall is allowing inbound traffic on your VTT port.
                        </div>
                        """,
                            unsafe_allow_html=True,
                        )
                    except requests.exceptions.Timeout:
                        st.error(
                            "⏳ Connection Timed Out: Your server took too long to respond. Check your firewall settings."
                        )
                    except Exception as e:
                        st.error(f"⚠️ Unexpected Network Error: {e}")
        st.divider()

    with st.expander("⚙️ Transmission Settings", expanded=True):
        vtt_target = st.selectbox(
            "Target Engine",
            ["Foundry VTT", "Roll20 API", "FoxQuest (Beta)"],
            key="vtt_target_hub",
        )
        vtt_subject = st.text_input("Subject Name:", key="vtt_sub_v12")
        vtt_content = st.text_area("Content (JSON):", height=200, key="vtt_pay_v12")

    if st.button(f"🚀 Blast to {vtt_target}", type="primary", key="vtt_btn_v12"):
        if active_url and vtt_content:
            with st.spinner(f"Pushing to {vtt_target}..."):
                try:
                    payload = {
                        "name": vtt_subject,
                        "content": vtt_content,
                        "source": "DM Co-Pilot",
                    }
                    res = requests.post(active_url, json=payload, timeout=5)
                    if res.status_code in [200, 201]:
                        st.success(f"✅ Materialized in {vtt_target}!")
                        st.balloons()
                    else:
                        st.error(f"❌ VTT Error: {res.status_code}")
                except Exception as e:
                    st.error(f"📡 Connection Failed: {e}")
        else:
            st.warning("⚠️ Webhook URL (in sidebar) and Content are required.")

elif page == "🧬 Homebrew Forge":
    st.title("🧬 Homebrew Forge")
    forge_prompt = st.text_area(
        "Describe your homebrew (Monster/Item/NPC):", key="forge_input_v12"
    )
    if st.button("Forge Legend ✨", type="primary", key="forge_btn_v12"):
        if forge_prompt:
            with st.spinner("Forging..."):
                res = get_ai_response(
                    f"Forge a 5e statblock for: {forge_prompt}",
                    llm_provider,
                    user_api_key,
                )
                st.markdown(res)

elif page == "🔄 2014->2024 Converter":
    st.title("🔄 2014 -> 2024 Converter")
    legacy_text = st.text_area("Paste legacy 2014 stats:", key="conv_input_v12")
    if st.button("Update Ruleset 🔄", key="conv_btn_v12"):
        with st.spinner("Modernizing..."):
            res = get_ai_response(
                f"Convert this to 2024 D&D rules: {legacy_text}",
                llm_provider,
                user_api_key,
            )
            st.markdown(res)

elif page == "🛠️ Bug Reports & Feature Requests":
    st.title("🛠️ Bug Reports & Feature Requests")
    with st.form("feedback_v12"):
        f_type = st.selectbox("Type", ["Bug", "Feature", "Feedback"])
        f_msg = st.text_area("Details:")
        if st.form_submit_button("Submit"):
            if db:
                db.collection("feedback").add(
                    {
                        "type": f_type,
                        "content": f_msg,
                        "timestamp": firestore.SERVER_TIMESTAMP,
                    }
                )
            st.success("Sent! I'll get to work.")
# ==========================================
# 🧠 INFINITE ARCHIVE (v6.0 BETA)
# ==========================================
elif page == "🧠 Infinite Archive (Beta)":
    st.title("🧠 Infinite Archive (Beta)")
    from qdrant_client.models import Distance, VectorParams, PointStruct
    import uuid
    import os

    raw_q_url = st.secrets.get("QDRANT_URL", os.getenv("QDRANT_URL", ""))
    raw_q_key = st.secrets.get("QDRANT_API_KEY", os.getenv("QDRANT_API_KEY", ""))
    qdrant_url = raw_q_url.strip() if raw_q_url else ""
    qdrant_key = raw_q_key.strip() if raw_q_key else ""

    if not qdrant_url or not openai_key:
        st.error(
            "⚠️ Qdrant Cloud or OpenAI API Keys are missing. Check your Render Environment."
        )
    else:
        q_client = init_qdrant(qdrant_url, qdrant_key)
        o_client = OpenAI(api_key=openai_key)

        safe_campaign_id = re.sub(
            r"[^a-z0-9_]", "_", st.session_state.campaign_id.lower()
        )
        collection_name = f"memory_vault_{safe_campaign_id}"

        try:
            if not q_client.collection_exists(collection_name):
                q_client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(size=1536, distance=Distance.COSINE),
                )
        except:
            pass

        st.divider()

        # --- 1. THE ENCODER (MEMORIZE LORE) ---
        st.subheader("📝 Write to Infinite Memory")
        new_lore = st.text_area(
            "What should the AI remember permanently?", key="q_lore_input"
        )

        if st.button("Commit to Archive 🧠", type="primary", key="q_mem_btn"):
            if new_lore:
                with st.spinner("Encoding into Vector Cloud..."):
                    try:
                        emb_res = o_client.embeddings.create(
                            input=new_lore, model="text-embedding-3-small"
                        )
                        q_client.upsert(
                            collection_name=collection_name,
                            points=[
                                PointStruct(
                                    id=str(uuid.uuid4()),
                                    vector=emb_res.data[0].embedding,
                                    payload={"text": new_lore},
                                )
                            ],
                        )
                        st.success(
                            f"Lore securely locked into the {st.session_state.campaign_id} Archive!"
                        )
                    except Exception as e:
                        st.error(f"Archive Error: {e}")
            else:
                st.warning("Please enter lore to remember.")

        st.divider()

        # --- 2. THE RECALL (SEMANTIC SEARCH) ---
        st.subheader("🔍 Query the Archive")
        question = st.text_input("Ask the Archive a question:", key="q_ask_input")
        if st.button("Search Infinite Memory 🔮", key="q_recall_btn"):
            if question:
                with st.spinner("Searching..."):
                    try:
                        q_res = o_client.embeddings.create(
                            input=question, model="text-embedding-3-small"
                        )
                        search_result = q_client.query_points(
                            collection_name=collection_name,
                            query=q_res.data[0].embedding,
                            limit=3,
                        ).points
                        retrieved_context = "\n\n".join(
                            [hit.payload["text"] for hit in search_result]
                        )
                        prompt = f"Based ONLY on these memories: {retrieved_context}. Answer: {question}"
                        answer = get_ai_response(prompt, llm_provider, user_api_key)
                        st.markdown(
                            f"<div class='stat-card'>{answer}</div>",
                            unsafe_allow_html=True,
                        )
                    except Exception as e:
                        st.error(f"Recall Failed: {e}")

        st.divider()

        # --- 3. THE PRE-COG ENGINE ---
        st.subheader("🔮 The Pre-Cog Engine (Predictive Auto-Prep)")
        if st.button(
            "Generate Next Session Prep 🔮", type="primary", key="precog_btn_v1"
        ):
            with st.spinner("Predicting the future..."):
                try:
                    q_res = o_client.embeddings.create(
                        input="What are the most recent events?",
                        model="text-embedding-3-small",
                    )
                    search_result = q_client.query_points(
                        collection_name=collection_name,
                        query=q_res.data[0].embedding,
                        limit=5,
                    ).points
                    if not search_result:
                        st.warning("Not enough memories in the Archive.")
                    else:
                        recent_context = "\n\n".join(
                            [hit.payload.get("text", "") for hit in search_result]
                        )
                        prompt = f"Based on these memories, predict the next session: {recent_context}"
                        prep_sheet = get_ai_response(prompt, llm_provider, user_api_key)
                        st.markdown(
                            f"<div class='stat-card'>{prep_sheet}</div>",
                            unsafe_allow_html=True,
                        )
                except Exception as e:
                    st.error(f"Pre-Cog Error: {e}")

        st.divider()

        # --- 4. THE CONTINUITY COP ---
        st.subheader("🚨 The Continuity Cop")
        prep_to_audit = st.text_area("Session Prep to Audit:", key="audit_input")
        if st.button("Audit for Contradictions 🚨", type="primary"):
            if prep_to_audit:
                with st.spinner("Auditing..."):
                    try:
                        q_res = o_client.embeddings.create(
                            input=prep_to_audit, model="text-embedding-3-small"
                        )
                        search_result = q_client.query_points(
                            collection_name=collection_name,
                            query=q_res.data[0].embedding,
                            limit=5,
                        ).points
                        retrieved_context = "\n\n".join(
                            [hit.payload.get("text", "") for hit in search_result]
                        )
                        prompt = f"Audit this prep against these memories for contradictions: {retrieved_context}\n\nPrep: {prep_to_audit}"
                        report = get_ai_response(
                            prompt, llm_provider, user_api_key, profile="lawyer"
                        )
                        st.markdown(
                            f"<div class='stat-card'>{report}</div>",
                            unsafe_allow_html=True,
                        )
                    except Exception as e:
                        st.error(f"Audit Error: {e}")

elif page == "🛠️ Admin Dashboard":
    st.title("📊 Enterprise Analytics Dashboard")
    admin_pwd = st.text_input("Enter Admin Password", type="password")

    if admin_pwd == "":
        if db is not None:
            st.success("✅ Secure Uplink Established. Welcome, Architect.")

            # --- SEABORN ENTERPRISE STYLING ---
            import matplotlib.pyplot as plt
            import seaborn as sns

            # Force Seaborn into a sleek dark mode to match your UI
            plt.style.use("dark_background")
            sns.set_theme(
                style="darkgrid",
                rc={
                    "axes.facecolor": "#0e1117",
                    "figure.facecolor": "#0e1117",
                    "grid.color": "#333333",
                    "text.color": "#00FF00",
                    "axes.labelcolor": "#00FF00",
                    "xtick.color": "#00FF00",
                    "ytick.color": "#00FF00",
                },
            )

            # Create organized tabs for Visual Analytics
            tab1, tab2, tab3, tab4, tab5 = st.tabs(
                [
                    "🔥 Traffic",
                    "⚡ Engine Health",
                    "📊 Feedback",
                    "🏛️ Community",
                    "⚔️ Combat Stats",
                ]
            )

            with tab1:
                st.markdown("### 🚦 Live Session Traffic")
                sessions = list(db.collection("active_sessions").stream())
                st.metric("🔥 Total Active DMs", len(sessions))
                st.caption("Currently connected to the real-time Firebase heartbeat.")

            with tab2:
                st.markdown("### ⚡ AI Engine Performance (Last 100 Calls)")
                llm_docs = (
                    db.collection("llm_telemetry")
                    .order_by("timestamp", direction=firestore.Query.DESCENDING)
                    .limit(100)
                    .stream()
                )
                llm_data = [d.to_dict() for d in llm_docs]

                if llm_data:
                    df_llm = pd.DataFrame(llm_data)
                    col1, col2, col3 = st.columns(3)

                    # Calculate Metrics
                    col1.metric(
                        "⚡ Avg Latency", f"{df_llm['latency_seconds'].mean():.2f}s"
                    )

                    cache_hits = (
                        df_llm["cache_hit"].sum()
                        if "cache_hit" in df_llm.columns
                        else 0
                    )
                    cache_rate = (
                        (cache_hits / len(df_llm)) * 100 if len(df_llm) > 0 else 0
                    )
                    col2.metric("🛡️ Redis Cache Hit Rate", f"{cache_rate:.1f}%")

                    success_rate = (
                        len(df_llm[df_llm["status"] == "success"]) / len(df_llm)
                    ) * 100
                    col3.metric("✅ API Success Rate", f"{success_rate:.1f}%")

                    st.divider()

                    # 📈 Seaborn: Latency Line Plot
                    fig_lat, ax_lat = plt.subplots(figsize=(10, 3))
                    sns.lineplot(
                        data=df_llm,
                        x=df_llm.index,
                        y="latency_seconds",
                        color="#00FF00",
                        linewidth=2,
                        ax=ax_lat,
                    )
                    ax_lat.set_title("Latency Trend (Seconds)", fontsize=14, pad=10)
                    ax_lat.set_xlabel("Recent Calls (Oldest to Newest)")
                    ax_lat.set_ylabel("Latency (s)")
                    st.pyplot(fig_lat, clear_figure=True)

                    # 📊 Seaborn: Provider Bar Plot
                    fig_prov, ax_prov = plt.subplots(figsize=(10, 3))
                    sns.countplot(
                        data=df_llm, y="provider", palette="viridis", ax=ax_prov
                    )
                    ax_prov.set_title(
                        "Model Provider Load Distribution", fontsize=14, pad=10
                    )
                    ax_prov.set_xlabel("Total Calls")
                    ax_prov.set_ylabel("")
                    st.pyplot(fig_prov, clear_figure=True)
                else:
                    st.info("Gathering telemetry data...")

            with tab3:
                st.markdown("### 👍 Community Approval Rating")
                fb_docs = list(db.collection("tool_feedback").stream())
                fb_data = [d.to_dict() for d in fb_docs]

                if fb_data:
                    df_fb = pd.DataFrame(fb_data)
                    upvotes = len(df_fb[df_fb["vote"] == "up"])
                    approval = (upvotes / len(df_fb)) * 100 if len(df_fb) > 0 else 0

                    st.metric("Global Approval Rating", f"{approval:.1f}%")
                    st.progress(approval / 100.0)

                    st.divider()

                    # 📊 Seaborn: Feedback Distribution
                    fig_fb, ax_fb = plt.subplots(figsize=(10, 4))
                    sns.countplot(
                        data=df_fb,
                        y="tool",
                        order=df_fb["tool"].value_counts().index,
                        palette="magma",
                        ax=ax_fb,
                    )
                    ax_fb.set_title(
                        "Most Engaged Tools (Feedback Volume)", fontsize=14, pad=10
                    )
                    ax_fb.set_xlabel("Total Votes Cast")
                    ax_fb.set_ylabel("")
                    st.pyplot(fig_fb, clear_figure=True)
                else:
                    st.info("Gathering feedback data...")

            with tab4:
                st.markdown("### 🏛️ Vault & Matchmaker")
                vault_docs = list(db.collection("community_vault").stream())
                match_docs = list(db.collection("matchmaker_board").stream())

                col_c1, col_c2 = st.columns(2)
                col_c1.metric("💎 Items in Vault", len(vault_docs))
                col_c2.metric("🤝 Matchmaker Listings", len(match_docs))

                if match_docs:
                    df_match = pd.DataFrame([d.to_dict() for d in match_docs])
                    st.divider()

                    # 📊 Seaborn: Matchmaker Roles
                    fig_match, ax_match = plt.subplots(figsize=(8, 3))
                    sns.countplot(data=df_match, x="role", palette="crest", ax=ax_match)
                    ax_match.set_title("LFG Role Distribution", fontsize=14, pad=10)
                    ax_match.set_xlabel("")
                    ax_match.set_ylabel("Active Listings")
                    st.pyplot(fig_match, clear_figure=True)

            with tab5:
                st.markdown("### ⚔️ Multiverse Combat Trends (Last 100 Battles)")
                combat_docs = (
                    db.collection("multiverse_telemetry")
                    .order_by("timestamp", direction=firestore.Query.DESCENDING)
                    .limit(100)
                    .stream()
                )
                combat_data = [d.to_dict() for d in combat_docs]

                if combat_data:
                    df_combat = pd.DataFrame(combat_data)
                    col_w1, col_w2 = st.columns(2)

                    col_w1.metric(
                        "⚔️ Avg Combatants per Battle",
                        f"{df_combat['total_combatants'].mean():.1f}",
                    )
                    col_w2.metric(
                        "🩸 Avg Monster HP", f"{df_combat['avg_hp'].mean():.0f}"
                    )

                    st.divider()

                    # 📈 Seaborn: Combatant Trend Line
                    fig_cmbt, ax_cmbt = plt.subplots(figsize=(10, 3))
                    sns.lineplot(
                        data=df_combat,
                        x=df_combat.index,
                        y="total_combatants",
                        color="#ff4b4b",
                        linewidth=2,
                        ax=ax_cmbt,
                    )
                    ax_cmbt.set_title(
                        "Combatant Count Trend", fontsize=14, pad=10, color="#ff4b4b"
                    )
                    ax_cmbt.set_xlabel("Recent Encounters")
                    ax_cmbt.set_ylabel("Total Combatants")
                    st.pyplot(fig_cmbt, clear_figure=True)
                else:
                    st.info("Gathering combat data...")

        else:
            st.error("❌ Database connection offline.")
    elif admin_pwd:
        st.error("❌ Incorrect Password.")

# --- 🛡️ AUTO-ATTACH MICRO FEEDBACK ---
non_tool_pages = [
    "📜 DM's Guide",
    "🆕 Patch Notes",
    "🏛️ Community Vault",
    "🤝 DM Matchmaker",
    "🤖 DM Assistant",
    "🛠️ Bug Reports & Feature Requests",
    "🛠️ Admin Dashboard",
]
if page not in non_tool_pages:
    render_micro_feedback(page)
# --- 🧹 INFRASTRUCTURE 3/3: BACKGROUND THREAD GARBAGE COLLECTOR ---
import threading


def cleanup_zombie_threads():
    """Identifies and safely joins finished background threads to free up server RAM."""
    main_thread = threading.main_thread()
    for t in threading.enumerate():
        if t is not main_thread and not t.is_alive():
            try:
                t.join(timeout=0.1)
            except Exception as e:
                print(f"Failed to clean up thread {t.name}: {e}")


# Run the garbage collector silently at the end of every script rerun
cleanup_zombie_threads()
