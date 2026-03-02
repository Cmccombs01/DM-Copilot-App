import streamlit as st
import pandas as pd
import streamlit_analytics2 as streamlit_analytics
import json 
import PyPDF2 
from datetime import datetime

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="DM Co-Pilot", page_icon="🐉", layout="wide")

# --- INITIALIZE GLOBAL SESSION LOG ---
# This keeps track of EVERYTHING generated in one text block
if 'session_log' not in st.session_state:
    st.session_state.session_log = f"--- DM Co-Pilot Session Log ({datetime.now().strftime('%Y-%m-%d')}) ---\n"
if 'party_treasury' not in st.session_state:
    st.session_state.party_treasury = []

# --- ANALYTICS SETUP ---
try:
    ANALYTICS_PASSWORD = st.secrets["analytics_password"]
except:
    ANALYTICS_PASSWORD = "local_test_password"

with streamlit_analytics.track(unsafe_password=ANALYTICS_PASSWORD):

    # --- DATA LOADING ---
    @st.cache_data
    def load_data(file):
        try: return pd.read_csv(file)
        except: return None

    monster_df = load_data("monsters.csv")

    # --- SIDEBAR ---
    st.sidebar.title("🐉 DM Co-Pilot")
    st.sidebar.markdown("[**💬 Join the Discord**](https://discord.gg/6gS3sFvZed)")
    
    llm_provider = st.sidebar.radio("Engine", ["☁️ Groq (Cloud)", "💻 Ollama (Local)"])
    groq_api_key = st.sidebar.text_input("Groq API Key:", type="password") if llm_provider == "☁️ Groq (Cloud)" else ""
    local_model = st.sidebar.selectbox("Model", ["llama3.1", "llama3"]) if llm_provider == "💻 Ollama (Local)" else ""

    page = st.sidebar.radio("Navigation", ["🤝 Matchmaker", "⚔️ Encounter", "🎭 Improv Tools", "🌍 Worldbuilder", "🧠 Assistant"])

    # --- AI HELPER ---
    def get_ai_response(prompt):
        if llm_provider == "☁️ Groq (Cloud)":
            from groq import Groq
            client = Groq(api_key=groq_api_key)
            res = client.chat.completions.create(messages=[{"role": "user", "content": prompt}], model="llama-3.1-8b-instant").choices[0].message.content
        else:
            import ollama
            res = ollama.chat(model=local_model, messages=[{"role": "user", "content": prompt}])['message']['content']
        
        # LOGGING: Automatically add every AI response to the session log
        st.session_state.session_log += f"\n\n[GENERATED CONTENT - {datetime.now().strftime('%H:%M')}]\n{res}\n"
        return res

    # --- PAGE 1: MATCHMAKER ---
    if page == "🤝 Matchmaker":
        st.title("🤝 Matchmaker & LFG")
        pitch = st.text_area("Campaign Pitch")
        if st.button("Generate LFG Post"):
            res = get_ai_response(f"Write a Reddit LFG post for: {pitch}")
            st.code(res)

    # --- PAGE 2: ENCOUNTER ---
    elif page == "⚔️ Encounter":
        st.title("⚔️ Encounter Architect")
        h_name = st.text_input("Monster Name", "Swamp Terror")
        if st.button("Forge Stat Block"):
            res = get_ai_response(f"Create a 5e stat block for {h_name}")
            st.code(res)

    # --- PAGE 3: IMPROV TOOLS (WITH SAVE GAME) ---
    elif page == "🎭 Improv Tools":
        st.title("🎭 Procedural Improv Tools")

        # 1. THE SESSION LEDGER (THE SAVE BUTTON)
        with st.sidebar:
            st.markdown("---")
            st.subheader("💾 Session Ledger")
            st.write("Download everything you've generated this session.")
            st.download_button(
                label="📥 Download Session (.txt)",
                data=st.session_state.session_log,
                file_name=f"DM_Session_{datetime.now().strftime('%Y-%m-%d')}.txt",
                mime="text/plain",
                use_container_width=True
            )
            if st.button("🗑️ Reset Session", use_container_width=True):
                st.session_state.session_log = ""
                st.rerun()

        # 2. LOOT & TREASURY
        st.subheader("💰 Loot Generator")
        if st.button("Forge Random Loot"):
            item = get_ai_response("Generate one unique 5e magic item.")
            st.info(item)

        # 3. LANDMARKS
        st.markdown("---")
        st.subheader("🗺️ Wilderness Landmarks")
        if st.button("Generate Landmark"):
            st.code(get_ai_response("Generate a unique D&D landmark."))

        # 4. THE CHAOS BUTTON
        st.markdown("---")
        st.subheader("🎲 The Chaos Button")
        c1, c2 = st.columns(2)
        if c1.button("🔥 Critical Success"):
            st.success(get_ai_response("Generate a heroic critical hit effect."))
        if c2.button("💀 Critical Failure"):
            st.error(get_ai_response("Generate a dangerous critical fail effect."))

    # --- REMAINING PAGES ---
    elif page == "🌍 Worldbuilder":
        st.title("🌍 Worldbuilder")
        if st.button("Generate City"): st.write(get_ai_response("Generate a fantasy city."))

    elif page == "🧠 Assistant":
        st.title("🧠 DM Assistant")
        st.write("Analyze notes or chat with PDFs.")