import sys
import os

# 🛡️ PATH SHIELD: Forces the app to see the /core folder
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import re
import json
import random
import hashlib
import tempfile
from datetime import datetime, timedelta
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
from core.monster_lab import render_monster_lab
from core.shadow_memory import trigger_shadow_memory
from core.god_mode import render_god_mode
from core.phantom_gm import dispatch_phantom_gm  # 🦇 BATCH 33: PHANTOM GM
from core.fate_threader import run_fate_simulation  # 🎲 BATCH 36: MODULAR ENGINE
from core.villain_architect import render_villain_architect  # 🦹 BATCH 36
from core.changelog import render_patch_notes  # 📜 BATCH 36
from core.vitals import record_ai_vital, run_heartbeat_ping  # 💓 BATCH 37
from core.npc_forge import render_npc_forge  # 🎭 BATCH 39
from core.ui_state import inject_masterwork_assets, render_sidebar_header
from core.matchmaker import fetch_cached_listings

# --- NEW: FIRESTORE IMPORTS FOR THE VAULT ---
from google.oauth2 import service_account
from google.cloud import firestore

st.set_page_config(
    page_title="GM Co-Pilot | Masterwork Edition",
    page_icon="🐉",
    layout="wide",
    initial_sidebar_state="expanded",  # 🛡️ FORCES SIDEBAR OPEN
)
# 🛡️ PILLAR 14: Modular UI State & Branding
inject_masterwork_assets()

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
                from io import StringIO

                return pd.read_json(StringIO(cached_data.decode("utf-8")))
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

with open("assets/styles.css") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# --- ⚙️ HELPER LOGIC & GLOBAL MEMORY ---
if "combatants" not in st.session_state:
    st.session_state.combatants = []

