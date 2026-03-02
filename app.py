import streamlit as st
import pandas as pd
import streamlit_analytics2 as streamlit_analytics
import random
from datetime import datetime

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="DM Co-Pilot | Masterwork Edition", page_icon="🐉", layout="wide")

# --- 🏰 THEMED UI & HANDOUT POLISH ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=MedievalSharp&family=Crimson+Text:ital,wght@0,400;0,700;1,400&display=swap');

    /* Main Background */
    .stApp {
        background-image: url("https://www.transparenttextures.com/patterns/old-map.png");
        background-color: #ffffff;
        font-family: 'Crimson Text', serif;
        color: #1a1a1a !important;
    }

    /* Sidebar Styling */
    [data-testid="stSidebar"] {
        background-image: url("https://www.transparenttextures.com/patterns/dark-leather.png");
        background-color: #252525;
        border-right: 3px solid #d4af37;
    }

    /* THE "WotC" HANDOUT CARD - NEW POLISH */
    .handout-card {
        background-color: #fdf6e3;
        background-image: url("https://www.transparenttextures.com/patterns/parchment.png");
        border: 2px solid #5d4037;
        padding: 30px;
        margin: 20px 0;
        box-shadow: 10px 10px 20px rgba(0,0,0,0.2);
        position: relative;
        color: #2c1b0e !important;
        font-size: 1.2rem;
        line-height: 1.6;
        border-radius: 2px;
    }

    .handout-card::before {
        content: "📜";
        position: absolute;
        top: -15px;
        left: 50%;
        transform: translateX(-50%);
        background: #fdf6e3;
        padding: 0 10px;
        font-size: 24px;
    }

    /* Button Polish */
    .stButton>button {
        background-color: #b22222 !important;
        color: #ffffff !important;
        border: 1px solid #d4af37 !important;
        font-family: 'MedievalSharp', cursive;
        border-radius: 0px !important;
        transition: 0.3s;
    }

    h1, h2, h3 {
        font-family: 'MedievalSharp', cursive;
        color: #800000 !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- ANALYTICS ---
with streamlit_analytics.track(unsafe_password=st.secrets.get("analytics_password", "local_test_password")):

    # --- SIDEBAR & NAV ---
    st.sidebar.markdown(f"<h2 style='text-align: center; color: #d4af37;'>🐉 DM CO-PILOT</h2>", unsafe_allow_html=True)
    
    # 🎲 Dice Tray
    st.sidebar.markdown("### 🎲 Dice Tray")
    cols = st.sidebar.columns(3)
    dice = [4, 6, 8, 10, 12, 20]
    for i, d in enumerate(dice):
        if cols[i % 3].button(f"d{d}"):
            st.session_state.last_roll = f"d{d}: {random.randint(1, d)}"
    st.sidebar.markdown(f"<div style='text-align:center; font-size:24px; color:#d4af37;'>{st.session_state.get('last_roll', 'Roll!')}</div>", unsafe_allow_html=True)
    
    st.sidebar.markdown("---")
    page = st.sidebar.radio("Navigation", ["🤝 Matchmaker", "⚔️ Encounter Architect", "📜 Scribe's Handouts", "🌍 Worldbuilder", "🧠 Assistant"])

    # --- AI HELPER ---
    def get_ai_response(prompt):
        from groq import Groq
        client = Groq(api_key=st.sidebar.text_input("Groq API Key", type="password"))
        if not client.api_key: return "Enter Key in Sidebar"
        res = client.chat.completions.create(messages=[{"role": "user", "content": prompt}], model="llama-3.1-8b-instant").choices[0].message.content
        return res

    # --- SCRIBE'S HANDOUTS (POLISHED) ---
    if page == "📜 Scribe's Handouts":
        st.title("📜 Scribe's Handouts")
        st.markdown("*Instructions: Select your document type. The generator will create an immersive prop for your players.*")
        
        h_style = st.selectbox("Document Style", ["Bounty Poster", "King's Decree", "Torn Journal Entry", "Mystic Prophecy"])
        msg = st.text_input("Core Message / Hook", placeholder="Wanted: The Thief known as 'Shadow-Step'...")
        
        if st.button("Forge Document"):
            with st.spinner("The Scribe is dipping the quill..."):
                res = get_ai_response(f"Write a flavorful, immersive {h_style} based on: {msg}. Use archaic language.")
                st.markdown(f"""
                    <div class='handout-card'>
                        <h3 style='text-align:center; color:#5d4037 !important;'>{h_style.upper()}</h3>
                        <hr style='border-top: 1px solid #5d4037;'>
                        {res.replace('\n', '<br>')}
                    </div>
                """, unsafe_allow_html=True)