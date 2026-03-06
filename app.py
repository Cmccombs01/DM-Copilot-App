import streamlit as st
import pandas as pd
import streamlit_analytics2 as streamlit_analytics
import random
from datetime import datetime
import os

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
        
        .stButton>button { 
            background-color: #000000 !important; 
            color: #00FF00 !important; 
            font-family: monospace !important; 
            font-weight: bold !important;
            width: 100%; 
            border-radius: 5px;
            border: 2px solid #00FF00 !important;
            font-size: 1.1rem !important;
            transition: 0.3s;
        }
        .stButton>button:hover {
            background-color: #00FF00 !important; 
            color: #000000 !important; 
        }
        </style>
        """, unsafe_allow_html=True)

else:
    # --- 🌌 MASTERWORK HACKER THEME (BLACK & NEON GREEN) ---
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=MedievalSharp&display=swap');

        /* 1. Main Background */
        [data-testid="stAppViewContainer"] {
            background-color: #000000 !important;
            background-image: none !important;
        }

        /* 2. Global Text & Headers */
        [data-testid="stAppViewContainer"] p, 
        [data-testid="stAppViewContainer"] span, 
        [data-testid="stAppViewContainer"] label, 
        [data-testid="stAppViewContainer"] li {
            color: #00FF00 !important;
            font-family: 'monospace', sans-serif !important;
        }

        [data-testid="stAppViewContainer"] h1, 
        [data-testid="stAppViewContainer"] h2, 
        [data-testid="stAppViewContainer"] h3 {
            font-family: 'MedievalSharp', cursive;
            color: #00FF00 !important;
            text-shadow: 0 0 10px #00FF00;
        }

        /* 3. Sidebar Navigation */
        [data-testid="stSidebar"] {
            background-color: #000000 !important;
            border-right: 2px solid #00FF00 !important;
        }
        
        [data-testid="stSidebar"] p, [data-testid="stSidebar"] span {
            color: #00FF00 !important;
            font-family: monospace !important;
        }

        /* 4. Radio Buttons */
        [data-testid="stSidebar"] div[data-baseweb="radio"] > div:first-child {
            background-color: #000000 !important;
            border: 2px solid #00FF00 !important;
        }
        [data-testid="stSidebar"] div[data-baseweb="radio"] div[role="radio"][aria-checked="true"] > div:first-child {
            background-color: #00FF00 !important;
        }

        /* 5. Output Cards & Result Boxes */
        .stat-card {
            background-color: #0a0a0a !important;
            border: 1px solid #00FF00 !important;
            padding: 25px;
            border-radius: 8px;
            border-left: 10px solid #00FF00 !important;
            color: #00FF00 !important;
            font-family: monospace !important;
            box-shadow: 0 0 15px rgba(0, 255, 0, 0.1);
            margin-bottom: 20px;
        }

        /* 6. Inputs & Text Areas */
        input, select, textarea, div[data-baseweb="select"] > div {
            background-color: #000000 !important;
            color: #00FF00 !important;
            border: 1px solid #00FF00 !important;
        }

        /* 7. Action Buttons */
        .stButton>button {
            background-color: #000000 !important;
            color: #00FF00 !important;
            font-family: monospace !important;
            border: 2px solid #00FF00 !important;
            width: 100%;
            transition: 0.3s;
        }
        .stButton>button:hover {
            background-color: #00FF00 !important;
            color: #000000 !important;
            border: 2px solid #000000 !important;
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

    elif page == "📫 Give Feedback":
        st.title("📫 Tavern Suggestion Box")
        
        with st.container():
            st.markdown("<div class='stat-card'>", unsafe_allow_html=True)
            
            star_rating = st.radio("### Rate your experience!", ["⭐", "⭐⭐", "⭐⭐⭐", "⭐⭐⭐⭐", "⭐⭐⭐⭐⭐"], index=4, horizontal=True)
            
            st.markdown("### Got an idea for a new tool?")
            user_feedback = st.text_area("What features should we add next?", height=100)
            
if st.button("Submit Feedback"):
            from streamlit_gsheets import GSheetsConnection
            
            # Connect to the Google Sheet
            conn = st.connection("gsheets", type=GSheetsConnection)
            
            # Create the new row of data
            new_data = pd.DataFrame({
                "Timestamp": [datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
                "Stars": [star_rating],
                "Feedback": [user_feedback]
            })
            
            # Read the existing sheet, add the new row, and update the cloud
            existing_data = conn.read(worksheet="Sheet1", usecols=list(range(3)), ttl=5)
            existing_data = existing_data.dropna(how="all") # Clean up any empty rows
            updated_data = pd.concat([existing_data, new_data], ignore_index=True)
            conn.update(worksheet="Sheet1", data=updated_data)
            st.success("The ravens have delivered your message! It is now permanently recorded in your Grimoire.")            
            st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("---")
        with st.expander("📊 Data Analyst Export (Admin View)"):
            st.write("Download the raw telemetry data to plug into Tableau or Excel.")
            if os.path.exists("telemetry_feedback.csv"):
                df_feedback = pd.read_csv("telemetry_feedback.csv")
                
                st.dataframe(df_feedback, width="stretch")
                
                csv = df_feedback.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Download Dataset as CSV",
                    data=csv,
                    file_name='dm_copilot_telemetry.csv',
                    mime='text/csv',
                )
            else:
                st.info("No feedback data collected yet.")

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

    else:
        st.title(f"{page}")
        user_val = st.text_input("Input concept...")
        if st.button(f"Generate {page}"):
            with st.spinner("Consulting the Grimoire..."):
                st.session_state.ai_outputs[page] = get_ai_response(f"Generate {page} content for: {user_val}", llm_provider, user_api_key)
        if page in st.session_state.ai_outputs:
            st.markdown(f"<div class='stat-card'>{st.session_state.ai_outputs[page]}</div>", unsafe_allow_html=True)

    st.sidebar.markdown("---")
    st.sidebar.download_button("📥 Export Session Log", st.session_state.session_log, file_name="DM_Log.txt", width="stretch")




