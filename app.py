import streamlit as st
import pandas as pd
import streamlit_analytics2 as streamlit_analytics
import random
from datetime import datetime
import os

# --- 🐛 LOGGING & CONFIG ---
st.set_page_config(page_title="DM Co-Pilot | Masterwork Edition", page_icon="🐉", layout="wide")

# --- 🚦 ROUTING: DETECT ANALYTICS MODE ---
is_analytics = st.query_params.get("analytics") == "on"

if is_analytics:
    # --- 🟢 HIGH-CONTRAST ANALYST MODE (BRIGHT GREEN) ---
    st.markdown("""
        <style>
        [data-testid="stAppViewContainer"] {
            background-color: #0e1117 !important;
            background-image: none !important;
        }
        html, body, [class*="st-"], p, span, label, li, h1, h2, h3, div {
            color: #00FF00 !important; 
            font-family: monospace !important;
        }
        svg text {
            fill: #00FF00 !important;
        }
        </style>
        """, unsafe_allow_html=True)

else:
    # --- 🏰 NORMAL THEMED UI (PARCHMENT MAIN, HACKER SIDEBAR) ---
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=MedievalSharp&family=Crimson+Text:ital,wght@0,400;0,700;1,400&display=swap');
        
        /* 1. Main Content Area (Parchment) */
        [data-testid="stAppViewContainer"] {
            background-color: #f4ecd8 !important;
            background-image: url("https://www.transparenttextures.com/patterns/old-map.png") !important;
        }
        
        /* Target ONLY the main area for the Maroon text so it doesn't break the sidebar */
        [data-testid="stAppViewContainer"] p, 
        [data-testid="stAppViewContainer"] span, 
        [data-testid="stAppViewContainer"] label, 
        [data-testid="stAppViewContainer"] li {
            color: #1a0000 !important; 
            font-family: 'Crimson Text', serif;
            font-size: 1.05rem !important;
        }
        [data-testid="stAppViewContainer"] h1, 
        [data-testid="stAppViewContainer"] h2, 
        [data-testid="stAppViewContainer"] h3 { 
            font-family: 'MedievalSharp', cursive; 
            color: #800000 !important; 
        }

        /* 2. THE FIX: Sidebar Navigation (Strict Black & Hacker Green) */
        [data-testid="stSidebar"] {
            background-image: none !important;
            background-color: #000000 !important; 
            border-right: 3px solid #00FF00 !important; 
        }
        
        /* Explicitly force every text element inside the sidebar to be Hacker Green */
        [data-testid="stSidebar"] p,
        [data-testid="stSidebar"] span,
        [data-testid="stSidebar"] label,
        [data-testid="stSidebar"] div,
        [data-testid="stSidebar"] h1,
        [data-testid="stSidebar"] h2,
        [data-testid="stSidebar"] h3 {
            color: #00FF00 !important;
            font-family: monospace !important; 
            font-weight: bold !important;
        }

        /* 3. Output Cards & Inputs (Main Area) */
        .stat-card { 
            background-color: rgba(255, 255, 255, 0.95) !important; 
            border: 1px solid #d1d1d1 !important; 
            padding: 25px; 
            border-radius: 8px; 
            border-left: 8px solid #800000 !important; 
            margin-bottom: 20px; 
            box-shadow: 2px 2px 10px rgba(0,0,0,0.1);
            color: #000000 !important;
        }
        input, select, textarea, div[data-baseweb="select"] > div {
            background-color: #ffffff !important;
            color: #000000 !important;
            border: 1px solid #800000 !important;
            border-radius: 4px !important;
        }
        
        .stButton>button { 
            background-color: #800000 !important; 
            color: white !important; 
            font-family: 'MedievalSharp', cursive; 
            width: 100%; 
            border-radius: 5px;
            border: 1px solid #ffd700 !important;
            font-size: 1.1rem !important;
            transition: 0.3s;
        }
        .stButton>button:hover {
            background-color: #b22222 !important; 
            border: 1px solid #ffffff !important;
        }
        </style>
        """, unsafe_allow_html=True)

# --- ⚖️ RECHARGE TIER LOGIC ---
def get_item_balance_rules(rarity):
    tiers = {
        "Common": "1 charge, no recharge. Minor flavor effect only.",
        "Uncommon": "Max 3 charges. Regains 1d3 charges at dawn.",
        "Rare": "Max 7 charges. Regains 1d6+1 charges at dawn.",
        "Very Rare": "Max 10 charges. Regains 1d8+2 charges at dawn.",
        "Legendary": "Max 20 charges. Regains 2d6+4 charges at dawn."
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

# --- MAIN APP ---
with streamlit_analytics.track():
    st.sidebar.markdown("<h2 style='text-align: center;'>🐉 DM CO-PILOT</h2>", unsafe_allow_html=True)
    
    llm_provider = st.sidebar.radio("Engine", ["☁️ Groq (Cloud)", "💻 Ollama (Local)"])
    user_api_key = st.sidebar.text_input("Groq API Key", type="password") if llm_provider == "☁️ Groq (Cloud)" else ""
    
    st.sidebar.markdown("---")
    
    page = st.sidebar.radio("Navigation", [
        "📜 DM's Guide", "🤝 Matchmaker", "⚔️ Encounter Architect", "🏰 Dungeon Map Generator",
        "📖 Spellbook Analytics", "🏙️ Instant City Generator", "🧩 Trap Architect",
        "🎭 NPC Quick-Forge", "📜 Scribe's Handouts", "💎 Magic Item Artificer", "📫 Give Feedback"
    ])

    # --- 1. THE DEDICATED GUIDE PAGE ---
    if page == "📜 DM's Guide":
        st.title("📜 Welcome to the DM Co-Pilot")
        st.markdown("<div class='stat-card'>", unsafe_allow_html=True)
        st.markdown("""
        ### How to use this Grimoire
        Select a tool from the **Navigation Sidebar** on the left to get started. 

        * **🤝 Matchmaker:** Enter your world concept and player preferences to get 3 unique campaign pitches tailored to your group.
        * **⚔️ Encounter Architect:** Input the party's level and a theme (e.g., 'Swamp ambush'). The AI provides monsters, terrain hazards, and a tactical twist.
        * **💎 Magic Item Artificer:** Pick a rarity and a name. The system follows official 5e rules to generate balanced charges and attunement requirements.
        * **🏰 Dungeon Map Generator:** Generates a randomized, copy-pasteable tactical grid for quick dungeon prep.
        
        **⚙️ Engine Settings:**
        Use the sidebar to toggle between **☁️ Groq** (Cloud-based, lightning fast) and **💻 Ollama** (Locally hosted, 100% private).
        """)
        st.markdown("</div>", unsafe_allow_html=True)

    # --- 2. THE DATA ANALYST FEEDBACK TOOL ---
    elif page == "📫 Give Feedback":
        st.title("📫 Tavern Suggestion Box")
        
        with st.container():
            st.markdown("<div class='stat-card'>", unsafe_allow_html=True)
            st.markdown("### Rate your experience!")
            
            star_rating = st.feedback("stars")
            
            st.markdown("### Got an idea for a new tool?")
            user_feedback = st.text_area("What features should we add next?", height=100)
            
            if st.button("Submit Feedback"):
                rating_val = star_rating + 1 if star_rating is not None else "No Rating"
                new_data = pd.DataFrame({
                    "Timestamp": [datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
                    "Stars": [rating_val],
                    "Feedback": [user_feedback]
                })
                
                csv_file = "telemetry_feedback.csv"
                if os.path.exists(csv_file):
                    new_data.to_csv(csv_file, mode='a', header=False, index=False)
                else:
                    new_data.to_csv(csv_file, index=False)

                st.success("The ravens have delivered your message! Thank you for helping us improve.")
            st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("---")
        with st.expander("📊 Data Analyst Export (Admin View)"):
            st.write("Download the raw telemetry data to plug into Tableau or Excel.")
            if os.path.exists("telemetry_feedback.csv"):
                df_feedback = pd.read_csv("telemetry_feedback.csv")
                st.dataframe(df_feedback, use_container_width=True)
                
                csv = df_feedback.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Download Dataset as CSV",
                    data=csv,
                    file_name='dm_copilot_telemetry.csv',
                    mime='text/csv',
                )
            else:
                st.info("No feedback data collected yet.")

    # --- 3. CLEANED UP TOOLS ---
    elif page == "🤝 Matchmaker":
        st.title("🤝 Campaign Matchmaker")
        user_val = st.text_input("Pitch/Preferences", placeholder="e.g. A desert world where water is gold, players like puzzles")
        if st.button("Generate Matchmaker"):
            with st.spinner("Consulting the Grimoire..."):
                st.session_state.ai_outputs["match"] = get_ai_response(f"Analyze D&D campaign compatibility for: {user_val}", llm_provider, user_api_key)
        if "match" in st.session_state.ai_outputs:
            st.markdown(f"<div class='stat-card'>{st.session_state.ai_outputs['match']}</div>", unsafe_allow_html=True)
    
    elif page == "💎 Magic Item Artificer":
        st.title("💎 Magic Item Artificer")
        item_theme = st.text_input("Item Name/Type", key="magic_item_theme", placeholder="e.g. A vampiric longsword")
        rarity_choice = st.selectbox("Select Rarity", ["Common", "Uncommon", "Rare", "Very Rare", "Legendary"], key="magic_item_rarity")
        
        if st.button("Forge Magic Item"):
            with st.spinner("Enchanting the artifact..."):
                balance = get_item_balance_rules(rarity_choice)
                prompt = f"Design a {rarity_choice} D&D 5e magic item: {item_theme}. RULES: {balance}"
                st.session_state.ai_outputs["magic_item"] = get_ai_response(prompt, llm_provider, user_api_key)
        if "magic_item" in st.session_state.ai_outputs:
            st.markdown(f"<div class='stat-card'>{st.session_state.ai_outputs['magic_item']}</div>", unsafe_allow_html=True)

    # Generic catch-all for the other tabs
    else:
        st.title(f"{page}")
        user_val = st.text_input("Input concept...")
        if st.button(f"Generate {page}"):
            with st.spinner("Consulting the Grimoire..."):
                st.session_state.ai_outputs[page] = get_ai_response(f"Generate {page} content for: {user_val}", llm_provider, user_api_key)
        if page in st.session_state.ai_outputs:
            st.markdown(f"<div class='stat-card'>{st.session_state.ai_outputs[page]}</div>", unsafe_allow_html=True)

    st.sidebar.markdown("---")
    st.sidebar.download_button("📥 Export Session Log", st.session_state.session_log, file_name="DM_Log.txt", use_container_width=True)