import streamlit as st
import pandas as pd
import streamlit_analytics2 as streamlit_analytics
import random
from datetime import datetime
import os
import json
import plotly.express as px
import PyPDF2 
from openai import OpenAI 

# --- 🚑 TRAFFIC SURGE PATCH FOR ANALYTICS ---
import streamlit_analytics2.display as sa2_display
if not hasattr(sa2_display, "original_show_results"):
    sa2_display.original_show_results = sa2_display.show_results
def safe_show_results(data, reset_data, unsafe_password):
    safe_data = data.copy()
    safe_data["widgets"] = data.get("widgets", {}).copy()
    return sa2_display.original_show_results(safe_data, reset_data, unsafe_password)
sa2_display.show_results = safe_show_results

st.set_page_config(page_title="DM Co-Pilot | Masterwork Edition", page_icon="🐉", layout="wide")

# --- 🌌 THEME & STYLING ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=MedievalSharp&display=swap');
    [data-testid="stAppViewContainer"] { background-color: #000000 !important; }
    [data-testid="stAppViewContainer"] p, label, li { color: #00FF00 !important; font-family: monospace !important; }
    h1, h2, h3 { font-family: 'MedievalSharp', cursive; color: #00FF00 !important; text-shadow: 0 0 10px #00FF00; }
    [data-testid="stSidebar"] { background-color: #000000 !important; border-right: 2px solid #00FF00 !important; }
    .stat-card {background-color: #0a0a0a !important; border: 1px solid #00FF00 !important; padding: 15px; border-radius: 8px; border-left: 10px solid #00FF00 !important; color: #00FF00 !important; margin-bottom: 10px; }
    .stButton>button {background-color: #000000 !important; color: #00FF00 !important; border: 2px solid #00FF00 !important; width: 100%; transition: 0.3s; }
    .stButton>button:hover { background-color: #00FF00 !important; color: #000000 !important; }
    .dice-result { font-size: 1.5rem; font-weight: bold; color: #00FF00; text-align: center; border: 2px dashed #00FF00; padding: 5px; margin-top: 5px; }
    span[data-testid="stExpanderIcon"] { color: #00FF00 !important; }
</style>
""", unsafe_allow_html=True)

# --- ⚙️ HELPER LOGIC ---
if 'session_log' not in st.session_state:
    st.session_state.session_log = f"--- DM Co-Pilot Session Log ({datetime.now().strftime('%Y-%m-%d')}) ---\n"
if 'ai_outputs' not in st.session_state:
    st.session_state.ai_outputs = {}
if 'combatants' not in st.session_state:
    st.session_state.combatants = []

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

# --- 🚀 MAIN APP WITH FIRESTORE ---
try:
    firestore_key = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
    analytics_context = streamlit_analytics.track(firestore_key_file=firestore_key, firestore_collection_name="dm_copilot_traffic")
except Exception:
    analytics_context = streamlit_analytics.track()

with analytics_context:
    st.sidebar.markdown("<h2 style='text-align: center;'>🐉 DM CO-PILOT</h2>", unsafe_allow_html=True)
    
    st.sidebar.markdown("---")
    llm_provider = st.sidebar.radio("Engine", ["☁️ Groq (Cloud)", "💻 Ollama (Local)"])
    user_api_key = st.sidebar.text_input("Groq API Key", type="password") if llm_provider == "☁️ Groq (Cloud)" else ""
    
    # --- 🔑 OPENAI BYOK VERIFIER (Bring Your Own Key) ---
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🎨 Premium Tools")
    st.sidebar.caption("Due to high traffic, Image & Audio tools currently require your own key. (See Patch Notes)")
    user_openai_key = st.sidebar.text_input("OpenAI API Key", type="password", help="DALL-E 3 & Whisper require an OpenAI Key. Get yours at platform.openai.com")
    
    # Prioritize user input, fallback to dev secret if empty
    openai_key = user_openai_key if user_openai_key else st.secrets.get("OPENAI_API_KEY")

    if not openai_key:
        st.sidebar.warning("⚠️ OpenAI Key needed for Art & Audio")
    else:
        st.sidebar.success("✅ OpenAI Engine Armed")

    st.sidebar.markdown("---")
    page = st.sidebar.radio("Navigation", [
        "📜 DM's Guide", 
        "🆕 Patch Notes & Roadmap", 
        "🛡️ Initiative Tracker", 
        "🎨 Image Generator", 
        "🎙️ Audio Scribe", 
        "📚 PDF-Lore Chat", 
        "🤝 Matchmaker", 
        "⚔️ Encounter Architect", 
        "🏰 Dungeon Map Generator", 
        "🍻 Tavern Rumor Mill", 
        "💰 Dynamic Shops", 
        "🧩 Trap Architect", 
        "🎭 NPC Quick-Forge", 
        "💎 Magic Item Artificer", 
        "💰 Loot Hoard", 
        "📫 Give Feedback"
    ])

    # --- ☕ TIP JAR: BUY ME A COFFEE ---
    st.sidebar.markdown("---")
    st.sidebar.markdown("""
    <div style="text-align: center;">
        <a href="https://buymeacoffee.com/calebmccombs" target="_blank">
            <img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 40px !important;width: 145px !important;" >
        </a>
    </div>
    """, unsafe_allow_html=True)

    # --- 🎲 SIDEBAR DICE ROLLER ---
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🎲 Quick-Roll")
    d_col1, d_col2 = st.sidebar.columns(2)
    with d_col1:
        if st.button("d20"): st.session_state.last_roll = f"d20: {random.randint(1, 20)}"
        if st.button("d10"): st.session_state.last_roll = f"d10: {random.randint(1, 10)}"
    with d_col2:
        if st.button("d12"): st.session_state.last_roll = f"d12: {random.randint(1, 12)}"
        if st.button("d8"): st.session_state.last_roll = f"d8: {random.randint(1, 8)}"
    if "last_roll" in st.session_state:
        st.sidebar.markdown(f"<div class='dice-result'>{st.session_state.last_roll}</div>", unsafe_allow_html=True)

    # --- PAGE LOGIC ---
    if page == "📜 DM's Guide":
        st.title("📜 Welcome to the DM Co-Pilot")
        st.markdown("<div class='stat-card'>### System Online\nSelect a tool from the sidebar to begin.</div>", unsafe_allow_html=True)

    elif page == "🆕 Patch Notes & Roadmap":
        st.title("🆕 Patch Notes & Roadmap")
        st.success("🔥 **MAJOR UPDATE: THE MASTERWORK v2.0 EDITION**")
        
        # --- NEW ANNOUNCEMENT BLOCK ---
        st.info("""
        📣 **DEV UPDATE ON API KEYS:** Wow, the traffic today has been insane! Thank you all for checking out the app. Because image generation (DALL-E 3) and audio transcription are expensive, my personal API budget hit its limit today. 
        
        To keep the core tools (like the Initiative Tracker and Generators) 100% free, the **Image Artificer** and **Audio Scribe** now require you to plug in your own OpenAI API key in the sidebar. 
        
        If you guys would rather I handle the API costs for everyone, I would have to charge a small subscription fee to use the app to cover it. Let me know what you prefer in the **📫 Give Feedback** tab! For now, the power is in your hands.
        """)
        
        st.markdown("""
        ### 🚀 Live Today
        * **🛡️ Initiative Tracker v2.0:** Now tracks Max HP and Status Conditions for every combatant.
        * **🎨 AI Image Artificer:** Generate visual art for your characters and items using DALL-E 3. *(Requires own OpenAI Key)*
        * **🎙️ Audio Scribe:** AI-powered session summaries via Whisper. *(Requires own OpenAI Key)*
        * **📚 PDF-Lore Chat:** Talk directly to your homebrew PDFs.
        """)

    elif page == "🛡️ Initiative Tracker":
        st.title("🛡️ Initiative Tracker v2.0")
        st.markdown("Track turn order, HP, and status conditions.")
        
        with st.expander("➕ Add Combatant", expanded=True):
            c_col1, c_col2, c_col3 = st.columns([2, 1, 1])
            with c_col1: c_name = st.text_input("Name")
            with c_col2: c_init = st.number_input("Init Roll", value=10)
            with c_col3: c_hp = st.number_input("Max HP", value=20)
            c_status = st.selectbox("Condition", ["Healthy", "Blinded", "Charmed", "Deafened", "Frightened", "Grappled", "Incapacitated", "Paralyzed", "Petrified", "Poisoned", "Prone", "Restrained", "Stunned", "Unconscious"])
            
            if st.button("Add to Combat"):
                if c_name:
                    st.session_state.combatants.append({"name": c_name, "init": c_init, "hp": c_hp, "status": c_status})
                    st.session_state.combatants = sorted(st.session_state.combatants, key=lambda x: x['init'], reverse=True)
                    st.rerun()

        if st.session_state.combatants:
            for idx, c in enumerate(st.session_state.combatants):
                with st.container():
                    cols = st.columns([3, 1, 1, 2, 0.5])
                    cols[0].write(f"**{c['name']}**")
                    cols[1].write(f"⚔️ {c['init']}")
                    cols[2].write(f"❤️ {c['hp']}")
                    cols[3].write(f"✨ {c['status']}")
                    if cols[4].button("🗑️", key=f"del_{idx}"):
                        st.session_state.combatants.pop(idx)
                        st.rerun()
            if st.button("🧹 Clear All Combatants"):
                st.session_state.combatants = []
                st.rerun()

    elif page == "🎨 Image Generator":
        st.title("🎨 AI Image Artificer")
        st.markdown("Visualize your NPCs, monsters, or legendary items using DALL-E 3. *(Requires your own OpenAI API Key in the sidebar)*")
        img_prompt = st.text_area("Describe the image (e.g., 'A battle-scarred Orc chieftain in heavy plate armor, digital art style')")
        
        if st.button("Forge Image"):
            if not openai_key:
                st.error("❌ Action blocked: Please enter a valid OpenAI API Key in the sidebar.")
            elif img_prompt:
                with st.spinner("Channeling artistic energy..."):
                    try:
                        client = OpenAI(api_key=openai_key)
                        response = client.images.generate(model="dall-e-3", prompt=img_prompt, n=1, size="1024x1024")
                        st.image(response.data[0].url, caption=img_prompt)
                    except Exception as e:
                        st.error(f"Error: {e}")
            else:
                st.warning("Please enter a description.")

    elif page == "🎙️ Audio Scribe":
        st.title("🎙️ Audio Scribe")
        st.markdown("*(Requires your own OpenAI API Key in the sidebar)*")
        audio_file = st.file_uploader("Upload Session Audio", type=["mp3", "wav", "m4a"])
        if audio_file and st.button("Transcribe"):
            if not openai_key:
                st.error("❌ OpenAI Key missing. Enter it in the sidebar.")
            else:
                with st.spinner("Processing..."):
                    client = OpenAI(api_key=openai_key)
                    transcript = client.audio.transcriptions.create(model="whisper-1", file=audio_file)
                    st.session_state.ai_outputs["audio"] = get_ai_response(f"Summarize this D&D session transcript: {transcript.text}", llm_provider, user_api_key)
        if "audio" in st.session_state.ai_outputs:
            st.markdown(f"<div class='stat-card'>{st.session_state.ai_outputs['audio']}</div>", unsafe_allow_html=True)

    elif page == "📚 PDF-Lore Chat":
        st.title("📚 PDF-Lore Chat")
        pdf_file = st.file_uploader("Upload Lore PDF", type="pdf")
        query = st.text_input("Ask a question about your lore:")
        if pdf_file and query and st.button("Consult Archives"):
            reader = PyPDF2.PdfReader(pdf_file)
            context = "".join([p.extract_text() for p in reader.pages[:5]])
            st.session_state.ai_outputs["lore"] = get_ai_response(f"Using this context: {context}\n\nAnswer: {query}", llm_provider, user_api_key)
        if "lore" in st.session_state.ai_outputs:
            st.markdown(f"<div class='stat-card'>{st.session_state.ai_outputs['lore']}</div>", unsafe_allow_html=True)

    elif page == "🤝 Matchmaker":
        st.title("🤝 Campaign Matchmaker")
        user_pref = st.text_area("What kind of game do your players want?")
        if st.button("Generate Pitches"):
            st.session_state.ai_outputs["match"] = get_ai_response(f"Generate 3 campaign pitches for: {user_pref}", llm_provider, user_api_key)
        if "match" in st.session_state.ai_outputs:
            st.markdown(f"<div class='stat-card'>{st.session_state.ai_outputs['match']}</div>", unsafe_allow_html=True)

    elif page == "⚔️ Encounter Architect":
        st.title("⚔️ Encounter Architect")
        boss_mode = st.toggle("Enable 'Boss Mode'")
        e_lvl = st.slider("Party Level", 1, 20, 5)
        e_theme = st.text_input("Theme", placeholder="e.g., Undead swamp")
        if st.button("Build Encounter"):
            st.session_state.ai_outputs["enc"] = get_ai_response(f"Build a level {e_lvl} encounter: {e_theme}. Boss Mode: {boss_mode}", llm_provider, user_api_key)
        if "enc" in st.session_state.ai_outputs:
            st.markdown(f"<div class='stat-card'>{st.session_state.ai_outputs['enc']}</div>", unsafe_allow_html=True)

    elif page == "🏰 Dungeon Map Generator":
        st.title("🏰 Tactical Dungeon Map Generator")
        if st.button("Generate Layout"):
            grid = ["".join(random.choices([".", "#", "?"], weights=[75, 20, 5], k=12)) for _ in range(12)]
            st.session_state.ai_outputs["map_grid"] = "\n".join(grid)
            st.session_state.ai_outputs["map_desc"] = get_ai_response("Describe a tactical D&D battlemap.", llm_provider, user_api_key)
        if "map_grid" in st.session_state.ai_outputs:
            st.code(st.session_state.ai_outputs["map_grid"])
            st.markdown(f"<div class='stat-card'>{st.session_state.ai_outputs.get('map_desc', '')}</div>", unsafe_allow_html=True)

    elif page == "🍻 Tavern Rumor Mill":
        st.title("🍻 Tavern Rumor Mill")
        loc = st.text_input("Location Name", "The Sword Coast")
        if st.button("Listen for Rumors"):
            st.session_state.ai_outputs["rumor"] = get_ai_response(f"Generate 3 rumors for {loc}: one true, one false, one dangerously misleading.", llm_provider, user_api_key)
        if "rumor" in st.session_state.ai_outputs:
            st.markdown(f"<div class='stat-card'>{st.session_state.ai_outputs['rumor']}</div>", unsafe_allow_html=True)

    elif page == "💰 Dynamic Shops":
        st.title("💰 Dynamic Shops")
        shop_type = st.selectbox("Shop Type", ["Blacksmith", "Alchemist", "Curio Shop"])
        if st.button("Open Shop"):
            st.session_state.ai_outputs["shop"] = get_ai_response(f"Generate a {shop_type} with a quirky shopkeeper.", llm_provider, user_api_key)
        if "shop" in st.session_state.ai_outputs:
            st.markdown(f"<div class='stat-card'>{st.session_state.ai_outputs['shop']}</div>", unsafe_allow_html=True)

    elif page == "🧩 Trap Architect":
        st.title("🧩 Trap Architect")
        if st.button("Construct Trap"):
            st.session_state.ai_outputs["trap"] = get_ai_response("Design a trap.", llm_provider, user_api_key)
        if "trap" in st.session_state.ai_outputs:
            st.markdown(f"<div class='stat-card'>{st.session_state.ai_outputs['trap']}</div>", unsafe_allow_html=True)

    elif page == "🎭 NPC Quick-Forge":
        st.title("🎭 NPC Quick-Forge")
        if st.button("Forge NPC"):
            st.session_state.ai_outputs["npc"] = get_ai_response("Create a D&D NPC.", llm_provider, user_api_key)
        if "npc" in st.session_state.ai_outputs:
            st.markdown(f"<div class='stat-card'>{st.session_state.ai_outputs['npc']}</div>", unsafe_allow_html=True)

    elif page == "💎 Magic Item Artificer":
        st.title("💎 Magic Item Artificer")
        rarity = st.selectbox("Rarity", ["Common", "Uncommon", "Rare", "Very Rare", "Legendary"])
        cursed = st.checkbox("Attach Narrative Curse")
        if st.button("Forge Item"):
            prompt = f"Design a {rarity} magic item."
            if cursed: prompt += " Include a deeply unsettling narrative curse."
            st.session_state.ai_outputs["magic"] = get_ai_response(prompt, llm_provider, user_api_key)
        if "magic" in st.session_state.ai_outputs:
            st.markdown(f"<div class='stat-card'>{st.session_state.ai_outputs['magic']}</div>", unsafe_allow_html=True)

    elif page == "💰 Loot Hoard":
        st.title("💰 Loot Hoard Generator")
        cr = st.slider("Monster CR", 0, 30, 5)
        if st.button("Generate Hoard"):
            gp = random.randint(10, 100) * cr
            st.session_state.ai_outputs["loot"] = f"**Hoard Found:** {gp} Gold Pieces."
            st.session_state.ai_outputs["loot_desc"] = get_ai_response(f"Flavorful loot for CR {cr}.", llm_provider, user_api_key)
        if "loot" in st.session_state.ai_outputs:
            st.markdown(f"<div class='stat-card'>{st.session_state.ai_outputs['loot']}\n\n{st.session_state.ai_outputs.get('loot_desc', '')}</div>", unsafe_allow_html=True)

    elif page == "📫 Give Feedback":
        st.title("📫 Tavern Suggestion Box")
        star_rating = st.radio("Rate your experience!", ["⭐", "⭐⭐", "⭐⭐⭐", "⭐⭐⭐⭐", "⭐⭐⭐⭐⭐"], index=4, horizontal=True)
        user_feedback = st.text_area("What should we add next?")
        if st.button("Submit Feedback"):
            try:
                from streamlit_gsheets import GSheetsConnection
                conn = st.connection("gsheets", type=GSheetsConnection)
                new_data = pd.DataFrame({"Timestamp": [datetime.now()], "Stars": [star_rating], "Feedback": [user_feedback]})
                existing_data = conn.read(worksheet="Sheet1", ttl=5).dropna(how="all")
                conn.update(worksheet="Sheet1", data=pd.concat([existing_data, new_data], ignore_index=True))
                st.success("Message recorded in your Grimoire.")
            except:
                st.error("Feedback link offline, check secrets.")

    # --- 💾 GLOBAL EXPORT LOGIC ---
    st.sidebar.markdown("---")
    adventure_content = f"# 🐉 DELVER'S GRIMOIRE: ADVENTURE EXPORT\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
    for key, val in st.session_state.ai_outputs.items():
        adventure_content += f"## {key.replace('_', ' ').upper()}\n{val}\n\n"
    st.sidebar.download_button("📥 Download Full Adventure (.md)", adventure_content, file_name=f"Adventure_{datetime.now().strftime('%m%d')}.md")
    st.sidebar.download_button("📥 Export Session Log (RAW)", st.session_state.session_log, file_name="DM_Log.txt")
