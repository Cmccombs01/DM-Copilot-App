import streamlit as st
import pandas as pd
import streamlit_analytics2 as streamlit_analytics
import random
from datetime import datetime
import streamlit.components.v1 as components
import logging
from fpdf import FPDF

# --- 🐛 ADVANCED ERROR LOGGING SETUP ---
logging.basicConfig(
    filename='app_errors.log',
    level=logging.ERROR,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="DM Co-Pilot | Masterwork Edition", page_icon="🐉", layout="wide")

# --- GOOGLE ANALYTICS ---
ga_tracking_code = """
<script async src="https://www.googletagmanager.com/gtag/js?id=G-S2FGGW3YMH"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());

  gtag('config', 'G-S2FGGW3YMH');
</script>
"""
components.html(ga_tracking_code, width=0, height=0)

# --- 🏰 THEMED UI & ACCESSIBILITY ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=MedievalSharp&family=Crimson+Text:ital,wght@0,400;0,700;1,400&display=swap');

    .stApp {
        background-image: url("https://www.transparenttextures.com/patterns/old-map.png");
        background-color: #ffffff;
        font-family: 'Crimson Text', serif;
        color: #1a1a1a !important;
    }

    [data-testid="stSidebar"] {
        background-image: url("https://www.transparenttextures.com/patterns/dark-leather.png");
        background-color: #252525;
        border-right: 3px solid #d4af37;
    }

    /* THEMED INSTRUCTION BOX */
    .instruction-box {
        background-color: #f0f4f8;
        border-left: 5px solid #2e5a88;
        padding: 15px;
        margin-bottom: 25px;
        border-radius: 5px;
        font-size: 1.1rem;
        color: #2c3e50;
    }

    .handout-card {
        background-color: #fdf6e3;
        background-image: url("https://www.transparenttextures.com/patterns/parchment.png");
        border: 2px solid #5d4037;
        padding: 30px;
        box-shadow: 10px 10px 20px rgba(0,0,0,0.1);
        color: #2c1b0e !important;
    }

    .stat-card {
        background-color: #ffffff;
        border: 1px solid #d1d1d1;
        padding: 20px;
        border-radius: 8px;
        border-left: 10px solid #b22222;
        margin-bottom: 20px;
    }

    /* BUTTON FIXES */
    .stButton>button, .stFormSubmitButton>button {
        background-color: #b22222 !important;
        color: #ffffff !important;
        border: 1px solid #d4af37 !important;
        font-family: 'MedievalSharp', cursive;
        font-size: 1.1rem !important;
        transition: background-color 0.3s ease;
    }
    
    .stButton>button:hover, .stFormSubmitButton>button:hover {
        background-color: #800000 !important;
        border: 1px solid #ffffff !important;
        color: #ffffff !important;
    }

    h1, h2, h3 {
        font-family: 'MedievalSharp', cursive;
        color: #800000 !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- INITIALIZE SESSION STATES ---
if 'session_log' not in st.session_state:
    st.session_state.session_log = f"--- DM Co-Pilot Session Log ({datetime.now().strftime('%Y-%m-%d')}) ---\n"
if 'last_roll' not in st.session_state:
    st.session_state.last_roll = "Roll the dice!"
if 'error_log' not in st.session_state:
    st.session_state.error_log = []

# --- ANALYTICS ---
with streamlit_analytics.track(unsafe_password=st.secrets.get("analytics_password", "local_test_password")):

    # --- SIDEBAR ---
    st.sidebar.markdown(f"<h2 style='text-align: center; color: #d4af37;'>🐉 DM CO-PILOT</h2>", unsafe_allow_html=True)
    
    # Dice Tray
    st.sidebar.markdown("### 🎲 Quick-Roll Tray")
    cols = st.sidebar.columns(3)
    dice = [4, 6, 8, 10, 12, 20]
    for i, d in enumerate(dice):
        if cols[i % 3].button(f"d{d}"):
            st.session_state.last_roll = f"d{d}: {random.randint(1, d)}"
    st.sidebar.markdown(f"<div style='text-align:center; font-size:24px; color:#d4af37; background:rgba(0,0,0,0.3); padding:5px; border-radius:5px;'>{st.session_state.last_roll}</div>", unsafe_allow_html=True)
    
    st.sidebar.markdown("---")
    llm_provider = st.sidebar.radio("Engine", ["☁️ Groq (Cloud)", "💻 Ollama (Local)"])
    user_api_key = st.sidebar.text_input("Groq API Key", type="password") if llm_provider == "☁️ Groq (Cloud)" else ""
    
    st.sidebar.markdown("---")
    
    # --- NAVIGATION MENU (Added Trap Architect) ---
    page = st.sidebar.radio("Navigation", [
        "🤝 Matchmaker", 
        "⚔️ Encounter Architect", 
        "🧩 Trap Architect",
        "🎭 NPC Quick-Forge", 
        "📜 Scribe's Handouts", 
        "💎 Magic Item Artificer", 
        "💰 Dynamic Shop Generator", 
        "🌍 Worldbuilder", 
        "📖 Session Recap Scribe",
        "🧠 Assistant", 
        "📫 Give Feedback"
    ])
    
    st.sidebar.download_button("📥 Export Session Log", st.session_state.session_log, file_name="DM_Log.txt", use_container_width=True)

    # --- 🗳️ UPDATED POLL (Removed Trap Architect, added Cursed Items) ---
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🗳️ Community Poll")
    poll_choice = st.sidebar.radio(
        "What should I build next?", 
        ["🎒 'Pocket Trash' Loot", "🏕️ Travel Montages", "🏰 Dungeon Map Generator", "💀 Cursed Item Creator"]
    )
    if poll_choice:
        st.sidebar.success(f"Vote for '{poll_choice}' recorded! 📝")

    # --- AI HELPER ---
    def get_ai_response(prompt):
        try:
            if llm_provider == "☁️ Groq (Cloud)":
                if not user_api_key: return "⚠️ Please enter your API Key in the sidebar to begin."
                from groq import Groq
                client = Groq(api_key=user_api_key)
                res = client.chat.completions.create(messages=[{"role": "user", "content": prompt}], model="llama-3.1-8b-instant").choices[0].message.content
            else:
                import ollama
                res = ollama.chat(model="llama3.1", messages=[{"role": "user", "content": prompt}])['message']['content']
            st.session_state.session_log += f"\n\n[TIME: {datetime.now().strftime('%H:%M')}]\n{res}\n"
            return res
        except Exception as e: 
            error_msg = f"ERROR on prompt '{prompt}': {str(e)}"
            st.session_state.error_log.append(f"[{datetime.now()}] {error_msg}")
            logger.error(error_msg)
            return "❌ The magic fizzled! The AI engine timed out or encountered an error. Please try again."

    # --- PAGE LOGIC ---
    if page == "🤝 Matchmaker":
        st.title("🤝 Campaign Matchmaker")
        st.markdown("""<div class='instruction-box'><b>How to use:</b> Paste your campaign summary and what you're looking for in a player. The AI will evaluate the 'vibe' and help you decide if a player is a good fit for your table.</div>""", unsafe_allow_html=True)
        pitch = st.text_area("The DM's Pitch & Player Preferences", placeholder="e.g. A dark gothic horror game for 4 players...")
        if st.button("Analyze Compatibility"):
            res = get_ai_response(f'Analyze: {pitch}')
            st.markdown(f"<div class='stat-card'>{res}</div>", unsafe_allow_html=True)
            if not res.startswith("❌") and not res.startswith("⚠️"): st.feedback("faces")

    elif page == "⚔️ Encounter Architect":
        st.title("⚔️ Encounter Architect")
        with st.expander("📖 How to use the Encounter Architect"):
            st.markdown("""
            1. **Type a name:** Enter any creature name, real or homebrew.
            2. **Generate:** The AI will forge a balanced 5th Edition stat block.
            """)
        h_name = st.text_input("Monster Name", placeholder="e.g. Lava Drake", help="Type any creature name here!")
        
        if st.button("Generate Stat Block"):
            with st.spinner("Forging the monster..."):
                res = get_ai_response(f"Generate a 5e stat block for {h_name}")
                st.markdown(f"<div class='stat-card'>{res.replace('\n', '<br>')}</div>", unsafe_allow_html=True)
                
                if not res.startswith("❌") and not res.startswith("⚠️"):
                    st.feedback("faces") 
                    try:
                        pdf = FPDF()
                        pdf.add_page()
                        pdf.set_font("Arial", size=12)
                        clean_text = res.encode('latin-1', 'ignore').decode('latin-1')
                        pdf.multi_cell(0, 10, txt=f"{h_name.upper()} - STAT BLOCK\n\n{clean_text}")
                        pdf_bytes = pdf.output(dest='S').encode('latin-1')
                        
                        st.download_button(
                            label="📝 Download PDF Stat Block",
                            data=pdf_bytes,
                            file_name=f"{h_name.replace(' ', '_')}_statblock.pdf",
                            mime="application/pdf",
                            use_container_width=True
                        )
                    except Exception as e:
                        st.error(f"Could not generate PDF: {e}")
                        logger.error(f"PDF Generation Error: {e}")

    # --- NEW FEATURE: TRAP ARCHITECT ---
    elif page == "🧩 Trap Architect":
        st.title("🧩 Trap & Puzzle Architect")
        st.markdown("""<div class='instruction-box'><b>How to use:</b> Enter a theme or location. The AI will generate a trap or puzzle, complete with 3 tiered hints to give struggling players, and a logical solution.</div>""", unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        with col1:
            trap_theme = st.text_input("Theme or Location", placeholder="e.g. Ancient Elven Tomb, Goblin Camp...")
        with col2:
            trap_type = st.radio("Encounter Type", ["Mechanical Trap", "Riddle / Puzzle"])

        if st.button("Construct Trap"):
            if not trap_theme:
                st.warning("⚠️ Please enter a theme or location first!")
            else:
                with st.spinner(f"Setting the mechanisms for the {trap_type.lower()}..."):
                    res = get_ai_response(f"Design a clever D&D 5e {trap_type.lower()} for a '{trap_theme}' setting. Include: 1) A flavorful description for the DM to read aloud. 2) The Mechanics (triggers, DC checks, damage, or the riddle text). 3) Three Tiered Hints the DM can hand out if players get stuck. 4) The clear, logical solution.")
                    st.markdown(f"<div class='stat-card'>{res.replace('\n', '<br>')}</div>", unsafe_allow_html=True)
                    if not res.startswith("❌") and not res.startswith("⚠️"): st.feedback("faces")

    elif page == "🎭 NPC Quick-Forge":
        st.title("🎭 The NPC Quick-Forge")
        st.markdown("""<div class='instruction-box'><b>How to use:</b> Enter a profession or basic concept. The AI will instantly generate a named character with a unique quirk, a hidden secret, and a voice prompt for you to act out.</div>""", unsafe_allow_html=True)
        npc_concept = st.text_input("NPC Concept", placeholder="e.g. A suspicious tavern keeper, or a nervous goblin merchant...")
        if st.button("Forge NPC"):
            with st.spinner("Breathing life into the NPC..."):
                res = get_ai_response(f"Create a memorable D&D 5e NPC based on this concept: '{npc_concept}'. Include a creative Name, a distinct Physical Quirk, a Secret they are hiding, a specific Voice/Mannerism prompt for the DM to act out, and their general Disposition.")
                st.markdown(f"<div class='stat-card'>{res.replace('\n', '<br>')}</div>", unsafe_allow_html=True)
                if not res.startswith("❌") and not res.startswith("⚠️"): st.feedback("faces")

    elif page == "📜 Scribe's Handouts":
        st.title("📜 Scribe's Handouts")
        st.markdown("""<div class='instruction-box'><b>How to use:</b> Choose a style of document and give it a 'hook' or 'secret'. The AI will write a beautiful, in-character prop.</div>""", unsafe_allow_html=True)
        h_style = st.selectbox("Style", ["Bounty Poster", "King's Decree", "Torn Journal", "Mystic Prophecy"])
        msg = st.text_input("Core Hook", placeholder="Wanted for stealing the Duke's ring...")
        if st.button("Forge Document"):
            res = get_ai_response(f"Write a flavorful {h_style}: {msg}")
            st.markdown(f"<div class='handout-card'><h3 style='text-align:center;'>{h_style.upper()}</h3><hr>{res.replace('\n', '<br>')}</div>", unsafe_allow_html=True)
            if not res.startswith("❌") and not res.startswith("⚠️"): st.feedback("faces")

    elif page == "💎 Magic Item Artificer":
        st.title("💎 Magic Item Artificer")
        st.markdown("""
        <div class='instruction-box'>
            <b>Toll Required!</b> The Artificer's forge is locked. To power the magic generator, you must feed it one piece of feedback or a feature idea!
        </div>
        """, unsafe_allow_html=True)
        
        toll_feedback = st.text_input("What should I build or improve next?", placeholder="e.g. Add a tavern generator, fix the dark mode...")
        item_theme = st.text_input("Magic Item Theme", placeholder="e.g. A shadowy rogue amulet")
        
        if st.button("Forge Magic Item"):
            if len(toll_feedback) < 3:
                st.warning("⚠️ The Goblin demands a real suggestion in the box above before opening the forge!")
            elif not item_theme:
                st.warning("⚠️ Please enter a theme for the magic item.")
            else:
                st.success("Toll accepted! Your feedback has been sent to the developer's ledger. Forging your item...")
                with st.spinner("Enchanting the artifact..."):
                    res = get_ai_response(f"Create a unique 5e magic item based on this theme: {item_theme}. Include a cool name, mechanical 5e stats, physical description, and a snippet of deep lore.")
                    st.markdown(f"<div class='stat-card'>{res.replace('\n', '<br>')}</div>", unsafe_allow_html=True)
                    if not res.startswith("❌") and not res.startswith("⚠️"): st.feedback("faces")

    elif page == "💰 Dynamic Shop Generator":
        st.title("💰 Dynamic Shop Generator")
        st.markdown("""<div class='instruction-box'><b>How to use:</b> Select a shop type. The AI will generate a shop name, a quirky proprietor, and a formatted inventory table complete with gold piece prices.</div>""", unsafe_allow_html=True)
        shop_type = st.selectbox("Shop Type", ["General Store", "Apothecary / Potions", "Black Market / Fence", "Magic Item Broker", "Weaponsmith"])
        if st.button("Generate Shop"):
            with st.spinner("Stocking the shelves..."):
                res = get_ai_response(f"Generate a '{shop_type}' for a D&D 5e game. Include a creative Shop Name, a brief description of the quirky shopkeeper, and a formatted table of 5-7 thematic items for sale with their gold piece prices.")
                st.markdown(f"<div class='stat-card'>{res.replace('\n', '<br>')}</div>", unsafe_allow_html=True)
                if not res.startswith("❌") and not res.startswith("⚠️"): st.feedback("faces")

    elif page == "🌍 Worldbuilder":
        st.title("🌍 Worldbuilder's Forge")
        st.markdown("""<div class='instruction-box'><b>How to use:</b> Select what you need and the AI will generate deep, flavorful history to flesh out your world.</div>""", unsafe_allow_html=True)
        w_type = st.selectbox("I need a...", ["City", "Deity", "Faction"])
        if st.button("Forge Lore"):
            res = get_ai_response(f'Deep lore for {w_type}')
            st.markdown(f"<div class='stat-card'>{res.replace('\n','<br>')}</div>", unsafe_allow_html=True)
            if not res.startswith("❌") and not res.startswith("⚠️"): st.feedback("faces")

    elif page == "📖 Session Recap Scribe":
        st.title("📖 'Previously On...' Summarizer")
        st.markdown("""<div class='instruction-box'><b>How to use:</b> Paste your messy, bullet-point notes from your last game. The AI will rewrite them into a dramatic, polished monologue designed to be read aloud to hype up the players.</div>""", unsafe_allow_html=True)
        messy_notes = st.text_area("Rough Session Notes", placeholder="The party fought some goblins, Bob almost died to a trap, they found a glowing sword...")
        if st.button("Draft Recap"):
            with st.spinner("Scripting the dramatic intro..."):
                res = get_ai_response(f"Turn these rough D&D session notes into a dramatic, polished 2-paragraph monologue designed to be read aloud by the Dungeon Master at the start of the next session to hype up the players: {messy_notes}")
                st.markdown(f"<div class='stat-card'>{res.replace('\n', '<br>')}</div>", unsafe_allow_html=True)
                if not res.startswith("❌") and not res.startswith("⚠️"): st.feedback("faces")

    elif page == "🧠 Assistant":
        st.title("🧠 Digital DM Assistant")
        st.markdown("""<div class='instruction-box'><b>How to use:</b> Paste your notes or ideas. The AI will act as your co-writer, identifying plot holes or suggesting twists.</div>""", unsafe_allow_html=True)
        notes = st.text_area("Session Notes", placeholder="The party found the map, but killed the NPC who could read it...")
        if st.button("🔍 Analyze Plot"):
            res = get_ai_response(f'Analyze plot twists: {notes}')
            st.markdown(f"<div class='stat-card'>{res}</div>", unsafe_allow_html=True)
            if not res.startswith("❌") and not res.startswith("⚠️"): st.feedback("faces")

    elif page == "📫 Give Feedback":
        st.title("📫 Tavern Suggestion Box")
        st.write("Help me improve the DM Co-Pilot! What should I build next?")
        
        from streamlit_gsheets import GSheetsConnection
        conn = st.connection("gsheets", type=GSheetsConnection)
        
        with st.form("user_feedback_form"):
            user_rating = st.radio("How would you rate the app so far?", 
                                   ["⭐⭐⭐⭐⭐ (5 Stars)", "⭐⭐⭐⭐ (4 Stars)", "⭐⭐⭐ (3 Stars)", "⭐⭐ (2 Stars)", "⭐ (1 Star)"], 
                                   horizontal=True)
            
            user_vtt = st.selectbox("What Virtual Tabletop do you use?", ["Roll20", "Foundry", "Owlbear Rodeo", "Pen & Paper", "Other"])
            user_idea = st.text_area("What feature should I add next?", placeholder="e.g., Export to PDF, NPC Generator...")
            
            submitted = st.form_submit_button("Submit Feedback")
            
            if submitted:
                numerical_rating = user_rating.split("(")[1][0] 
                sheet_url = "https://docs.google.com/spreadsheets/d/1g6GRCspt8pIEaUpbGdUruiZu8X3wpOIDJNGr9O1lVBo/edit"
                existing_data = conn.read(spreadsheet=sheet_url, usecols=[0, 1, 2, 3])
                
                new_row = pd.DataFrame([{
                    "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "Rating": numerical_rating,
                    "VTT": user_vtt,
                    "Feature_Idea": user_idea
                }])
                
                updated_data = pd.concat([existing_data, new_row], ignore_index=True)
                conn.update(spreadsheet=sheet_url, data=updated_data)
                
                st.markdown(f"""
                <div style="background-color: #f0f4f8; border-left: 6px solid #000080; padding: 15px; border-radius: 5px; margin-top: 20px;">
                    <h3 style="color: #000080; margin: 0; font-family: 'Crimson Text', serif;">📬 Feedback Received!</h3>
                    <p style="color: #000080; font-size: 1.1rem; margin-top: 5px; font-weight: bold;">
                        Thank you! Your {numerical_rating}-star rating and feedback have been sent to the developer's ledger.
                    </p>
                </div>
                """, unsafe_allow_html=True)