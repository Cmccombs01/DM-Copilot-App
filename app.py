import streamlit as st
import pandas as pd
import streamlit_analytics2 as streamlit_analytics
import random
from datetime import datetime
import streamlit.components.v1 as components
import logging
from fpdf import FPDF
import altair as alt
import json
import urllib.parse
import os

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
    
    .dungeon-grid {
        font-size: 28px;
        line-height: 1.1;
        letter-spacing: -3px;
        text-align: center;
        background-color: #2c3e50;
        padding: 20px;
        border-radius: 10px;
        border: 4px solid #b22222;
    }
    </style>
    """, unsafe_allow_html=True)

# --- INITIALIZE SESSION STATES ---
if 'session_log' not in st.session_state:
    st.session_state.session_log = f"--- DM Co-Pilot Session Log ({datetime.now().strftime('%Y-%m-%d')}) ---\n"
if 'last_roll' not in st.session_state:
    st.session_state.last_roll = "Roll the dice!"
if 'ai_outputs' not in st.session_state:
    st.session_state.ai_outputs = {}
if 'last_page' not in st.session_state:
    st.session_state.last_page = None

# --- 📊 BACKGROUND DATA LOGGER ---
def log_usage_to_sheet(tool_name, user_input):
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
    
    st.sidebar.markdown("### 🎲 Quick-Roll Tray")
    cols = st.sidebar.columns(3)
    dice = [4, 6, 8, 10, 12, 20]
    for i, d in enumerate(dice):
        if cols[i % 3].button(f"d{d}"):
            roll_result = random.randint(1, d)
            st.session_state.last_roll = f"d{d}: {roll_result}"
            log_usage_to_sheet("Dice Roller", f"Rolled d{d} (Result: {roll_result})")
            
    st.sidebar.markdown(f"<div style='text-align:center; font-size:24px; color:#d4af37; background:rgba(0,0,0,0.3); padding:5px; border-radius:5px;'>{st.session_state.last_roll}</div>", unsafe_allow_html=True)
    
    st.sidebar.markdown("---")
    
    llm_provider = st.sidebar.radio("Engine", ["☁️ Groq (Cloud)", "💻 Ollama (Local)"])
    if llm_provider == "☁️ Groq (Cloud)":
        user_api_key = st.sidebar.text_input("Groq API Key", type="password")
        st.sidebar.caption("🔑 Don't have one? [Get your free Groq API key here!](https://console.groq.com/keys)")
    else:
        user_api_key = ""
        
    st.sidebar.markdown("---")
    
    page = st.sidebar.radio("Navigation", [
        "🤝 Matchmaker", "⚔️ Encounter Architect", "🏰 Dungeon Map Generator",
        "📖 Spellbook Analytics", "🏙️ Instant City Generator", "🧩 Trap Architect",
        "🎭 NPC Quick-Forge", "📜 Scribe's Handouts", "💎 Magic Item Artificer", 
        "💀 Cursed Item Creator", "💰 Dynamic Shop Generator", "🎒 'Pocket Trash' Loot", 
        "🐉 The Dragon's Hoard", "🍻 Tavern Rumor Mill", "🌍 Worldbuilder", 
        "📖 Session Recap Scribe", "🧠 Assistant", "📫 Give Feedback"
    ])
    
    if st.session_state.last_page != page:
        log_usage_to_sheet("Page Navigation", f"Viewed: {page}")
        st.session_state.last_page = page
    
    st.sidebar.download_button("📥 Export Session Log", st.session_state.session_log, file_name="DM_Log.txt", use_container_width=True)

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
            return "❌ The AI engine encountered an error. Please check your API key and try again."

    # --- PAGE LOGIC ---
    if page == "🤝 Matchmaker":
        st.title("🤝 Campaign Matchmaker")
        pitch = st.text_area("The DM's Pitch & Player Preferences", placeholder="e.g. A dark gothic horror game for 4 players...")
        if st.button("Analyze Compatibility"):
            with st.spinner("Analyzing..."):
                st.session_state.ai_outputs["Matchmaker"] = get_ai_response(f'Analyze: {pitch}')
        if "Matchmaker" in st.session_state.ai_outputs:
            st.markdown(f"<div class='stat-card'>{st.session_state.ai_outputs['Matchmaker']}</div>", unsafe_allow_html=True)

    elif page == "⚔️ Encounter Architect":
        st.title("⚔️ Encounter Architect")
        st.markdown("### 📊 Visual Monster Balancer")
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
            except: pass
            crs = [round(random.uniform(0, 30), 2) for _ in range(400)]
            hps = [max(1, int(cr * 15 + random.uniform(-20, 40))) for cr in crs]
            return pd.DataFrame({'Name': [f'Monster {i}' for i in range(1, 401)], 'CR': crs, 'HP': hps})

        m_df = load_monster_data()
        chart = alt.Chart(m_df).mark_circle(size=70, color='#b22222', opacity=0.6).encode(
            x=alt.X('CR:Q', title='Challenge Rating (CR)'),
            y=alt.Y('HP:Q', title='Hit Points (HP)'),
            tooltip=['Name', 'CR', 'HP']
        ).interactive()
        st.altair_chart(chart, use_container_width=True)
        
        h_name = st.text_input("Monster Name", placeholder="e.g. Lava Drake")
        if st.button("Generate Stat Block"):
            with st.spinner("Forging..."):
                st.session_state.ai_outputs["Encounter"] = get_ai_response(f"Generate a 5e stat block for {h_name}")
                st.session_state.ai_outputs["Encounter_Name"] = h_name
                
        if "Encounter" in st.session_state.ai_outputs:
            res = st.session_state.ai_outputs["Encounter"]
            st.markdown(f"<div class='stat-card'>{res.replace('\n', '<br>')}</div>", unsafe_allow_html=True)
            if not res.startswith("❌"):
                col1, col2 = st.columns(2)
                # PDF Download logic here
                foundry_json = {"name": st.session_state.ai_outputs.get("Encounter_Name", "NPC"), "type": "npc", "system": {"details": {"biography": {"value": res}}}}
                col2.download_button("⚙️ Export to Foundry VTT (JSON)", json.dumps(foundry_json, indent=4), f"monster_foundry.json", "application/json", use_container_width=True)

    elif page == "🏰 Dungeon Map Generator":
        st.title("🏰 Procedural Map Generator")
        map_size = st.slider("Select Matrix Size", 5, 15, 8)
        if st.button("Generate Dungeon Matrix"):
            grid = [["⬛" if random.random() < 0.3 else "⬜" for _ in range(map_size)] for _ in range(map_size)]
            grid[0][0], grid[map_size-1][map_size-1] = "🚪", "🐉"
            html_grid = f"<div class='dungeon-grid'>{'<br>'.join([''.join(row) for row in grid])}</div>"
            st.session_state.ai_outputs["Map"] = html_grid
        if "Map" in st.session_state.ai_outputs:
            st.markdown(st.session_state.ai_outputs["Map"], unsafe_allow_html=True)

    elif page == "📖 Spellbook Analytics":
        st.title("📖 Spellbook Data Analytics")
        @st.cache_data
        def load_spell_data():
            try:
                if os.path.exists("dnd-spells.csv"): df = pd.read_csv("dnd-spells.csv")
                elif os.path.exists("spells.csv"): df = pd.read_csv("spells.csv")
                else: raise FileNotFoundError()
                df.columns = [str(col).strip().title() for col in df.columns]
                for target in ['School', 'Level']:
                    if target not in df.columns:
                        for col in df.columns:
                            if target.lower() in col.lower():
                                df.rename(columns={col: target}, inplace=True)
                                break
                return df
            except:
                schools = ["Evocation", "Abjuration", "Necromancy", "Illusion", "Conjuration", "Divination", "Enchantment", "Transmutation"]
                return pd.DataFrame({"Name": [f"Spell {i}" for i in range(150)], "Level": [random.randint(0, 9) for _ in range(150)], "School": [random.choice(schools) for _ in range(150)]})

        spell_df = load_spell_data()
        col1, col2 = st.columns(2)
        with col1:
            st.altair_chart(alt.Chart(spell_df['School'].value_counts().reset_index().rename(columns={'index':'School','School':'Count'})).mark_arc(innerRadius=50).encode(theta='Count:Q', color='School:N'), use_container_width=True)
        with col2:
            st.altair_chart(alt.Chart(spell_df['Level'].value_counts().reset_index().rename(columns={'index':'Level','Level':'Count'})).mark_bar(color='#2e5a88').encode(x='Level:O', y='Count:Q'), use_container_width=True)
        st.dataframe(spell_df, use_container_width=True)

    elif page == "🏙️ Instant City Generator":
        st.title("🏙️ Instant Crowd Generator")
        crowd_size = st.slider("Crowd Size", 5, 50, 15)
        @st.cache_data
        def load_names_data():
            try:
                fname = "dnd_chars_all.tsv" if os.path.exists("dnd_chars_all.tsv") else "dnd_chars_unique.tsv"
                df = pd.read_csv(fname, sep='\t')
                name_col = next((col for col in df.columns if 'name' in col.lower()), None)
                return df[name_col].dropna().tolist() if name_col else ["Brog", "Elara"]
            except: return ["Brog", "Elara", "Thordak", "Sylas"]

        if st.button("Generate Crowd"):
            names = load_names_data()
            profs = ["Blacksmith", "Baker", "Guard", "Merchant", "Noble", "Alchemist"]
            quirks = ["Always sniffing", "Missing an ear", "Carries a pet rat", "Speaks too loudly"]
            st.session_state.ai_outputs["Crowd"] = pd.DataFrame([{"Name": random.choice(names), "Profession": random.choice(profs), "Quirk": random.choice(quirks)} for _ in range(crowd_size)])
        if "Crowd" in st.session_state.ai_outputs:
            st.dataframe(st.session_state.ai_outputs["Crowd"], use_container_width=True, hide_index=True)

    elif page == "📜 Scribe's Handouts":
        st.title("📜 Scribe's Handouts")
        h_style = st.selectbox("Style", ["Wanted Poster", "King's Decree", "Torn Journal Page"])
        msg = st.text_input("Core Hook", placeholder="Wanted for stealing...")
        if st.button("Forge Document & Image Prop"):
            with st.spinner("Writing & Illustrating..."):
                st.session_state.ai_outputs["Handout"] = get_ai_response(f"Write a realistic {h_style}: {msg}")
                safe_prompt = urllib.parse.quote(f"Realistic fantasy {h_style} prop for D&D related to: {msg}")
                st.session_state.ai_outputs["Handout_Image"] = f"https://image.pollinations.ai/prompt/{safe_prompt}?width=512&height=512&nologo=true"
        if "Handout" in st.session_state.ai_outputs:
            st.markdown(f"<div class='handout-card'><h3 style='text-align:center;'>{h_style.upper()}</h3><hr>", unsafe_allow_html=True)
            if "Handout_Image" in st.session_state.ai_outputs: st.image(st.session_state.ai_outputs["Handout_Image"], use_container_width=True)
            st.markdown(f"<br>{st.session_state.ai_outputs['Handout'].replace('\n', '<br>')}</div>", unsafe_allow_html=True)

    # --- OTHER PAGES (NPC, TRAP, SHOP, etc) ---
    elif page == "🎭 NPC Quick-Forge":
        st.title("🎭 The NPC Quick-Forge")
        concept = st.text_input("Concept")
        if st.button("Forge"):
            st.session_state.ai_outputs["NPC"] = get_ai_response(f"Memorable NPC: {concept}")
        if "NPC" in st.session_state.ai_outputs: st.markdown(f"<div class='stat-card'>{st.session_state.ai_outputs['NPC']}</div>", unsafe_allow_html=True)

    elif page == "💀 Cursed Item Creator":
        st.title("💀 Cursed Item Creator")
        theme = st.text_input("Item Theme")
        if st.button("Forge Curse"):
            st.session_state.ai_outputs["Cursed"] = get_ai_response(f"Powerful 5e item with a horrifying curse based on: {theme}")
        if "Cursed" in st.session_state.ai_outputs: st.markdown(f"<div class='stat-card'>{st.session_state.ai_outputs['Cursed']}</div>", unsafe_allow_html=True)

    elif page == "🐉 The Dragon's Hoard":
        st.title("🐉 The Dragon's Hoard")
        tier = st.selectbox("CR Tier", ["CR 0-4", "CR 5-10", "CR 11-16", "CR 17+"])
        if st.button("Generate Hoard"):
            st.session_state.ai_outputs["Hoard"] = get_ai_response(f"Balanced treasure hoard for {tier}")
        if "Hoard" in st.session_state.ai_outputs: st.markdown(f"<div class='stat-card'>{st.session_state.ai_outputs['Hoard']}</div>", unsafe_allow_html=True)

    elif page == "🍻 Tavern Rumor Mill":
        st.title("🍻 Tavern Rumor Mill")
        target = st.text_input("Rumor Subject")
        if st.button("Eavesdrop"):
            st.session_state.ai_outputs["Rumor"] = get_ai_response(f"3 rumors about {target} (1 true, 1 lie, 1 misleading)")
        if "Rumor" in st.session_state.ai_outputs: st.markdown(f"<div class='stat-card'>{st.session_state.ai_outputs['Rumor']}</div>", unsafe_allow_html=True)

    elif page == "📫 Give Feedback":
        st.title("📫 Tavern Suggestion Box")
        from streamlit_gsheets import GSheetsConnection
        conn = st.connection("gsheets", type=GSheetsConnection)
        with st.form("feedback"):
            rating = st.radio("Rating", ["5", "4", "3", "2", "1"], horizontal=True)
            vtt = st.selectbox("VTT", ["Roll20", "Foundry", "Other"])
            idea = st.text_area("Ideas")
            if st.form_submit_button("Submit"):
                sheet_url = "https://docs.google.com/spreadsheets/d/1g6GRCspt8pIEaUpbGdUruiZu8X3wpOIDJNGr9O1lVBo/edit"
                df = conn.read(spreadsheet=sheet_url)
                new_row = pd.DataFrame([{"Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "Action_Type": "Form", "Rating": rating, "VTT": vtt, "Feature_Idea": idea}])
                conn.update(spreadsheet=sheet_url, data=pd.concat([df, new_row], ignore_index=True))
                st.success("Feedback recorded!")