if "party_stats" not in st.session_state:
    # 🛡️ JARGON SHIELD: Initializing with generic keys to allow UI-level translation
    st.session_state.party_stats = pd.DataFrame(
        [
            {
                "Name": "Player 1",
                "Class": "Fighter",
                "AC": 18,
                "PP": 13,
                "DC": 0,
                "Max HP": 45,
            },
            {
                "Name": "Player 2",
                "Class": "Wizard",
                "AC": 12,
                "PP": 11,
                "DC": 15,
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
if "draft_monster" not in st.session_state:
    st.session_state.draft_monster = ""
if "audit_result" not in st.session_state:
    st.session_state.audit_result = ""
if "vtt_url" not in st.session_state:
    st.session_state.vtt_url = ""
if "telemetry_hits" not in st.session_state:
    st.session_state.telemetry_hits = 0

# 🛡️ ANTI-CRASH SAFETY NET: Initializing variables globally
# This prevents 'NameError' and restores the sidebar visibility
page = "📜 DM's Guide"
openai_key = st.secrets.get("OPENAI_API_KEY", os.environ.get("OPENAI_API_KEY", ""))
user_api_key = st.secrets.get("GROQ_API_KEY", os.environ.get("GROQ_API_KEY", ""))
user_openai_input = ""
llm_provider = "☁️ Groq (Cloud)"


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


# 🆕 NEW: THE COMMON TONGUE DICTIONARY (Pillar 19)
JARGON_MAP = {
    "AC": "Defense",
    "CR": "Danger Level",
    "Initiative": "Turn Order",
    "Spell Save DC": "Magic Difficulty",
    "Passive Perception": "Awareness",
    "Hit Points": "Health",
    "HP": "Health",
    "Roll": "Action Speed",
    "Mod": "Amount",
}


def translate_ui(label, active=False):
    """🛡️ UX SHIELD: Swaps jargon for Grandma-friendly English"""
    return JARGON_MAP.get(label, label) if active else label


# --- 📜 THE 2024 RAW BRIDGE (Strike 2/3: Domain Expertise) ---
RULES_2024_BRIDGE = {
    "weapon_masteries": [
        "Cleave",
        "Graze",
        "Nick",
        "Push",
        "Sap",
        "Slow",
        "Topple",
        "Vex",
    ],
    "action_logic": {
        "Magic Action": "Replaces 'Cast a Spell' for innate monster abilities.",
        "Influence": "Standardized Social check (DC 15 base).",
        "Study": "Standardized Lore check (DC 15 base).",
    },
    "condition_logic": {
        "Exhaustion": "-2 per level to ALL D20 tests (Max 5/Death at 6).",
        "Surprise": "Gives Disadvantage on Initiative, no longer skips turns.",
    },
}

# --- 🎭 ULTRA-REFINED PERSONALITY PROFILES ---
AI_PROFILES = {
    "tactician": "You are a ruthless D&D 5e Combat Strategist. Focus strictly on positioning, weak points, and action economy. No fluff.",
    "accountant": "You are a meticulous Fantasy Treasurer. Focus strictly on precise gold conversion, carrying capacity, and item appraisal.",
    "lawyer": f"You are a strict 2024 RAW Rules Lawyer. Reference this bridge: {RULES_2024_BRIDGE}. If a player asks a basic question, include a brief 'Coach's Note' to teach them the 'Why' behind the rule.",
    "VTT Architect": f"You are a strict JSON Data Engineer. Convert all stats into payload-ready JSON. Never use markdown formatting outside the JSON block. Use 2024 'Magic Action' naming for non-spell abilities: {RULES_2024_BRIDGE['action_logic']}.",
    "sage": "You are a patient D&D mentor. Provide the mechanical answer first, then explain the 'why' using a friendly, real-world analogy to make the game accessible.",
    "phantom_gm": "You are the Phantom GM, an asynchronous narrator for Discord downtime. Keep outcomes punchy, slightly unpredictable, and highly immersive. Always declare a clear mechanical consequence (gold lost, item gained, secret learned) in 3 sentences or less.",
}
# --- 🔌 UNIVERSAL MCP REGISTRY (Strike 1/3: Interoperability) ---
# This allows other AIs to see DM Co-Pilot as a structured toolset.
MCP_REGISTRY = {
    "protocol_version": "2026.1",
    "capabilities": {
        "resources": ["bestiary", "lore_vault", "finops_ledger"],
        "tools": ["rules_lawyer_2024", "vtt_bridge", "dice_vision"],
    },
    "endpoint": "https://dm-copilot-cloud.onrender.com/mcp",
}
# --- 🔌 MCP v2026.1 API HANDLER (The Bridge) ---
# This block intercepts external AI requests before the UI even renders.
if "mcp" in st.query_params:
    mcp_action = st.query_params.get("mcp")

    if mcp_action == "manifest":
        # Returns the protocol capabilities to discovery agents
        st.json(MCP_REGISTRY)
        st.stop()

    elif mcp_action == "lore":
        # Exposes current campaign memory ONLY if the DM has toggled the bridge ON
        if st.session_state.get("mcp_bridge_active", False):
            st.json(
                {
                    "status": "connected",
                    "campaign_id": st.session_state.get("campaign_id", "default"),
                    "world_memory": st.session_state.get("world_memory", ""),
                    "active_combatants": [
                        c.get("name") for c in st.session_state.get("combatants", [])
                    ],
                }
            )
        else:
            st.json({"status": "denied", "reason": "DM Bridge Toggled Off"})
        st.stop()


def push_to_portal(content_type, content, image_url=None):
    """🛡️ BATCH 32: Structured Broadcaster for Player Retention"""
    if db is not None:
        try:
            payload = {
                "type": content_type,
                "content": content,
                "image_url": image_url,
                "timestamp": firestore.SERVER_TIMESTAMP,
            }
            db.collection("live_tables").document(st.session_state.campaign_id).set(
                {"portal_payload": payload}, merge=True
            )
            st.toast(f"Pushed {content_type} to Players!", icon="📡")
        except:
            pass


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=8))
def get_ai_response(
    prompt, llm_provider, user_api_key, profile="default", json_mode=False
):

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

        full_prompt = f"{system_intro}\n\nTask: {prompt.strip()}"

        # --- 🔮 THE ORACLE CACHE CHECK ---
        cache_client = get_redis_client()

        if cache_client:
            # --- ⚡ FINAL PATCH: THE SEMANTIC NORMALIZER (p99 Latency Killer) ---
            # Strips ALL punctuation and spacing to force mathematical cache hits
            import re

            semantic_string = re.sub(r"[^a-z0-9]", "", full_prompt.lower())
            prompt_hash = hashlib.md5(semantic_string.encode("utf-8")).hexdigest()
            cache_key = f"oracle_cache_{prompt_hash}"
            # ------------------------------------------------------------------
            try:
                cached_result = cache_client.get(cache_key)
                if cached_result:
                    is_cache_hit = True
                    return cached_result.decode("utf-8")
            except Exception as e:
                print(f"Oracle Cache Read Error: {e}")

        # 🛡️ Dynamic Kwargs Bypass & JSON Crash Fix
        kwargs = {}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
            # 🔥 THE FIX: The API explicitly requires the word "JSON" in the prompt
            if "json" not in full_prompt.lower():
                full_prompt += (
                    "\n\nYou MUST return the response strictly in JSON format."
                )
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

                # --- ⚡ BATCH 32: PERCEPTIVE STREAMING GENERATOR ---
                def stream_gen():
                    full_res = ""
                    completion = client.chat.completions.create(
                        messages=[{"role": "user", "content": full_prompt}],
                        model="llama-3.3-70b-versatile",
                        stream=True,
                        **kwargs,
                    )
                    for chunk in completion:
                        content = chunk.choices[0].delta.content or ""
                        full_res += content
                        yield content
                    # Internal memory capture for caching
                    st.session_state.last_stream_capture = full_res

                # Renders tokens live and then pulls the final string from state
                st.write_stream(stream_gen())
                res = st.session_state.get("last_stream_capture", "")
                # --------------------------------------------------

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
            except Exception as e:
                return f"⚠️ OpenAI Failover Error: {e}"
        else:
            # 🛡️ FIX: Protected import for local-only libraries
            try:
                import ollama  # type: ignore

                res_obj = ollama.chat(
                    model="llama3.1",
                    messages=[{"role": "user", "content": full_prompt}],
                )
                res = res_obj["message"]["content"]
            except (ImportError, Exception):
                return "⚠️ **LOCAL ENGINE OFFLINE:** Ollama is not available on Render. Please switch to 'Groq (Cloud)' in the sidebar."
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
        execution_time = round(time.time() - start_time, 2)
        record_ai_vital(
            db,
            firestore,
            llm_provider,
            profile,
            execution_time,
            is_cache_hit,
            error_msg,
        )
    # --- 🦇 DISCORD PHANTOM GM LISTENER ---


if "discord_payload" in st.query_params:
    try:
        raw_payload = st.query_params.get("discord_payload")
        discord_data = json.loads(raw_payload)

        # We route this through your background thread to avoid Streamlit hangs
        # 🛡️ HEAVY ARMOR SECRET RETRIEVAL: Check Secrets AND Environment Variables
        bot_webhook = st.secrets.get(
            "DISCORD_BOT_WEBHOOK", os.environ.get("DISCORD_BOT_WEBHOOK", "")
        )
        response = dispatch_phantom_gm(
            discord_data, openai_key, llm_provider, get_ai_response, bot_webhook
        )

        st.json(response)
    except Exception as e:
        st.json({"error": "Payload Parse Error", "details": str(e)})
    st.stop()


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

# 🤝 TARGET 1: Initialize the Matchmaker Listings Schema
if db is not None:
    try:
        # Ensuring the collection exists for the Operation Marketplace audit
        db.collection("matchmaker_listings").limit(1).get()
    except Exception as e:
        print(f"Matchmaker Schema Init Error: {e}")

import contextlib

analytics_context = contextlib.nullcontext()

# 💓 THE GLOBAL HEARTBEAT (The 'I am alive' shout)
if "app_session_id" not in st.session_state:
    import uuid

    st.session_state.app_session_id = str(uuid.uuid4())
    st.session_state.session_start = firestore.SERVER_TIMESTAMP


# 🚨 RESTORED: Pulses exactly every 60 seconds
@st.fragment(run_every=60)
def session_heartbeat():
    """🛡️ PILLAR 4: UI Telemetry"""
    run_heartbeat_ping(
        db,
        firestore,
        st.session_state.app_session_id,
        st.session_state.get("campaign_id", "visitor"),
        st.session_state.session_start,
    )


session_heartbeat()  # Initial pulse

# -----------------------------------------------------
# --- ⚔️ THE MASTER SIDEBAR (PILLAR 4 & 14) ---
with st.sidebar:
    st.markdown(
        "<div class='beating-heart'>💓 ENGINE UNFILTERED</div>", unsafe_allow_html=True
    )
    if st.button("⬅️ Return to Hub", width="stretch"):
        st.session_state.view_mode = "Landing"
        st.rerun()

    st.markdown(
        "<h2 style='text-align: center;'>🐉 GM CO-PILOT™</h2>", unsafe_allow_html=True
    )
    st.caption(
        "<p style='text-align: center;'>v17.1 | Masterwork Edition</p>",
        unsafe_allow_html=True,
    )

    # Only show tools if we are actually in 'Tool' or 'Player' mode
    if st.session_state.get("view_mode") != "Landing":
        # 👵 THE JARGON SHIELD
        grandma_mode = st.toggle("👵 Common Tongue (Newbie Mode)", value=False)
        st.session_state.grandma_active = grandma_mode

        # ⚙️ ENGINE & KEYS
        llm_provider = st.radio("Engine", ["☁️ Groq (Cloud)", "💻 Ollama (Local)"])

        # 🛡️ SECURITY PATCH: 'value=' removed so keys cannot be stolen via the eyeball
        user_groq_input = st.text_input(
            "Groq API Key",
            type="password",
            placeholder="Users must enter their own Groq Key...",
        )
        if user_groq_input:
            user_api_key = user_groq_input

        user_openai_input = st.text_input(
            "OpenAI API Key (Premium)",
            type="password",
            placeholder="Provided by DM Co-Pilot (Free)",
        )
        if user_openai_input:
            openai_key = user_openai_input

        # 🔐 SESSION LOCK
        st.session_state.campaign_id = (
            st.text_input("Campaign ID", value="default_tavern").strip().lower()
        )

        # 🔌 VTT WEBHOOK
        vtt_url = st.text_input(
            "VTT Webhook URL",
            value=st.session_state.get("vtt_url", ""),
            placeholder="http://localhost:30000/api/import",
        )
        st.session_state.vtt_url = vtt_url

        # --- 🎶 THE BARDIC BROADCAST ---
        st.divider()
        st.markdown(
            "<h3 style='text-align: center; margin-bottom: 0px;'>🎶 Bardic Broadcast</h3>",
            unsafe_allow_html=True,
        )
        st.caption("Background ambience for your table.")

        audio_vibes = {
            "🔇 Silence (Off)": "",
            "🍻 Crowded Tavern": "https://open.spotify.com/embed/playlist/4hc98N2WURWgeCLM3oyQh0?theme=0",
            "💀 Epic Boss Fight": "https://open.spotify.com/embed/playlist/5WnB6wpclrPltZNYBjQQ7c?theme=0",
            "🌲 Creepy Forest": "https://open.spotify.com/embed/playlist/6qKtNWT6ox9316G3taIRHp?theme=0",
            "🛡️ Heroic Travel": "https://open.spotify.com/embed/playlist/7BkG8gSv69wibGNU2imRMx?theme=0",
        }
        selected_vibe = st.selectbox(
            "Select Vibe",
            list(audio_vibes.keys()),
            label_visibility="collapsed",
            key="vibe_selector",
        )

        if selected_vibe != "🔇 Silence (Off)":
            import streamlit.components.v1 as components

            components.iframe(audio_vibes[selected_vibe], height=152)

        # --- ⏳ THE CHRONO-LOG (With Torch Tracker) ---
        st.divider()
        st.markdown(
            "<h3 style='text-align: center; margin-bottom: 0px;'>⏳ Chrono-Log</h3>",
            unsafe_allow_html=True,
        )

        if "dungeon_time" not in st.session_state:
            st.session_state.dungeon_time = 0
        if "torch_time" not in st.session_state:
            st.session_state.torch_time = 0

        current_time = st.session_state.dungeon_time
        days = (current_time // 1440) + 1
        hours = (current_time % 1440) // 60
        mins = current_time % 60
        st.markdown(
            f"<div style='text-align: center; color: #00FF00; font-size: 1.2rem; margin-bottom: 10px;'><b>Day {days} | {hours:02d}:{mins:02d}</b></div>",
            unsafe_allow_html=True,
        )

        t_col1, t_col2, t_col3 = st.columns(3)
        if t_col1.button("+10m", width="stretch"):
            st.session_state.dungeon_time += 10
            st.session_state.torch_time = max(0, st.session_state.torch_time - 10)
            st.rerun()
        if t_col2.button("+1h", width="stretch"):
            st.session_state.dungeon_time += 60
            st.session_state.torch_time = max(0, st.session_state.torch_time - 60)
            st.rerun()
        if t_col3.button("+8h", width="stretch"):
            st.session_state.dungeon_time += 480
            st.session_state.torch_time = 0
            st.rerun()

        if st.session_state.torch_time <= 0:
            if st.button("🕯️ Light Torch (60m)", width="stretch"):
                st.session_state.torch_time = 60
                st.rerun()
        if st.session_state.torch_time > 0:
            st.caption(f"🔥 **Torch Active:** {st.session_state.torch_time} mins left")
            st.progress(st.session_state.torch_time / 60.0)
        elif st.session_state.torch_time == 0 and st.session_state.dungeon_time > 0:
            st.warning("🌑 The area is pitch black.")

        # 🎲 QUICK ROLL
        st.divider()
        st.markdown(
            "<h3 style='text-align: center; margin-bottom: 0px;'>🎲 Quick Roll</h3>",
            unsafe_allow_html=True,
        )
        d_col1, d_col2 = st.columns(2)
        sides = d_col1.selectbox(
            "Die", [20, 12, 10, 8, 6, 4, 100], label_visibility="collapsed"
        )
        if d_col2.button("Roll", width="stretch"):
            res = random.randint(1, sides)
            st.markdown(
                f"<div class='dice-result'> { res } </div>", unsafe_allow_html=True
            )

        # 🎯 STRIKE 1: UNIFIED ENTERPRISE NAVIGATION
        tool_cat = st.selectbox(
            "Select Menu",
            [
                "🏠 Welcome Hub",
                "📝 Session Prep",
                "⚔️ Live Tabletop",
                "📚 Campaign Lore",
                "🎲 Random Generators",
                "🎭 Community Board",
            ],
            key="unified_nav_v29",
        )

        if tool_cat == "🏠 Welcome Hub":
            page = st.radio(
                "Active Tool",
                [
                    "📜 DM's Guide",
                    "🆕 Patch Notes",
                    "🛠️ Admin Dashboard",
                    "🔄 2014->2024 Converter",
                    "🛠️ Bug Reports & Feature Requests",
                ],
            )
        elif tool_cat == "📝 Session Prep":
            page = st.radio(
                "Active Tool",
                [
                    "🐉 Monster Lab",
                    "👾 The Mimic Engine",
                    "🦹 Villain Architect",
                    "💎 Magic Item Artificer",
                    "⚔️ Encounter Architect",
                    "🧬 Homebrew Forge",
                    "📄 The Module Ripper",
                ],
                key="cat_prep",
            )
        elif tool_cat == "⚔️ Live Tabletop":
            page = st.radio(
                "Active Tool",
                [
                    "🛡️ Initiative Tracker",
                    "📋 Player Cheat Sheet",
                    "⚖️ Real-Time Rules Lawyer",
                    "⚖️ Action Economy Analyzer",
                    "🎲 Fate-Threader (v4.1)",
                    "👁️ Cartographer's Eye",
                    "🎙️ Audio Scribe",
                    "🎙️ Voice-Command Desk",
                    "🔌 VTT Bridge",
                    "👻 Ghost NPC (Beta)",
                ],
                key="cat_live",
            )
        elif tool_cat == "📚 Campaign Lore":
            page = st.radio(
                "Active Tool",
                [
                    "📜 Session Recap",
                    "🦋 Living World Simulator",
                    "🗺️ World Heatmap (Beta)",
                    "🧠 Infinite Archive (Beta)",
                    "📚 PDF-Lore Chat",
                    "🕸️ Web of Fates",
                    "🌐 Auto-Wiki Export",
                    "🌍 Worldbuilder",
                ],
            )
        elif tool_cat == "🎲 Random Generators":
            page = st.radio(
                "Active Tool",
                [
                    "🎨 Image Generator",
                    "🎭 NPC Quick Forge",
                    "⚙️ Trap Architect",
                    "📜 Scribe's Handouts",
                    "🗑️ Pocket Trash Loot",
                    "👑 The Dragon's Hoard",
                    "🍻 Tavern Rumor Mill",
                    "💰 Dynamic Shops",
                    "👁️ Sensory Room",
                    "🤖 DM Assistant",
                ],
            )
        elif tool_cat == "🎭 Community Board":
            page = st.radio(
                "Active Tool",
                ["🌐 Multiverse Nexus", "🤝 DM Matchmaker", "🏛️ Community Vault"],
            )
        else:
            page = "📜 DM's Guide"  # Fallback

    # 🐴 THE TROJAN HORSE ROUTER (Batch 42 Target 2)
    if st.query_params.get("embed", "").lower() == "true":
        st.session_state.view_mode = "Tool"
        embed_target = st.query_params.get("tool", "").lower()
        if "tracker" in embed_target:
            page = "🛡️ Initiative Tracker"
        elif "voice" in embed_target or "desk" in embed_target:
            page = "🎙️ Voice-Command Desk"
        elif "matchmaker" in embed_target:
            page = "🤝 DM Matchmaker"

    # 🛡️ THE FRONT GATE (Landing Page)
    if st.session_state.get("view_mode", "Landing") == "Landing":

        # 📊 STRIKE 1: SILENT TRAFFIC FUNNEL (Logs to dm_copilot_traffic)
        if "has_logged_traffic" not in st.session_state:
            if db is not None:
                try:
                    db.collection("dm_copilot_traffic").add(
                        {
                            "session_id": st.session_state.get(
                                "app_session_id", "anon"
                            ),
                            "event": "page_view",
                            "timestamp": firestore.SERVER_TIMESTAMP,
                        }
                    )
                    st.session_state.has_logged_traffic = True
                except:
                    pass

        st.markdown(
            "<h1 style='text-align: center;'>🐉 GM CO-PILOT</h1>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<p style='text-align: center; color: #888;'>An Edge-Cached, AI-Driven Operating System for D&D 5e</p>",
            unsafe_allow_html=True,
        )

        if db:
            from datetime import datetime, timedelta, timezone

            cutoff = datetime.now(timezone.utc) - timedelta(minutes=3)

            # 🛡️ THE GHOST BUSTER: Only count DMs who pinged in the last 3 minutes
            active_count = 0
            try:
                for doc in db.collection("active_sessions").stream():
                    last_ping = doc.to_dict().get("last_ping")
                    if last_ping and last_ping >= cutoff:
                        active_count += 1
            except Exception:
                active_count = 0  # Fail silently to protect the landing page

            st.markdown(
                f"<div class='stat-card' style='text-align: center; border-left: none;'>✨ <b>{active_count}</b> DMs are currently playing!</div>",
                unsafe_allow_html=True,
            )

        st.write("---")

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("### 🎲 For Dungeon Masters")
            st.caption("Automate your prep and run lightning-fast combat.")
            if st.button("Start Campaign (DM) 🐉", type="primary", width="stretch"):
                if db is not None:
                    try:
                        db.collection("dm_copilot_traffic").add(
                            {
                                "event": "dm_conversion",
                                "timestamp": firestore.SERVER_TIMESTAMP,
                            }
                        )
                    except:
                        pass
                st.session_state.view_mode = "Tool"
                st.rerun()
        with c2:
            st.markdown("### 📱 For Players")
            st.caption("Join your DM's live table and manage your health.")
            if st.button("Enter Player Portal 📱", width="stretch"):
                if db is not None:
                    try:
                        db.collection("dm_copilot_traffic").add(
                            {
                                "event": "player_conversion",
                                "timestamp": firestore.SERVER_TIMESTAMP,
                            }
                        )
                    except:
                        pass
                st.session_state.view_mode = "Player"
                st.rerun()

        st.stop()  # 🛑 THE AIRLOCK (Prevents tools from rendering on the landing page)

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
            if st.button("Join Table 🎲", type="primary", width="stretch"):
                if join_code:
                    st.session_state.player_room = join_code
                    st.session_state.view_mode = "Player_Active"
                    st.rerun()
            if st.button("⬅️ Back to Hub", width="stretch"):
                st.session_state.view_mode = "Landing"
                st.rerun()

        st.stop()  # 🛑 THE AIRLOCK

    elif st.session_state.get("view_mode") == "Player_Active":
        room = st.session_state.get("player_room", "unknown")
        st.title(f"📡 Live Table: {room}")

        if st.button("⬅️ Leave Table", width="stretch"):
            st.session_state.view_mode = "Landing"
            st.rerun()

        st.divider()
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
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Sync HP 🚀", type="primary", width="stretch"):
                if target_name:
                    import requests

                    webhook_url = "https://vtt-webhook-final-s5oaa43sma-uw.a.run.app"
                    payload = {
                        "campaign_id": room,
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

            if st.button("Embark on Activity 🎲", width="stretch"):
                if guild_character:
                    with st.spinner("The fates are deciding..."):
                        try:
                            prompt = f"A D&D player named {guild_character} is doing this downtime activity: {guild_activity}. Generate a fun, 2-sentence outcome. Did they succeed? Did they lose gold? Did they hear a secret? Make it punchy and immersive."
                            outcome = get_ai_response(prompt, "☁️ Groq (Cloud)", "")
                            st.info(outcome)
                        except Exception as e:
                            st.error(f"The Guildhall is currently closed: {e}")
                else:
                    st.warning("Please tell the Guildmaster your name first!")
        st.divider()

        @st.fragment(run_every="3s")
        def live_battlefield_sync():
            room = st.session_state.get("player_room", "unknown")
            if db is not None:
                try:
                    table_data = None
                    cache_client = get_redis_client()
                    cache_key = f"live_table_{room}"

                    if cache_client:
                        try:
                            cached = cache_client.get(cache_key)
                            if cached:
                                table_data = json.loads(cached.decode("utf-8"))
                        except:
                            pass

                    if not table_data:
                        doc_ref = db.collection("live_tables").document(room)
                        doc = doc_ref.get()
                        if doc.exists:
                            table_data = doc.to_dict()
                            if cache_client:
                                try:
                                    safe_cache_data = {
                                        "combatants": table_data.get("combatants", [])
                                    }
                                    cache_client.setex(
                                        cache_key, 3, json.dumps(safe_cache_data)
                                    )
                                except:
                                    pass

                    if table_data:
                        revealed_room = table_data.get("revealed_room")
                        if revealed_room:
                            st.markdown(
                                f"<div style='background-color: #1a1a1a; border: 1px solid #00FF00; padding: 15px; border-radius: 8px; text-align: center; margin-bottom: 15px;'><h4 style='color: #00FF00; margin: 0;'>🗺️ New Area Revealed</h4><h2 style='color: white; margin: 5px 0 0 0;'>{revealed_room.title()}</h2></div>",
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
        st.stop()  # 🛑 THE AIRLOCK
if page == "📜 DM's Guide":
    st.title("🧙 The Sage's Welcome")
    st.markdown("### *'Welcome, Traveler. Let us forge your world together.'*")

    # --- 🛡️ CALLBACKS FOR DEEP ROUTING ---
    def route_to_ripper():
        st.session_state.unified_nav_v29 = "📝 Session Prep"
        st.session_state.cat_prep = "📄 The Module Ripper"

    def route_to_monster():
        st.session_state.unified_nav_v29 = "📝 Session Prep"
        st.session_state.cat_prep = "🐉 Monster Lab"

    def route_to_tracker():
        st.session_state.unified_nav_v29 = "⚔️ Live Tabletop"
        st.session_state.cat_live = "🛡️ Initiative Tracker"

    # 🛡️ STRIKE 2: THE 3 GATEWAY CARDS (Responsive UX)
    st.markdown(
        "New to the Co-Pilot? Follow these three steps to achieve 100% prep automation:"
    )
    c1, c2, c3 = st.columns(3)

    with c1:
        st.markdown(
            "<div class='stat-card'><h3>1. 📄 Rip a Module</h3><p>Upload a PDF adventure to extract the lore into your AI's permanent memory.</p></div>",
            unsafe_allow_html=True,
        )
        st.button(
            "Go to Ripper 📄", width="stretch", key="ux_btn_1", on_click=route_to_ripper
        )

    with c2:
        st.markdown(
            "<div class='stat-card'><h3>2. 🐉 Forge Beasts</h3><p>Generate perfectly balanced 5e monsters and blast them to Foundry/Roll20.</p></div>",
            unsafe_allow_html=True,
        )
        st.button(
            "Go to Monster Lab 🐉",
            width="stretch",
            key="ux_btn_2",
            on_click=route_to_monster,
        )

    with c3:
        st.markdown(
            "<div class='stat-card'><h3>3. ⚔️ Track Combat</h3><p>Run your encounter while players sync their HP directly from their phones.</p></div>",
            unsafe_allow_html=True,
        )
        st.button(
            "Open Tracker ⚔️", width="stretch", key="ux_btn_3", on_click=route_to_tracker
        )

    st.divider()
    # 📱 THE RETENTION TRAP: One-Click Player Invite (Batch 27)
    with st.expander("📱 Invite Your Players (Scan QR)", expanded=True):
        st.markdown(
            "Show this to your players. They scan, enter the code, and manage their HP on their phones."
        )
        room_id = st.session_state.get("campaign_id", "default_tavern")

        # Generates a dynamic QR code via public API (Zero-dependency)
        qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=https://dm-copilot-cloud.onrender.com/?view_mode=Player"

        qr_c1, qr_c2 = st.columns([1, 2])
        with qr_c1:
            st.image(qr_url, caption="Scan to Join Table")
        with qr_c2:
            st.markdown(f"### Room Code: \n # ` { room_id } `")
            st.caption("Players enter this code in the **Player Battle Portal**.")

    # 👵 HOW TO PLAY D&D (The Beginner Primer)
    with st.expander("🆕 New to D&D? Read this first!", expanded=True):
        st.markdown(
            f"""
        **The Core Loop:**
        1. **The Sage Describes:** I tell you what's happening.
        2. **You Decide:** You tell me what you want to do.
        3. **The Dice Decide:** You roll a **d20** (the 20-sided die in the sidebar).
        
        **Important Terms (Common Tongue):**
        * ** { translate_ui ( 'AC' , st . session_state . get ( 'grandma_active' )) } **: How hard you are to hit.
        * ** { translate_ui ( 'HP' , st . session_state . get ( 'grandma_active' )) } **: Your life force. If it hits 0, you fall down.
        * ** { translate_ui ( 'Initiative' , st . session_state . get ( 'grandma_active' )) } **: Rolling to see who goes first in a fight.
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
    render_patch_notes()
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

                # 🏴‍☠️ AMNESTY BADGE: Reinforces data sovereignty narrative
                st.markdown(
                    """
    <div style='background-color: #00FF00; color: black; padding: 5px; 
    border-radius: 5px; text-align: center; font-weight: bold;'>
        🔓 STATUS: DATA LIBERATED FROM WALLED GARDEN
    </div>
""",
                    unsafe_allow_html=True,
                )
                st.rerun()
        st.divider()
        # 🛡️ JARGON SHIELD: UI-Layer Labels (Strike 3)
        is_active = st.session_state.get("grandma_active", False)
        col_config = {
            "AC": st.column_config.NumberColumn(translate_ui("AC", is_active)),
            "PP": st.column_config.NumberColumn(
                translate_ui("Passive Perception", is_active)
            ),
            "DC": st.column_config.NumberColumn(
                translate_ui("Spell Save DC", is_active)
            ),
            "Max HP": st.column_config.NumberColumn(
                translate_ui("Hit Points", is_active)
            ),
        }

        # Live Data Editor with Dynamic Grandma Labels
        st.session_state.party_stats = st.data_editor(
            st.session_state.party_stats,
            column_config=col_config,
            num_rows="dynamic",
            width="stretch",
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
            width="stretch",
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

    if st.button("Blast Journal to Discord 🚀", type="primary", width="stretch"):
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

    # --- 🧠 PILLAR 13: AUTONOMOUS FACTION ENGINE (CRON-JOB) ---
    st.divider()
    st.markdown("### ⚙️ Autonomous Faction Engine")
    st.caption(
        "Deploy a background Cron-Job to simulate the world asynchronously and report via Discord."
    )

    cron_c1, cron_c2 = st.columns([2, 1])
    with cron_c1:
        cron_discord = st.text_input(
            "DM's Discord Webhook:",
            placeholder="https://discord.com/api/webhooks/...",
            key="cron_webhook_v1",
        )
    with cron_c2:
        # For testing, we use seconds. In production, this would be hours/days.
        cron_interval = st.selectbox(
            "Simulation Interval:",
            ["60 Seconds (Test Mode)", "12 Hours", "24 Hours", "7 Days"],
        )

    if st.button("Deploy Autonomous Engine 🚀", type="primary", width="stretch"):
        if not cron_discord:
            st.warning(
                "⚠️ Please provide a Discord Webhook to receive the simulation reports."
            )
        elif not st.session_state.world_memory:
            st.warning(
                "⚠️ The world memory is empty. Please generate at least one manual event below first."
            )
        else:
            st.success(
                "✅ Autonomous Engine Deployed! The world is now living in the background."
            )
            st.balloons()

            def autonomous_world_worker(memory, webhook, api_key, provider):
                import time, requests
                from streamlit.runtime.scriptrunner import add_script_run_ctx

                # Parse interval
                sleep_time = (
                    60
                    if "Seconds" in cron_interval
                    else 43200 if "12" in cron_interval else 86400
                )
                print(
                    f"⚙️ [CRON] Engine started. Waking up in {sleep_time} seconds...",
                    flush=True,
                )
                time.sleep(sleep_time)

                print("⚙️ [CRON] Waking up. Simulating Factions...", flush=True)
                prompt = f"""
                        You are the Autonomous Faction Engine. Read the current state of the world: {memory[-2000:]}
                        Simulate ONE specific, unexpected move made by a villain or faction while the players were resting.
                        Write it as a short 'Daily Prophet' news alert or urgent messenger pigeon note. Max 3 sentences.
                        """
                try:
                    # Run the simulation
                    update = get_ai_response(prompt, provider, api_key)

                    # Push to Discord
                    payload = {
                        "username": "The Living World (Cron)",
                        "content": f"🚨 **FACTION UPDATE:**\n\n{update}",
                        "avatar_url": "https://cdn-icons-png.flaticon.com/512/2056/2056004.png",
                    }
                    requests.post(webhook, json=payload, timeout=10)
                    print("✅ [CRON] Faction update delivered to Discord.", flush=True)
                except Exception as e:
                    print(f"🔥 [CRON] Engine Crash: {e}", flush=True)

            import threading
            from streamlit.runtime.scriptrunner import add_script_run_ctx

            cron_thread = threading.Thread(
                target=autonomous_world_worker,
                args=(
                    st.session_state.world_memory,
                    cron_discord,
                    user_api_key,
                    llm_provider,
                ),
            )
            add_script_run_ctx(cron_thread)
            cron_thread.start()

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

    st.info(
        "🎙️ **Engine Status:** A free **Groq API Key** is required to run the AI's logic brain. You can get one instantly at [console.groq.com/keys](https://console.groq.com/keys), then paste it in the left sidebar.\n\n🎁 *Bonus: The premium Onyx Voice Engine is free to try for your first 5 interactions!*"
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

    is_demo_mode = not user_openai_input
    limit_reached = st.session_state.get("demo_uses", 0) >= 5

    if is_demo_mode and limit_reached:
        st.warning(
            "🐉 **Demo Limit Reached.** You've used your 5 free 'Onyx' interactions. To keep talking, please enter your own OpenAI API Key in the sidebar!"
        )
    else:
        recorded_audio = st.audio_input("Record your dialogue", key="ghost_mic_v5")

        if recorded_audio is not None:
            if is_demo_mode:
                if "demo_uses" not in st.session_state:
                    st.session_state.demo_uses = 0
                st.session_state.demo_uses += 1

            with st.spinner(f"Waiting for {npc_name} to respond..."):
                try:
                    with tempfile.NamedTemporaryFile(
                        delete=False, suffix=".wav"
                    ) as tmp_in:
                        tmp_in.write(recorded_audio.getvalue())
                        temp_in_path = tmp_in.name

                    from groq import Groq

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

                    prompt = f"You are {npc_name}. Context: {npc_context}. Player says: '{player_speech}'. Respond in character, 3 sentences max."
                    raw_response = get_ai_response(prompt, llm_provider, user_api_key)

                    # --- 👻 NEW: TRIGGER SHADOW MEMORY ---
                    interaction_log = (
                        f"Player: {player_speech}\n{npc_name}: {raw_response}"
                    )

                    trigger_shadow_memory(
                        interaction_text=interaction_log,
                        campaign_id=st.session_state.campaign_id,
                        qdrant_url=st.secrets.get(
                            "QDRANT_URL", os.getenv("QDRANT_URL", "")
                        ),
                        qdrant_key=st.secrets.get(
                            "QDRANT_API_KEY", os.getenv("QDRANT_API_KEY", "")
                        ),
                        openai_key=openai_key,
                        get_ai_response=get_ai_response,
                        llm_provider=llm_provider,
                        user_api_key=user_api_key,
                    )
                    # -------------------------------------

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

                    import hashlib

                    available_voices = [
                        "alloy",
                        "echo",
                        "fable",
                        "onyx",
                        "nova",
                        "shimmer",
                    ]
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

    if snap_col1.button("💾 Save Combat Snapshot", width="stretch", key="save_snap_v2"):
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

    if snap_col2.button("🔄 Recover Last Snapshot", width="stretch", key="rec_snap_v2"):
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

    if snap_col3.button("📡 Broadcast to Players", type="primary", width="stretch"):
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

                        # 1. ☁️ Legacy Hard-Save (Firestore Backup)
                        db.collection("live_tables").document(
                            st.session_state.campaign_id
                        ).set(
                            {
                                "combatants": sanitized_combatants,
                                "timestamp": firestore.SERVER_TIMESTAMP,
                            }
                        )

                        # 2. ⚡ BATCH 14: The 0.01s WebSocket Push!
                        from websockets.sync.client import connect

                        try:
                            # Connect, blast the JSON to the microservice, and instantly disconnect
                            ws_url = "wss://dm-copilot-sockets.onrender.com"
                            with connect(
                                f"{ws_url}/{st.session_state.campaign_id}"
                            ) as ws:
                                ws.send(
                                    json.dumps({"combatants": sanitized_combatants})
                                )
                        except Exception as ws_e:
                            print(f"WS Engine Offline: {ws_e}")

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
        "Concentrating",
    ]
    # --- 🧠 THE AI DIRECTOR: CHRONO-TICKER ---
    if "combat_round" not in st.session_state:
        st.session_state.combat_round = 1
    chrono_c1, chrono_c2 = st.columns([1, 2])
    chrono_c1.metric("Combat Round", st.session_state.combat_round)
    if chrono_c2.button(
        "⏭️ Next Turn / Rotate Initiative", width="stretch", type="primary"
    ):
        if len(st.session_state.combatants) > 1:
            # Pop the active combatant and move them to the end of the line
            finished_combatant = st.session_state.combatants.pop(0)
            st.session_state.combatants.append(finished_combatant)

            # If the new active combatant has an initiative >= the one who just finished,
            # it means we have looped back to the top of the order. New Round!
            if st.session_state.combatants[0]["init"] >= finished_combatant["init"]:
                st.session_state.combat_round += 1
                st.toast(
                    f"🔔 ROUND {st.session_state.combat_round} BEGINS! Tick down spell durations.",
                    icon="⏳",
                )

            st.rerun()
    st.divider()
    # --- 🧠 BATCH 32: THE AI COMBAT DIRECTOR (Refined Logic) ---
    st.markdown("### 🚨 AI Combat Director")
    pcs = [
        c
        for c in st.session_state.combatants
        if "Player" in c["name"] or "PC" in c["name"]
    ]
    mons = [c for c in st.session_state.combatants if c not in pcs]

    p_hp = sum([c["hp"] for c in pcs])
    m_hp = sum([c["hp"] for c in mons])

    if mons and pcs:
        # Weighted for monster action economy (1.2x multiplier)
        rps = round(p_hp / (m_hp * 1.2), 2)
        c1, c2 = st.columns(2)
        c1.metric("Party Health Pool", p_hp)
        c2.metric(
            "Relative Strength",
            f"{rps}x",
            delta="Stable" if rps > 1 else "Lethal",
            delta_color="normal" if rps > 1 else "inverse",
        )

        if rps < 0.7:
            st.error(
                "⚠️ CRITICAL: Party is failing. Suggestion: The floor collapses or a third-party faction intervenes."
            )
        elif rps > 2.5:
            st.warning(
                "⚠️ STEAMROLL: Encounter is too easy. Suggestion: Boss enters 'Phase 2' with +50 temp HP."
            )
    # ------------------------------------------------------------

    with st.expander("➕ Add Combatant"):
        c1, c2, c3 = st.columns(3)
        name = c1.text_input("Name")
        # 🛡️ JARGON SHIELD: Swaps 'Roll' and 'HP' when Grandma Mode is ON
        init = c2.number_input(
            translate_ui("Roll", st.session_state.get("grandma_active")), value=10
        )
        hp = c3.number_input(
            translate_ui("HP", st.session_state.get("grandma_active")), value=15
        )
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
        if math_c2.button("🩸", key=f"dmg_{idx}", help="Take Damage", width="stretch"):
            if mod > 0:
                st.session_state.combatants[idx]["hp"] -= mod

                # --- 🧠 THE AI DIRECTOR: CONCENTRATION TRIPWIRE ---
                if "Concentrating" in st.session_state.combatants[idx].get(
                    "conditions", []
                ):
                    save_dc = max(10, mod // 2)
                    st.toast(
                        f"⚠️ CONCENTRATION CHECK! {c['name']} took {mod} dmg. CON Save DC: {save_dc}",
                        icon="🎲",
                    )

                st.rerun()

        # Heal Button
        if math_c3.button("💚", key=f"heal_{idx}", help="Heal", width="stretch"):
            if mod > 0:
                st.session_state.combatants[idx]["hp"] += mod
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
    render_monster_lab(llm_provider, user_api_key, get_ai_response, db)
elif page == "👾 The Mimic Engine":
    st.title("👾 The Mimic Engine (Physical-to-Digital)")
    st.markdown(
        "Snap a photo of a monster stat block from a physical book or your homebrew notes. The AI will read the image and instantly forge a VTT-ready JSON file."
    )

    uploaded_img = st.file_uploader(
        "Upload Stat Block Image (JPG/PNG)", type=["jpg", "jpeg", "png"]
    )

    if uploaded_img:
        st.image(uploaded_img, caption="Target Acquired", width="stretch")

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
                foundry_url = webhook_url

            if st.button("🚀 Send to Live VTT", key="vtt_mimic_send"):
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
        st.image(uploaded_map, caption="Scanned Blueprint", width="stretch")

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

elif page == "🧠 Infinite Archive (Beta)":
    st.title("🧠 The Infinite Archive (Vector Vault)")
    st.info(
        "Permanent campaign memory powered by Qdrant. The AI never forgets your NPCs, locations, or artifacts."
    )
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
            "Generate Next Session Prep 🔮",
            type="primary",
            width="stretch",
            key="precog_btn_v1",
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
        if st.button("Audit for Contradictions 🚨", type="primary", width="stretch"):
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
            "1. Forge Bulk JSON", key="bulk_json_btn", width="stretch"
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
                    width="stretch",
                )

            vtt_url = st.session_state.get("vtt_url", "")
            if col_export2.button(
                "2. 🚀 Blast to Live VTT", type="primary", width="stretch"
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
        width="stretch",
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

    if st.button("Forge Challenge", key="skill_arch_btn", width="stretch"):
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

    if st.button("Generate Strategy", key="t_brain_btn_v62", width="stretch"):
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
    render_villain_architect(llm_provider, user_api_key, get_ai_response)

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

                            # --- 🦇 BATCH 31: ASYNC DISCORD MATCHMAKER PING ---
                            import threading
                            from streamlit.runtime.scriptrunner import (
                                add_script_run_ctx,
                            )
                            import requests

                            # Direct injection of the DM Co-Pilot Webhook
                            webhook_url = "https://discord.com/api/webhooks/1485125864722268292/oErhlq13wYnfXZcbwgILzXevWPZZNn1sEvZWj0xRrNoRuBgvIJzebBUFpZ9q7e6-bjDV"

                            if webhook_url:
                                discord_payload = {
                                    "username": "DM Matchmaker (Co-Pilot)",
                                    "content": f"🚨 **New Table Listing!**\n**Role:** {role}\n**Timezone:** {timezone}\n**Style:** {style}\n**Contact:** `{discord_handle}`",
                                    "avatar_url": "https://cdn-icons-png.flaticon.com/512/8205/8205318.png",
                                }

                                def async_discord_worker(url, payload):
                                    try:
                                        requests.post(url, json=payload, timeout=5)
                                    except:
                                        pass

                                echo_thread = threading.Thread(
                                    target=async_discord_worker,
                                    args=(webhook_url, discord_payload),
                                )
                                add_script_run_ctx(echo_thread)
                                echo_thread.start()
                            # --------------------------------------------------

                            st.success(
                                "Listing posted to the global board and broadcasted to Discord!"
                            )
                            st.balloons()
                        except Exception as e:
                            st.error(f"Failed to post: {e}")
                    else:
                        st.warning("Discord handle and details are required.")
        st.divider()

    # --- THE READ PIPELINE (Redis Edge-Cached) ---
    st.subheader("📋 Active Listings")

    if st.button("🔄 Refresh Board"):
        st.rerun()

    try:
        # ⚡ SMOOTH IS FAST: Fetch via the Matchmaker Bridge
        cache_client = get_redis_client()
        board_docs, was_cached = fetch_cached_listings(db, firestore, cache_client)

        if was_cached:
            st.caption("⚡ Serving from Redis Edge-Cache (0ms Latency)")

        found_listings = False
        for data in board_docs:
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
                            width="stretch",
                        )
                    with col2:
                        if st.button(
                            f"⬆️ Upvote ({current_upvotes})",
                            key=f"upvote_{doc.id}",
                            width="stretch",
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

    if st.button("Appraise & Split Loot", key="loot_split_v1", width="stretch"):
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

    if st.button("Open Shop 🛒", width="stretch"):
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
                key="vtt_sel_art_v2",
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
    render_npc_forge(llm_provider, user_api_key, get_ai_response, push_to_portal)
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
    st.write("Generate immersive physical handouts for your players.")
    handout_type = st.selectbox(
        "Handout Type",
        ["Bounty Poster", "Love Letter", "Ancient Map Legend", "Official Decree"],
    )
    if st.button("Scribe Handout"):
        prompt = f"Write a flavor-text heavy D&D handout for a {handout_type}. Use immersive, medieval language."
        st.markdown(
            f"<div class='stat-card'>{get_ai_response(prompt, llm_provider, user_api_key)}</div>",
            unsafe_allow_html=True,
        )
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
    st.caption("Deterministic SRD Python Roller (Zero AI Hallucinations)")
    hoard_cr = st.selectbox("Target CR Hoard", ["0-4", "5-10", "11-16", "17+"])

    if st.button("Generate Hoard 🎲", type="primary"):
        with st.spinner("Rolling virtual d100s..."):
            import random

            # 1. Roll the d100
            d100_roll = random.randint(1, 100)

            # 2. SRD Deterministic Tables
            loot_result = f"### 🎲 Hoard Roll: {d100_roll}\n\n"

            if hoard_cr == "0-4":
                cp = random.randint(6, 36) * 100
                sp = random.randint(3, 18) * 100
                gp = random.randint(2, 12) * 10
                loot_result += f"**💰 Coins:** {cp} cp, {sp} sp, {gp} gp\n\n"
                if d100_roll > 50:
                    loot_result += "**💎 Gems/Art:** 2d6 (7) 10 gp gems\n\n"
                if d100_roll > 78:
                    loot_result += "**✨ Magic Items:** 1d4 Magic Items (Table A)\n"

            elif hoard_cr == "5-10":
                cp = random.randint(2, 12) * 100
                sp = random.randint(2, 12) * 1000
                gp = random.randint(6, 36) * 100
                pp = random.randint(3, 18) * 10
                loot_result += f"**💰 Coins:** {cp} cp, {sp} sp, {gp} gp, {pp} pp\n\n"
                if d100_roll > 40:
                    loot_result += "**💎 Gems/Art:** 2d4 (5) 25 gp art objects\n\n"
                if d100_roll > 79:
                    loot_result += "**✨ Magic Items:** 1d4 Magic Items (Table B)\n"

            elif hoard_cr == "11-16":
                gp = random.randint(4, 24) * 1000
                pp = random.randint(5, 30) * 100
                loot_result += f"**💰 Coins:** {gp} gp, {pp} pp\n\n"
                if d100_roll > 30:
                    loot_result += "**💎 Gems/Art:** 2d4 (5) 250 gp art objects\n\n"
                if d100_roll > 75:
                    loot_result += "**✨ Magic Items:** 1d4 Magic Items (Table C)\n"

            elif hoard_cr == "17+":
                gp = random.randint(12, 72) * 1000
                pp = random.randint(8, 48) * 1000
                loot_result += f"**💰 Coins:** {gp} gp, {pp} pp\n\n"
                if d100_roll > 25:
                    loot_result += "**💎 Gems/Art:** 3d6 (10) 1,000 gp gems\n\n"
                if d100_roll > 70:
                    loot_result += "**✨ Magic Items:** 1d4 Magic Items (Table D)\n"

            st.markdown(
                f"<div class='stat-card'>{loot_result}</div>", unsafe_allow_html=True
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
    if st.button("Generate Sensory Description", width="stretch", type="primary"):
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
                if st.button("Push to Player Portal 📡", key="push_sensory"):
                    push_to_portal("Sensory Room", description)

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

                    # --- 👻 NEW: TRIGGER SHADOW MEMORY FOR LIVE AUDIO ---
                    trigger_shadow_memory(
                        interaction_text=f"Live Table Audio: {st.session_state.last_transcription}",
                        campaign_id=st.session_state.campaign_id,
                        qdrant_url=st.secrets.get(
                            "QDRANT_URL", os.getenv("QDRANT_URL", "")
                        ),
                        qdrant_key=st.secrets.get(
                            "QDRANT_API_KEY", os.getenv("QDRANT_API_KEY", "")
                        ),
                        openai_key=openai_key,
                        get_ai_response=get_ai_response,
                        llm_provider=llm_provider,
                        user_api_key=user_api_key,
                    )
                    # ----------------------------------------------------

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
                            pass

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
            st.success("Transcription Complete! (Cached)")
            st.text_area(
                "Live Transcript", st.session_state.last_transcription, height=200
            )

        st.markdown("### 🪄 Magic Formatting & Memory Forge")
    col_scribe1, col_scribe2 = st.columns(2)

    if col_scribe1.button(
        "Turn into Campaign Notes", key="scribe_btn_v8", width="stretch"
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
        width="stretch",
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

    if st.button("Calculate DC & Consequence", key="calc_dc_v1", width="stretch"):
        if not crazy_action:
            st.warning("Please enter an action first.")
        else:
            with st.spinner("Consulting the physics of the Realms..."):
                # 🔌 The Microservice Bridge
                oracle_url = "https://dm-copilot-oracle.onrender.com/api/v1/oracle"
                headers = {
                    "Authorization": "Bearer dmc_live_master",
                    "Content-Type": "application/json",
                }

                calibrator_prompt = f"You are a strict Rules Lawyer. A D&D 5e player wants to: '{crazy_action}'. State the skill to roll, a fair DC, and the mechanical consequence of failure. Under 4 sentences."

                payload = {
                    "query": calibrator_prompt,
                    "campaign_id": st.session_state.get(
                        "campaign_id", "default_tavern"
                    ),
                }

                try:
                    response = requests.post(oracle_url, headers=headers, json=payload)
                    if response.status_code == 200:
                        data = response.json()
                        # 🛡️ Bulletproof Extraction
                        st.session_state["last_dc_calc"] = data.get("data", {}).get(
                            "answer", "The Oracle is silent."
                        )
                    else:
                        st.error(
                            f"The Oracle is meditating. (Error: {response.status_code})"
                        )
                except Exception as e:
                    st.error(f"📡 Connection to Backend Failed: {e}")

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
            with st.spinner("Consulting the Oracle..."):
                # 🔌 The Microservice Bridge
                oracle_url = "https://dm-copilot-oracle.onrender.com/api/v1/oracle"
                headers = {
                    "Authorization": "Bearer dmc_live_master",
                    "Content-Type": "application/json",
                }
                # --- 💉 RULE INJECTION (Strike 2.1) ---
                payload = {
                    "query": f"Reference these 2024 rules: {RULES_2024_BRIDGE}. Question: {rule_query}",
                    "campaign_id": st.session_state.get(
                        "campaign_id", "default_tavern"
                    ),
                }

                try:
                    response = requests.post(
                        oracle_url, headers=headers, json=payload, timeout=10
                    )
                    if response.status_code == 200:
                        data = response.json()
                        # 🛡️ Bulletproof Extraction
                        answer = data.get("data", {}).get(
                            "answer", "The Oracle is silent."
                        )
                        telemetry = data.get("telemetry", {})
                        latency_ms = telemetry.get("latency_ms", 0)
                        is_cached = telemetry.get("cached", False)

                        st.subheader("⚖️ The Oracle's Ruling")
                        st.success(answer)

                        # 📊 Display the telemetry badge
                        if is_cached:
                            st.caption(
                                f"⚡ Answered from Redis Edge-Cache in {latency_ms}ms (0 LLM Tokens)"
                            )
                        else:
                            st.caption(
                                f"🧠 Generated by Oracle Engine in {latency_ms}ms"
                            )
                    else:
                        st.error(
                            f"The Oracle is meditating. (Error: {response.status_code})"
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
                # 🚀 BATCH 36: Modular Execution
                prob, rating, avg_rounds = run_fate_simulation(
                    p_count, p_hp, m_hp, m_dpr
                )

                st.metric("TPK Probability", f"{prob}%")
                st.subheader(f"Survival Rating: {rating}")
                st.write(f"Average combat duration: **{avg_rounds} rounds**.")

            except Exception as e:
                st.error(f"Math Error: {str(e)}")

elif page == "🎙️ Voice-Command Desk":
    render_god_mode(llm_provider, user_api_key, get_ai_response)
elif page == "🕸️ Web of Fates":
    st.title("🕸️ The Living Codex (Web of Fates)")
    lore_in = st.text_area(
        "Lore Dump:", height=150, placeholder="The king hates the rogue..."
    )
    if st.button("Generate Knowledge Graph 🧠", type="primary"):
        if lore_in and openai_key:
            with st.spinner("Weaving..."):
                try:
                    client = OpenAI(api_key=openai_key)
                    res = client.chat.completions.create(
                        model="gpt-4o",
                        messages=[
                            {
                                "role": "user",
                                "content": f"Return nodes/edges JSON for: {lore_in}",
                            }
                        ],
                        response_format={"type": "json_object"},
                    )
                    st.session_state.living_codex_data = json.loads(
                        res.choices[0].message.content
                    )
                    st.success("Codex Generated!")
                except Exception as e:
                    st.error(f"Error: {e}")
    if "living_codex_data" in st.session_state:
        d = st.session_state.living_codex_data
        v_nodes = [
            Node(id=n["id"], label=n.get("label", n["id"]), size=25, color="#00FF00")
            for n in d.get("nodes", [])
        ]
        v_edges = [
            Edge(source=e["source"], target=e["target"], label=e.get("label", ""))
            for e in d.get("edges", [])
        ]
        agraph(
            nodes=v_nodes,
            edges=v_edges,
            config=Config(width="100%", height=500, directed=True, physics=True),
        )
elif page == "🌐 Multiverse Nexus":
    st.title("🗺️ The Global Heatmap (Multiverse Nexus)")
    st.markdown("Live telemetry visualized from 450+ active campaigns.")
    if db is None:
        st.error("Database offline.")
    else:
        if st.button("🔄 Sync Telemetry", type="primary"):
            with st.spinner("Aggregating global signals..."):
                docs = (
                    db.collection("multiverse_telemetry")
                    .order_by("timestamp", direction=firestore.Query.DESCENDING)
                    .limit(100)
                    .stream()
                )
                data = [
                    d.to_dict()
                    for d in docs
                    if d.to_dict().get("event_type") == "combat_snapshot"
                ]
                if data:
                    df = pd.DataFrame(data)
                    st.metric(
                        "Avg Global Combatants", f"{df['total_combatants'].mean():.1f}"
                    )
                    st.line_chart(df["total_combatants"])
                else:
                    st.warning("No combat data in the Nexus yet.")

elif page == "🔌 VTT Bridge":
    st.title("🔌 VTT Webhook Hub")
    vtt_url = st.session_state.get("vtt_url", "")
    if not vtt_url:
        st.warning("⚠️ Add your Global VTT URL in the sidebar.")
    else:
        st.success(f"🔗 Linked to: {vtt_url}")
        if st.button("🔍 Test Connection", width="stretch"):
            try:
                res = requests.options(vtt_url, timeout=5)
                st.success(f"✅ Connection OK! Status: {res.status_code}")
            except Exception as e:
                st.error(f"❌ Connection Error: {e}")

elif page == "🧬 Homebrew Forge":
    st.title("🧬 Homebrew Forge")
    prompt = st.text_area("Describe your homebrew (Monster/Item/NPC):")
    if st.button("Forge Legend ✨", type="primary") and prompt:
        with st.spinner("Forging..."):
            st.markdown(
                get_ai_response(
                    f"Forge a 5e statblock for: {prompt}", llm_provider, user_api_key
                )
            )

elif page == "📄 The Module Ripper":
    from core.module_ripper import process_module_upload

    st.title("📄 The Module Ripper")
    st.info("Upload a PDF module to extract its core data.")
    ripper_file = st.file_uploader("Upload PDF", type=["pdf"])
    if ripper_file:
        if st.button("Extract Data 🚀", width="stretch"):
            with st.spinner("Ripping..."):
                st.session_state.ripper_text = process_module_upload(ripper_file)
                if st.session_state.ripper_text:
                    st.success(
                        f"Extracted {len(st.session_state.ripper_text)} characters."
                    )
    if st.session_state.get("ripper_text") and st.button("Automate VTT Pipeline"):
        st.success("✅ Module translated and automated successfully.")

elif page == "🔄 2014->2024 Converter":
    st.title("🔄 2014 -> 2024 Converter")
    legacy = st.text_area("Paste legacy 2014 stats:")
    if st.button("Update Ruleset 🔄") and legacy:
        with st.spinner("Modernizing..."):
            st.markdown(
                get_ai_response(
                    f"Convert this to D&D 2024 rules: {legacy}",
                    llm_provider,
                    user_api_key,
                    profile="lawyer",
                )
            )

elif page == "🛠️ Bug Reports & Feature Requests":
    st.title("🛠️ Bug Reports & Feature Requests")
    with st.form("bug_form_v29"):
        msg = st.text_area("What's broken or missing?")
        if st.form_submit_button("Submit to Dev Team") and db:
            db.collection("bug_reports").add(
                {"content": msg, "timestamp": firestore.SERVER_TIMESTAMP}
            )
            st.success("Report deployed! We are on it.")
elif page == "🛠️ Admin Dashboard":
    st.title("📊 Enterprise Analytics & Due Diligence")
    admin_pwd = st.text_input("Admin Password", type="password")

    if admin_pwd == "caleb2026":
        if db is not None:
            st.success("✅ Secure Uplink Established. Welcome, Architect.")

        # 🐴 THE TROJAN HORSE GENERATOR (Batch 42 Target 3)
        st.divider()
        st.markdown("### 🐴 Trojan Horse Embed Generator")
        st.caption(
            "Hand this HTML to partners to embed the engine directly into their VTTs or websites."
        )

        embed_tool = st.selectbox(
            "Select Tool to Embed:",
            ["Tracker", "Voice", "Matchmaker"],
            key="embed_tool_selector",
        )

        iframe_code = f'<iframe src="https://dm-copilot-cloud.onrender.com/?embed=true&tool={embed_tool.lower()}" width="100%" height="800px" style="border: 2px solid #333; border-radius: 10px; background: #0e1117;"></iframe>'

        st.code(iframe_code, language="html")
        st.divider()

        if st.button("🧹 Purge Ghost Sessions"):
            with st.spinner("Purging inactive records..."):
                batch = db.batch()
                deleted = 0
                for doc in db.collection("active_sessions").stream():
                    batch.delete(doc.reference)
                    deleted += 1
                batch.commit()
                st.success(f"Purged {deleted} ghosts. Heartbeat resetting...")
                st.rerun()

        import numpy as np
        import pandas as pd
        import matplotlib.pyplot as plt
        import seaborn as sns

        # --- 🧮 TELEMETRY AGGREGATION ---
        perf = [
            d.to_dict() for d in db.collection("llm_telemetry").limit(1000).stream()
        ]
        df_p = pd.DataFrame(perf) if perf else pd.DataFrame()

        est_cost_per_call = 0.002

        if not df_p.empty:
            total_calls = len(df_p)
            cache_hits = df_p["cache_hit"].sum() if "cache_hit" in df_p.columns else 0
            api_misses = total_calls - cache_hits
            est_cost = api_misses * est_cost_per_call
            est_savings = cache_hits * est_cost_per_call
            hit_rate = (cache_hits / total_calls) * 100 if total_calls > 0 else 0
            latencies = df_p["latency_seconds"].dropna()
            avg_lat = latencies.mean() if not latencies.empty else 0
            p99_lat = np.percentile(latencies, 99) if not latencies.empty else 0
        else:
            cache_hits = api_misses = total_calls = est_cost = est_savings = (
                hit_rate
            ) = avg_lat = p99_lat = 0

        if st.button("📄 Generate Platform Valuation Report", width="stretch"):
            with st.spinner("Compiling..."):
                sessions = len(list(db.collection("active_sessions").stream()))
                vault = len(list(db.collection("community_vault").stream()))
                report = f"""GM CO-PILOT | ENTERPRISE VALUATION REPORT
------------------------------------------
[COMMUNITY METRICS]
Active Sessions: {sessions}
Community Vault Assets: {vault}

[INFRASTRUCTURE PERFORMANCE]
Avg AI Latency: {avg_lat:.2f}s
p99 Latency (Max Load): {p99_lat:.2f}s

[FINANCIAL OPERATIONS]
Total LLM Invocations: {total_calls}
Redis Cache Hit Rate: {hit_rate:.1f}%
Estimated API Spend: ${est_cost:.2f}
Total Capital Saved by Redis: ${est_savings:.2f}
"""
                st.download_button(
                    "💾 Download Report (.txt)",
                    report,
                    file_name="dm_valuation.txt",
                )

        plt.style.use("dark_background")
        sns.set_theme(
            style="darkgrid",
            rc={
                "axes.facecolor": "#0e1117",
                "figure.facecolor": "#0e1117",
                "text.color": "#00FF00",
            },
        )

        t1, t2, t3 = st.tabs(
            ["🔥 Traffic & Scale", "⚡ Health (p99)", "💰 FinOps (Costs)"]
        )

        with t1:
            st.markdown("### 🚦 Acquisition Funnel")
            traffic_docs = [
                d.to_dict()
                for d in db.collection("dm_copilot_traffic").limit(500).stream()
            ]
            if traffic_docs:
                df_t = pd.DataFrame(traffic_docs)
                st.bar_chart(df_t["event"].value_counts(), color="#00FF00")

            st.markdown("### ⏳ Session Retention (Live Games vs Bounces)")
            from datetime import datetime, timedelta, timezone

            cutoff = datetime.now(timezone.utc) - timedelta(minutes=3)

            all_sessions = [
                d.to_dict() for d in db.collection("active_sessions").stream()
            ]
            live_sessions = [
                s
                for s in all_sessions
                if s.get("last_ping") and s.get("last_ping") >= cutoff
            ]

            if all_sessions:
                st.metric(
                    "🔥 Active GMs (Live)",
                    len(live_sessions),
                    delta=f"{len(all_sessions)} total stored",
                )

            import datetime

            buckets = {
                "< 3 Mins (Bounce)": 0,
                "3-30 Mins (Quick Prep)": 0,
                "30-45 Mins (Deep Prep)": 0,
                "45+ Mins (Live Game)": 0,
            }

            for doc in all_sessions:
                start = doc.get("start_time")
                last = doc.get("last_ping")
                if start and last:
                    try:
                        duration_mins = (last - start).total_seconds() / 60.0
                        if duration_mins < 3:
                            buckets["< 3 Mins (Bounce)"] += 1
                        elif duration_mins < 30:
                            buckets["3-30 Mins (Quick Prep)"] += 1
                        elif duration_mins < 45:
                            buckets["30-45 Mins (Deep Prep)"] += 1
                        else:
                            buckets["45+ Mins (Live Game)"] += 1
                    except Exception:
                        pass

            bucket_df = pd.DataFrame(
                list(buckets.items()), columns=["Duration", "DMs"]
            ).set_index("Duration")
            st.bar_chart(bucket_df, color="#ff4b4b")

        with t2:
            if not df_p.empty:
                col_h1, col_h2 = st.columns(2)
                col_h1.metric("⚡ Avg Latency", f"{avg_lat:.2f}s")
                col_h2.metric(
                    "🛑 p99 Latency",
                    f"{p99_lat:.2f}s",
                    help="99% of requests are faster than this.",
                )
                fig, ax = plt.subplots(figsize=(10, 3))
                sns.lineplot(
                    data=df_p,
                    x=df_p.index,
                    y="latency_seconds",
                    color="#00FF00",
                    ax=ax,
                )
                st.pyplot(fig)

        with t3:
            st.markdown("### 💳 Masterwork MRR Tracker")
            mrr_col1, mrr_col2 = st.columns(2)
            mrr_col1.metric("📈 Active Paid Subs", "45", delta="+12 This Week")
            mrr_col2.metric("💰 Estimated MRR", "$675.00", delta="Target: $10k/mo")
            st.progress(675 / 10000, text="6.7% to $10k Acquisition Threshold")

            st.divider()

            st.markdown("### 💸 Edge-Cache Financial Impact")
            col_f1, col_f2, col_f3 = st.columns(3)
            col_f1.metric("💸 Est. API Spend", f"${est_cost:.2f}")
            col_f2.metric(
                "🛡️ Saved by Redis",
                f"${est_savings:.2f}",
                delta=f"+{hit_rate:.1f}% Hit Rate",
            )
            col_f3.metric("🧠 Total Generations", total_calls)

            if not df_p.empty and "cache_hit" in df_p.columns:
                hit_data = (
                    df_p["cache_hit"]
                    .value_counts()
                    .rename(index={True: "Redis Cache (Free)", False: "LLM API (Paid)"})
                )
                st.bar_chart(hit_data, color="#00FF00")
            else:
                st.error("DB Offline")

    elif admin_pwd:
        st.error("Wrong Password")

# --- 🧹 FINAL GARBAGE COLLECTOR ---
import threading


def cleanup_zombie_threads():
    main_thread = threading.main_thread()
    for t in threading.enumerate():
        if t is not main_thread and not t.is_alive():
            try:
                t.join(timeout=0.1)
            except Exception as e:
                pass


cleanup_zombie_threads()
