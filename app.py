
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
            df = pd.read_csv("monsters.csv")
            return df
        except FileNotFoundError:
            return None

    @st.cache_data
    def load_spell_data():
        try:
            df = pd.read_csv("spells.csv")
            return df
        except FileNotFoundError:
            return None

    monster_df = load_monster_data()
    spell_df = load_spell_data()

    # --- SIDEBAR NAVIGATION ---
    st.sidebar.title("🐉 DM Co-Pilot")
    st.sidebar.markdown("Your all-in-one Campaign Management Platform.")
    st.sidebar.markdown("---")
    st.sidebar.subheader("🏰 The Deep-Delver's Grimoire")
    st.sidebar.write("Share your generated loot and NPCs with other DMs!")
    st.sidebar.markdown("[**💬 Join the Discord Community**](https://discord.gg/6gS3sFvZed)")

    # --- ENGINE SETTINGS ---
    st.sidebar.markdown("---")
    st.sidebar.subheader("⚙️ Engine Settings")
    llm_provider = st.sidebar.radio("Processing Engine", ["☁️ Groq (Cloud)", "💻 Ollama (Local)"])

    groq_api_key = ""
    local_model = ""

    if llm_provider == "☁️ Groq (Cloud)":
        groq_api_key = st.sidebar.text_input("Enter Groq API Key:", type="password")
    else:
        local_model = st.sidebar.selectbox("Select Local Model", ["llama3.1", "llama3", "mistral"])

    # --- MAIN NAVIGATION ---
    page = st.sidebar.radio(
        "Navigation",
        ["🤝 Campaign Matchmaker", "⚔️ Encounter Architect", "📜 Session Scribe", "🎭 Procedural Improv Tools", "🌍 Worldbuilder's Forge", "🎲 Skill Challenge Architect", "🧠 Digital DM Assistant"]
    )

    # --- AI HELPER FUNCTION ---
    def get_ai_response(prompt_text):
        if llm_provider == "☁️ Groq (Cloud)":
            if not groq_api_key:
                st.warning("⚠️ Please enter your Groq API key in the sidebar.")
                st.stop()
            try:
                from groq import Groq
                client = Groq(api_key=groq_api_key)
                chat_completion = client.chat.completions.create(
                    messages=[{"role": "user", "content": prompt_text}], 
                    model="llama-3.1-8b-instant"
                )
                return chat_completion.choices[0].message.content
            except Exception as e:
                st.error(f"Error: {e}")
                st.stop()
        else:
            try:
                import ollama
                response = ollama.chat(model=local_model, messages=[{"role": "user", "content": prompt_text}])
                return response['message']['content']
            except Exception as e:
                st.error(f"Ollama Error: {e}")
                st.stop()

    # --- PAGE 1: MATCHMAKER & LFG ---
    if page == "🤝 Campaign Matchmaker":
        st.title("🤝 Campaign Matchmaker")
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("🐉 DM Profile")
            dm_timezone = st.selectbox("DM Timezone", ["PST", "MST", "CST", "EST", "GMT"])
            dm_style = st.slider("DM Playstyle (0=Combat, 100=Roleplay)", 0, 100, 50)
            dm_pitch = st.text_area("Campaign Pitch", "A grimdark swamp campaign...")
        with col2:
            st.subheader("🛡️ Player Profile")
            player_timezone = st.selectbox("Player Timezone", ["PST", "MST", "CST", "EST", "GMT"])
            player_style = st.slider("Player Preference", 0, 100, 50)
            player_bio = st.text_area("Player Bio", "I love exploration...")

        if st.button("Run Matchmaker Engine", type="primary"):
            prompt = f"Analyze DM Pitch: {dm_pitch} and Player Bio: {player_bio}. Give a compatibility score."
            st.write(get_ai_response(prompt))

        st.markdown("---")
        st.subheader("📢 LFG Post Architect")
        with st.expander("Draft Your Recruitment Flyer"):
            lfg_sys = st.text_input("System", "D&D 5e")
            lfg_req = st.text_input("Requirements", "18+, Mic Required")
            if st.button("Generate LFG Post"):
                prompt = f"Write a Reddit LFG post for {lfg_sys}. Hook: {dm_pitch}. Requirements: {lfg_req}."
                res = get_ai_response(prompt)
                st.code(res, language="markdown") # st.code provides an easy "copy" button automatically!
                st.success("Post drafted! Use the copy icon in the top right of the box above.")

    # --- PAGE 2: ENCOUNTER ARCHITECT (WITH STAT BLOCKS) ---
    elif page == "⚔️ Encounter Architect":
        st.title("⚔️ Encounter Architect")
        tab1, tab2 = st.tabs(["🐉 Monster Vault", "🛠️ Homebrew CR & Stat Blocks"])
        
        with tab1:
            if monster_df is not None:
                st.data_editor(monster_df, use_container_width=True)
            else:
                st.error("monsters.csv missing.")

        with tab2:
            st.subheader("Homebrew Monster Forge")
            c1, c2, c3 = st.columns(3)
            h_name = st.text_input("Monster Name", "Swamp Terror")
            h_hp = c1.number_input("HP", value=50)
            h_ac = c2.number_input("AC", value=15)
            h_dpr = c3.number_input("DPR", value=12)
            
            if st.button("Calculate CR & Generate Stat Block"):
                cr = max(0, round(((h_hp/15) + ((h_ac-13)/2) + (h_dpr/5))/2))
                st.success(f"Estimated CR: {cr}")
                
                with st.spinner("Forging Stat Block..."):
                    prompt = f"Create a D&D 5e stat block for a CR {cr} monster named {h_name} with {h_hp} HP and {h_ac} AC. Include 2 thematic abilities."
                    block = get_ai_response(prompt)
                    st.markdown("### 📜 Formatted Stat Block")
                    st.code(block, language="markdown")

    # --- OTHER PAGES (TRUNCATED FOR BREVITY - KEEP YOUR EXISTING CODE FOR THESE) ---
    elif page == "🎭 Procedural Improv Tools":
        st.title("🎭 Procedural Improv Tools")
        with st.expander("🍻 Tavern Generator"):
            if st.button("Generate Tavern"):
                st.write(get_ai_response("Generate a D&D tavern name, barkeep, and rumor."))
    
    # [ADD YOUR REMAINING PAGES HERE FROM THE PREVIOUS FULL SCRIPT]