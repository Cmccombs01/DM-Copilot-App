import streamlit as st
import pandas as pd
import streamlit_analytics2 as streamlit_analytics
import random
from datetime import datetime
import streamlit.components.v1 as components
import logging
from fpdf import FPDF
import altair as alt

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

# --- INITIALIZE SESSION STATES (WITH GLOBAL MEMORY) ---
if 'session_log' not in st.session_state:
    st.session_state.session_log = f"--- DM Co-Pilot Session Log ({datetime.now().strftime('%Y-%m-%d')}) ---\n"
if 'last_roll' not in st.session_state:
    st.session_state.last_roll = "Roll the dice!"
if 'error_log' not in st.session_state:
    st.session_state.error_log = []
if 'ai_outputs' not in st.session_state:
    st.session_state.ai_outputs = {}

# --- 📊 BACKGROUND DATA LOGGER ---
def log_usage_to_sheet(tool_name, user_input):
    """Silently logs app usage data to the Google Sheet for analysis"""
    try:
        from streamlit_gsheets import GSheetsConnection
        conn = st.connection("gsheets", type=GSheetsConnection)
        sheet_url = "https://docs.google.com/spreadsheets/d/1g6GRCspt8pIEaUpbGdUruiZu8X3wpOIDJNGr9O1lVBo/edit"
        
        existing_data = conn.read(spreadsheet=sheet_url)
        new_row = pd.DataFrame([{
            "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Action_Type": "Tool Usage",
            "Tool_Used": tool_name,
            "User_Input": str(user_input)
        }])
        
        updated_data = pd.concat([existing_data, new_row], ignore_index=True)
        conn.update(spreadsheet=sheet_url, data=updated_data)
    except Exception as e:
        logger.error(f"Failed to log to GSheets: {e}")
        pass

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
    
    # --- 🔑 UPDATED API KEY INSTRUCTIONS ---
    llm_provider = st.sidebar.radio("Engine", ["☁️ Groq (Cloud)", "💻 Ollama (Local)"])
    if llm_provider == "☁️ Groq (Cloud)":
        user_api_key = st.sidebar.text_input("Groq API Key", type="password")
        st.sidebar.caption("🔑 Don't have one? [Get your free Groq API key here!](https://console.groq.com/keys)")
    else:
        user_api_key = ""
        
    st.sidebar.markdown("---")
    
    # --- NAVIGATION MENU ---
    page = st.sidebar.radio("Navigation", [
        "🤝 Matchmaker", 
        "⚔️ Encounter Architect", 
        "🧩 Trap Architect",
        "🎭 NPC Quick-Forge", 
        "📜 Scribe's Handouts", 
        "💎 Magic Item Artificer", 
        "💀 Cursed Item Creator",
        "💰 Dynamic Shop Generator",
        "🎒 'Pocket Trash' Loot", 
        "🐉 The Dragon's Hoard",
        "🍻 Tavern Rumor Mill",
        "🌍 Worldbuilder", 
        "📖 Session Recap Scribe",
        "🧠 Assistant", 
        "📫 Give Feedback"
    ])
    
    st.sidebar.download_button("📥 Export Session Log", st.session_state.session_log, file_name="DM_Log.txt", use_container_width=True)

    # --- 🗳️ REFRESHED SIDEBAR POLL ---
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🗳️ Community Poll")
    poll_choice = st.sidebar.radio(
        "What should I build next?", 
        ["✨ Wild Magic Surge Generator", "🏕️ Travel Montages", "🏰 Dungeon Map Generator", "📜 1d100 Feywild Bargains"]
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
            log_usage_to_sheet("Matchmaker", pitch)
            with st.spinner("Analyzing..."):
                st.session_state.ai_outputs["Matchmaker"] = get_ai_response(f'Analyze: {pitch}')
        if "Matchmaker" in st.session_state.ai_outputs:
            st.markdown(f"<div class='stat-card'>{st.session_state.ai_outputs['Matchmaker']}</div>", unsafe_allow_html=True)
            if not st.session_state.ai_outputs["Matchmaker"].startswith("❌"): st.feedback("faces")

    elif page == "⚔️ Encounter Architect":
        st.title("⚔️ Encounter Architect")
        
        st.markdown("### 📊 Visual Monster Balancer")
        st.write("Compare monster stats against the SRD baseline to prevent accidental TPKs (Total Party Kills). Hover over the dots to see specific monsters!")
        
        @st.cache_data
        def load_monster_data():
            try:
                df = pd.read_csv("monsters.csv")
                plot_df = pd.DataFrame()
                cr_col = next((col for col in df.columns if 'cr' in col.lower() or 'challenge' in col.lower()), None)
                hp_col = next((col for col in df.columns if 'hp' in col.lower() or 'hit points' in col.lower()), None)
                name_col = next((col for col in df.columns if 'name' in col.lower()), df.columns[0])
                if cr_col and hp_col:
                    def parse_cr(x):
                        try:
                            if pd.isna(x): return 0.0
                            if isinstance(x, str) and '/' in x:
                                n, d = x.split('/')
                                return float(n)/float(d)
                            return float(x)
                        except: return 0.0
                    plot_df['CR'] = df[cr_col].apply(parse_cr)
                    plot_df['HP'] = pd.to_numeric(df[hp_col].astype(str).str.extract(r'(\d+)')[0], errors='coerce').fillna(0)
                    plot_df['Name'] = df[name_col]
                    return plot_df
                else:
                    raise Exception("Expected columns not found")
            except:
                crs = [round(random.uniform(0, 30), 2) for _ in range(400)]
                hps = [max(1, int(cr * 15 + random.uniform(-20, 40))) for cr in crs]
                return pd.DataFrame({'Name': [f'Baseline Monster {i}' for i in range(1, 401)], 'CR': crs, 'HP': hps})

        m_df = load_monster_data()
        chart = alt.Chart(m_df).mark_circle(size=70, color='#b22222', opacity=0.6).encode(
            x=alt.X('CR:Q', title='Challenge Rating (CR)'),
            y=alt.Y('HP:Q', title='Hit Points (HP)'),
            tooltip=['Name', 'CR', 'HP']
        ).interactive()
        st.altair_chart(chart, use_container_width=True)
        
        st.markdown("---")
        st.markdown("### 🛠️ Stat Block Forge")
        h_name = st.text_input("Monster Name", placeholder="e.g. Lava Drake")
        
        if st.button("Generate Stat Block"):
            log_usage_to_sheet("Encounter Architect", h_name)
            with st.spinner("Forging the monster..."):
                st.session_state.ai_outputs["Encounter"] = get_ai_response(f"Generate a 5e stat block for {h_name}")
                st.session_state.ai_outputs["Encounter_Name"] = h_name
                
        if "Encounter" in st.session_state.ai_outputs:
            res = st.session_state.ai_outputs["Encounter"]
            c_name = st.session_state.ai_outputs.get("Encounter_Name", "Monster")
            st.markdown(f"<div class='stat-card'>{res.replace('\n', '<br>')}</div>", unsafe_allow_html=True)
            if not res.startswith("❌"):
                try:
                    pdf = FPDF()
                    pdf.add_page()
                    pdf.set_font("Arial", size=12)
                    clean_text = res.encode('latin-1', 'ignore').decode('latin-1')
                    pdf.multi_cell(0, 10, txt=f"{c_name.upper()} - STAT BLOCK\n\n{clean_text}")
                    pdf_bytes = pdf.output(dest='S').encode('latin-1')
                    
                    st.download_button(
                        label="📝 Download PDF Stat Block",
                        data=pdf_bytes,
                        file_name=f"{c_name.replace(' ', '_')}_statblock.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )
                except Exception as e:
                    pass

    elif page == "🧩 Trap Architect":
        st.title("🧩 Trap & Puzzle Architect")
        col1, col2 = st.columns(2)
        with col1:
            trap_theme = st.text_input("Theme or Location", placeholder="e.g. Ancient Elven Tomb, Goblin Camp...")
        with col2:
            trap_type = st.radio("Encounter Type", ["Mechanical Trap", "Riddle / Puzzle"])

        if st.button("Construct Trap"):
            if not trap_theme:
                st.warning("⚠️ Please enter a theme or location first!")
            else:
                log_usage_to_sheet("Trap Architect", f"{trap_type} in {trap_theme}")
                with st.spinner(f"Setting the mechanisms for the {trap_type.lower()}..."):
                    st.session_state.ai_outputs["Trap"] = get_ai_response(f"Design a clever D&D 5e {trap_type.lower()} for a '{trap_theme}' setting. Include: 1) A flavorful description for the DM to read aloud. 2) The Mechanics (triggers, DC checks, damage, or the riddle text). 3) Three Tiered Hints the DM can hand out if players get stuck. 4) The clear, logical solution.")
        
        if "Trap" in st.session_state.ai_outputs:
            st.markdown(f"<div class='stat-card'>{st.session_state.ai_outputs['Trap'].replace('\n', '<br>')}</div>", unsafe_allow_html=True)

    elif page == "🎭 NPC Quick-Forge":
        st.title("🎭 The NPC Quick-Forge")
        npc_concept = st.text_input("NPC Concept", placeholder="e.g. A suspicious tavern keeper...")
        if st.button("Forge NPC"):
            log_usage_to_sheet("NPC Quick-Forge", npc_concept)
            with st.spinner("Breathing life into the NPC..."):
                st.session_state.ai_outputs["NPC"] = get_ai_response(f"Create a memorable D&D 5e NPC based on this concept: '{npc_concept}'. Include a creative Name, a distinct Physical Quirk, a Secret they are hiding, a specific Voice/Mannerism prompt for the DM to act out, and their general Disposition.")
        if "NPC" in st.session_state.ai_outputs:
            st.markdown(f"<div class='stat-card'>{st.session_state.ai_outputs['NPC'].replace('\n', '<br>')}</div>", unsafe_allow_html=True)

    elif page == "📜 Scribe's Handouts":
        st.title("📜 Scribe's Handouts")
        h_style = st.selectbox("Style", ["Bounty Poster", "King's Decree", "Torn Journal", "Mystic Prophecy"])
        msg = st.text_input("Core Hook", placeholder="Wanted for stealing the Duke's ring...")
        if st.button("Forge Document"):
            log_usage_to_sheet("Scribe Handouts", f"{h_style} - {msg}")
            with st.spinner("Writing..."):
                st.session_state.ai_outputs["Handout_Style"] = h_style
                st.session_state.ai_outputs["Handout"] = get_ai_response(f"Write a flavorful {h_style}: {msg}")
        if "Handout" in st.session_state.ai_outputs:
            style = st.session_state.ai_outputs.get("Handout_Style", h_style)
            st.markdown(f"<div class='handout-card'><h3 style='text-align:center;'>{style.upper()}</h3><hr>{st.session_state.ai_outputs['Handout'].replace('\n', '<br>')}</div>", unsafe_allow_html=True)

    elif page == "💎 Magic Item Artificer":
        st.title("💎 Magic Item Artificer")
        st.markdown("<div class='instruction-box'><b>Toll Required!</b> You must feed the generator one piece of feedback or a feature idea!</div>", unsafe_allow_html=True)
        toll_feedback = st.text_input("What should I build or improve next?", placeholder="e.g. Add a tavern generator...")
        item_theme = st.text_input("Magic Item Theme", placeholder="e.g. A shadowy rogue amulet")
        
        if st.button("Forge Magic Item"):
            if len(toll_feedback) < 3:
                st.warning("⚠️ The Goblin demands a real suggestion in the box above before opening the forge!")
            elif not item_theme:
                st.warning("⚠️ Please enter a theme for the magic item.")
            else:
                log_usage_to_sheet("Magic Item Artificer", f"Feedback: {toll_feedback} | Theme: {item_theme}")
                st.success("Toll accepted! Forging your item...")
                with st.spinner("Enchanting..."):
                    st.session_state.ai_outputs["MagicItem"] = get_ai_response(f"Create a unique 5e magic item based on this theme: {item_theme}. Include a cool name, mechanical 5e stats, physical description, and a snippet of deep lore.")
        if "MagicItem" in st.session_state.ai_outputs:
            st.markdown(f"<div class='stat-card'>{st.session_state.ai_outputs['MagicItem'].replace('\n', '<br>')}</div>", unsafe_allow_html=True)

    elif page == "💀 Cursed Item Creator":
        st.title("💀 Cursed Item Creator")
        curse_theme = st.text_input("Item Type or Theme", placeholder="e.g. A sentient longsword, a golden crown...")
        if st.button("Forge Cursed Item"):
            log_usage_to_sheet("Cursed Item Creator", curse_theme)
            with st.spinner("Binding dark magic to the artifact..."):
                st.session_state.ai_outputs["Cursed"] = get_ai_response(f"Create a powerful 5e magic item based on '{curse_theme}'. Give it amazing benefits that make players genuinely WANT to use it, but attach a horrifyingly flavorful, narrative-driven curse that slowly corrupts them or causes chaos. Include stats, description, and the curse mechanics.")
        if "Cursed" in st.session_state.ai_outputs:
            st.markdown(f"<div class='stat-card'>{st.session_state.ai_outputs['Cursed'].replace('\n', '<br>')}</div>", unsafe_allow_html=True)

    elif page == "💰 Dynamic Shop Generator":
        st.title("💰 Dynamic Shop Generator")
        shop_type = st.selectbox("Shop Type", ["General Store", "Apothecary / Potions", "Black Market / Fence", "Magic Item Broker", "Weaponsmith"])
        if st.button("Generate Shop"):
            log_usage_to_sheet("Shop Generator", shop_type)
            with st.spinner("Stocking the shelves..."):
                st.session_state.ai_outputs["Shop"] = get_ai_response(f"Generate a '{shop_type}' for a D&D 5e game. Include a creative Shop Name, a brief description of the quirky shopkeeper, and a formatted table of 5-7 thematic items for sale with their gold piece prices.")
        if "Shop" in st.session_state.ai_outputs:
            st.markdown(f"<div class='stat-card'>{st.session_state.ai_outputs['Shop'].replace('\n', '<br>')}</div>", unsafe_allow_html=True)

    elif page == "🎒 'Pocket Trash' Loot":
        st.title("🎒 'Pocket Trash' Loot Generator")
        loot_target = st.selectbox("Who (or what) was looted?", ["Common Bandit / Thug", "Goblin / Orc Grunt", "Wealthy Noble / Merchant", "Cultist / Dark Acolyte", "Ancient Undead (Skeleton/Zombie)", "Dead Explorer / Adventurer"])
        if st.button("Search their pockets!"):
            log_usage_to_sheet("Pocket Trash", loot_target)
            with st.spinner("Rifling through their belongings..."):
                st.session_state.ai_outputs["Trash"] = get_ai_response(f"Generate 'pocket trash' loot for a D&D 5e game. The players just defeated and looted a '{loot_target}'. Instead of just generic coins, provide a formatted, bulleted list of 4-5 flavorful, mundane items they find in their pockets or pouches. Make it highly thematic. Include a tiny, randomized amount of relevant coins at the very end.")
        if "Trash" in st.session_state.ai_outputs:
            st.markdown(f"<div class='stat-card'>{st.session_state.ai_outputs['Trash'].replace('\n', '<br>')}</div>", unsafe_allow_html=True)

    elif page == "🐉 The Dragon's Hoard":
        st.title("🐉 The Dragon's Hoard")
        cr_tier = st.selectbox("Encounter Challenge Rating (CR)", ["CR 0-4 (Local Threat)", "CR 5-10 (Regional Boss)", "CR 11-16 (Kingdom Threat)", "CR 17+ (World Ender)"])
        if st.button("Generate Hoard"):
            log_usage_to_sheet("Dragon's Hoard", cr_tier)
            with st.spinner("Counting the gold..."):
                st.session_state.ai_outputs["Hoard"] = get_ai_response(f"Generate a D&D 5e treasure hoard appropriate for a boss fight of {cr_tier}. Include a specific, logical amount of gold/silver/copper, 3-5 valuable art objects or gems with vivid descriptions and their GP values, and 1-2 highly thematic magic items.")
        if "Hoard" in st.session_state.ai_outputs:
            st.markdown(f"<div class='stat-card'>{st.session_state.ai_outputs['Hoard'].replace('\n', '<br>')}</div>", unsafe_allow_html=True)

    elif page == "🍻 Tavern Rumor Mill":
        st.title("🍻 The Tavern Rumor Mill")
        rumor_target = st.text_input("Rumor Subject", placeholder="e.g. The town of Phandalin, the local Baron...")
        if st.button("Eavesdrop"):
            log_usage_to_sheet("Rumor Mill", rumor_target)
            with st.spinner("Buying a round for the locals..."):
                st.session_state.ai_outputs["Rumor"] = get_ai_response(f"Generate 3 local tavern rumors about '{rumor_target}' for a D&D game. Format as a bulleted list: One must be completely true, one must be a total lie, and one must be partially true but dangerously misleading.")
        if "Rumor" in st.session_state.ai_outputs:
            st.markdown(f"<div class='stat-card'>{st.session_state.ai_outputs['Rumor'].replace('\n', '<br>')}</div>", unsafe_allow_html=True)

    elif page == "🌍 Worldbuilder":
        st.title("🌍 Worldbuilder's Forge")
        w_type = st.selectbox("I need a...", ["City", "Deity", "Faction"])
        if st.button("Forge Lore"):
            log_usage_to_sheet("Worldbuilder", w_type)
            with st.spinner("Writing history..."):
                st.session_state.ai_outputs["World"] = get_ai_response(f'Deep lore for {w_type}')
        if "World" in st.session_state.ai_outputs:
            st.markdown(f"<div class='stat-card'>{st.session_state.ai_outputs['World'].replace('\n','<br>')}</div>", unsafe_allow_html=True)

    elif page == "📖 Session Recap Scribe":
        st.title("📖 'Previously On...' Summarizer")
        messy_notes = st.text_area("Rough Session Notes", placeholder="The party fought some goblins...")
        if st.button("Draft Recap"):
            log_usage_to_sheet("Session Recap", messy_notes)
            with st.spinner("Scripting the dramatic intro..."):
                st.session_state.ai_outputs["Recap"] = get_ai_response(f"Turn these rough D&D session notes into a dramatic, polished 2-paragraph monologue designed to be read aloud by the Dungeon Master at the start of the next session: {messy_notes}")
        if "Recap" in st.session_state.ai_outputs:
            st.markdown(f"<div class='stat-card'>{st.session_state.ai_outputs['Recap'].replace('\n', '<br>')}</div>", unsafe_allow_html=True)

    elif page == "🧠 Assistant":
        st.title("🧠 Digital DM Assistant")
        notes = st.text_area("Session Notes", placeholder="The party found the map...")
        if st.button("🔍 Analyze Plot"):
            log_usage_to_sheet("DM Assistant", notes)
            with st.spinner("Analyzing..."):
                st.session_state.ai_outputs["Assistant"] = get_ai_response(f'Analyze plot twists: {notes}')
        if "Assistant" in st.session_state.ai_outputs:
            st.markdown(f"<div class='stat-card'>{st.session_state.ai_outputs['Assistant']}</div>", unsafe_allow_html=True)

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
                existing_data = conn.read(spreadsheet=sheet_url)
                
                new_row = pd.DataFrame([{
                    "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "Action_Type": "Form Submission",
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