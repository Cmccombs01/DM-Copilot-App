import streamlit as st
import pandas as pd
import streamlit_analytics2 as streamlit_analytics
import json 
import PyPDF2 
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="DM Co-Pilot", page_icon="🐉", layout="wide")

# --- INITIALIZE GLOBAL STATES ---
if 'party_treasury' not in st.session_state:
    st.session_state.party_treasury = []
if 'initiative_list' not in st.session_state:
    st.session_state.initiative_list = []

# --- ANALYTICS SETUP ---
try:
    ANALYTICS_PASSWORD = st.secrets["analytics_password"]
except:
    ANALYTICS_PASSWORD = "local_test_password"

with streamlit_analytics.track(unsafe_password=ANALYTICS_PASSWORD):

    # --- LOAD DATA ---
    @st.cache_data
    def load_monster_data():
        try:
            return pd.read_csv("monsters.csv")
        except:
            return None

    @st.cache_data
    def load_spell_data():
        try:
            return pd.read_csv("spells.csv")
        except:
            return None

    monster_df = load_monster_data()
    spell_df = load_spell_data()

    # --- SIDEBAR ---
    st.sidebar.title("🐉 DM Co-Pilot")
    st.sidebar.markdown("[**💬 Join the Discord**](https://discord.gg/6gS3sFvZed)")
    
    llm_provider = st.sidebar.radio("Engine", ["☁️ Groq (Cloud)", "💻 Ollama (Local)"])
    groq_api_key = ""
    local_model = ""
    if llm_provider == "☁️ Groq (Cloud)":
        groq_api_key = st.sidebar.text_input("Groq API Key:", type="password")
    else:
        local_model = st.sidebar.selectbox("Local Model", ["llama3.1", "llama3"])

    page = st.sidebar.radio("Navigation", ["🤝 Campaign Matchmaker", "⚔️ Encounter Architect", "📜 Session Scribe", "🎭 Procedural Improv Tools", "🌍 Worldbuilder's Forge", "🎲 Skill Challenge Architect", "🧠 Digital DM Assistant"])

    # --- AI HELPER ---
    def get_ai_response(prompt_text):
        if llm_provider == "☁️ Groq (Cloud)":
            if not groq_api_key:
                st.warning("Enter API Key in sidebar.")
                st.stop()
            from groq import Groq
            client = Groq(api_key=groq_api_key)
            return client.chat.completions.create(messages=[{"role": "user", "content": prompt_text}], model="llama-3.1-8b-instant").choices[0].message.content
        else:
            import ollama
            return ollama.chat(model=local_model, messages=[{"role": "user", "content": prompt_text}])['message']['content']

    # --- PAGE 1: MATCHMAKER & LFG ---
    if page == "🤝 Campaign Matchmaker":
        st.title("🤝 Campaign Matchmaker")
        col1, col2 = st.columns(2)
        with col1:
            dm_pitch = st.text_area("Campaign Pitch", "A grimdark swamp campaign...")
            dm_style = st.slider("DM Style", 0, 100, 50)
        with col2:
            player_bio = st.text_area("Player Bio", "I love exploration...")
            player_style = st.slider("Player Style", 0, 100, 50)
            
        if st.button("Run Matchmaker"):
            st.write(get_ai_response(f"Match DM: {dm_pitch} with Player: {player_bio}"))

        st.markdown("---")
        st.subheader("📢 LFG Post Architect")
        lfg_sys = st.text_input("System", "D&D 5e")
        if st.button("Generate LFG Post"):
            res = get_ai_response(f"Write a Reddit LFG post for {lfg_sys}. Hook: {dm_pitch}")
            st.code(res, language="markdown")

    # --- PAGE 2: ENCOUNTER ARCHITECT ---
    elif page == "⚔️ Encounter Architect":
        st.title("⚔️ Encounter Architect")
        tab1, tab2 = st.tabs(["🐉 Monster Vault", "🛠️ Homebrew Stat Blocks"])
        with tab1:
            if monster_df is not None: st.data_editor(monster_df, use_container_width=True)
        with tab2:
            h_name = st.text_input("Monster Name", "Swamp Terror")
            h_hp = st.number_input("HP", value=50)
            h_ac = st.number_input("AC", value=15)
            h_dpr = st.number_input("DPR", value=12)
            if st.button("Forge Stat Block"):
                cr = max(0, round(((h_hp/15) + ((h_ac-13)/2) + (h_dpr/5))/2))
                block = get_ai_response(f"Create a 5e stat block for {h_name}, CR {cr}, {h_hp}HP, {h_ac}AC.")
                st.code(block, language="markdown")

    # --- PAGE 4: PROCEDURAL IMPROV (THE TRIPLE THREAT) ---
    elif page == "🎭 Procedural Improv Tools":
        st.title("🎭 Procedural Improv Tools")

        # 1. LOOT CURER & TREASURY
        st.subheader("💰 Loot & Treasury")
        col_l1, col_l2 = st.columns([2, 1])
        with col_l1:
            loot_loc = st.text_input("Location Found", "A sunken pirate ship")
        with col_l2:
            p_lvl = st.number_input("Party Level", 1, 20, 5)
            
        if st.button("Forge Loot"):
            item = get_ai_response(f"Generate one magic item for level {p_lvl} found in {loot_loc}.")
            st.session_state.last_loot = item
            st.info(item)
            
        if 'last_loot' in st.session_state:
            if st.button("📥 Send to Party Treasury"):
                st.session_state.party_treasury.append(st.session_state.last_loot)
                st.success("Locked in the vault!")

        with st.expander("🛡️ View Party Treasury"):
            if st.session_state.party_treasury:
                for i, itm in enumerate(st.session_state.party_treasury):
                    st.write(f"**Item {i+1}:**")
                    st.code(itm, language="markdown")
                if st.button("Clear Treasury"):
                    st.session_state.party_treasury = []; st.rerun()
            else: st.write("Vault empty.")

        # 2. LANDMARK GENERATOR
        st.markdown("---")
        st.subheader("🗺️ Wilderness Landmarks")
        env = st.selectbox("Environment", ["Forest", "Desert", "Mountain", "Swamp", "Tundra"])
        if st.button("Generate Landmark"):
            res = get_ai_response(f"Generate a unique point of interest in a {env} with a name, description, and hidden secret.")
            st.code(res, language="markdown")

        # 3. THE CHAOS BUTTON
        st.markdown("---")
        st.subheader("🎲 The Chaos Button")
        c1, c2 = st.columns(2)
        if c1.button("🔥 Critical Success (20)"):
            st.success(get_ai_response("Generate a heroic cinematic critical hit effect with a small 5e mechanical bonus."))
        if c2.button("💀 Critical Failure (1)"):
            st.error(get_ai_response("Generate a funny but dangerous critical fail effect with a small 5e mechanical penalty."))

    # --- REMAINDER OF PAGES ---
    elif page == "📜 Session Scribe":
        st.title("📜 Session Scribe")
        notes = st.text_area("Raw Notes")
        if st.button("Summarize"): st.write(get_ai_response(f"Summarize these D&D notes: {notes}"))

    elif page == "🌍 Worldbuilder's Forge":
        st.title("🌍 Worldbuilder's Forge")
        w_type = st.selectbox("Type", ["City", "Faction", "Deity"])
        if st.button("Forge Lore"): st.write(get_ai_response(f"Generate lore for a {w_type}"))

    elif page == "🎲 Skill Challenge Architect":
        st.title("🎲 Skill Challenge Architect")
        scen = st.text_area("Scenario", "Escaping a flood")
        if st.button("Generate Challenge"): st.write(get_ai_response(f"Create a 3-stage skill challenge for: {scen}"))

    elif page == "🧠 Digital DM Assistant":
        st.title("🧠 Digital DM Assistant")
        st.info("Upload Lore PDF or analyze notes below.")
        p_notes = st.text_area("Past Sessions")
        if st.button("Analyze"): st.write(get_ai_response(f"Analyze these campaign sessions for plot holes: {p_notes}"))