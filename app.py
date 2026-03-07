import streamlit as st
import pandas as pd
import streamlit_analytics2 as streamlit_analytics
import random
from datetime import datetime
import os
import json
import requests
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
        return res
    except Exception as e:
        return f"❌ Error: {str(e)}"

# --- 🚀 MAIN APP ---
try:
    firestore_key = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
    analytics_context = streamlit_analytics.track(firestore_key_file=firestore_key, firestore_collection_name="dm_copilot_traffic")
except Exception:
    analytics_context = streamlit_analytics.track()

with analytics_context:
    st.sidebar.markdown("<h2 style='text-align: center;'>🐉 DM CO-PILOT</h2>", unsafe_allow_html=True)
    
    llm_provider = st.sidebar.radio("Engine", ["☁️ Groq (Cloud)", "💻 Ollama (Local)"])
    user_api_key = st.sidebar.text_input("Groq API Key", type="password") if llm_provider == "☁️ Groq (Cloud)" else ""
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🎨 Premium Tools")
    st.sidebar.caption("BYOK Mode Active")
    user_openai_key = st.sidebar.text_input("OpenAI API Key", type="password")
    openai_key = user_openai_key if user_openai_key else st.secrets.get("OPENAI_API_KEY")

    st.sidebar.markdown("---")
    page = st.sidebar.radio("Navigation", [
        "📜 DM's Guide", 
        "🆕 Patch Notes", 
        "🛡️ Initiative Tracker",
        "🐉 Monster Bestiary",
        "🎨 Image Generator", 
        "🎙️ Audio Scribe", 
        "📚 PDF-Lore Chat", 
        "⚔️ Encounter Architect", 
        "🍻 Tavern Rumor Mill", 
        "💰 Dynamic Shops", 
        "💎 Magic Item Artificer", 
        "📫 Give Feedback"
    ])

    st.sidebar.markdown("---")
    st.sidebar.markdown('<div style="text-align: center;"><a href="https://buymeacoffee.com/calebmccombs" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 40px !important;width: 145px !important;" ></a></div>', unsafe_allow_html=True)

    if page == "📜 DM's Guide":
        st.title("📜 Welcome to the DM Co-Pilot")
        st.markdown("<div class='stat-card'>### System Online\nSelect a tool from the sidebar to begin.</div>", unsafe_allow_html=True)

    elif page == "🆕 Patch Notes":
        st.title("🆕 Patch Notes")
        st.info("📣 **BYOK Model Implemented:** To keep the app free, Image and Audio tools now use your own OpenAI API keys.")
        st.success("✅ **NEW: Monster Bestiary Integration!** Search 400+ monsters and sync them to initiative.")
        st.success("📝 **v2.2 Update:** Added 'Download Stat Block' feature to the Bestiary for physical table prep.")

    elif page == "🛡️ Initiative Tracker":
        st.title("🛡️ Initiative Tracker v2.1")
        with st.expander("➕ Add Combatant"):
            c1, c2, c3 = st.columns(3)
            name = c1.text_input("Name")
            init = c2.number_input("Roll", value=10)
            hp = c3.number_input("HP", value=15)
            if st.button("Add"):
                st.session_state.combatants.append({"name": name, "init": init, "hp": hp, "status": "Healthy"})
                st.session_state.combatants = sorted(st.session_state.combatants, key=lambda x: x['init'], reverse=True)
                st.rerun()
        
        for idx, c in enumerate(st.session_state.combatants):
            cols = st.columns([3, 1, 1, 1])
            cols[0].write(f"**{c['name']}**")
            cols[1].write(f"⚔️ {c['init']}")
            cols[2].write(f"❤️ {c['hp']}")
            if cols[3].button("🗑️", key=f"del_{idx}"):
                st.session_state.combatants.pop(idx)
                st.rerun()

    elif page == "🐉 Monster Bestiary":
        st.title("🐉 Monster Bestiary (SRD)")
        search_query = st.text_input("Search for a monster (e.g., 'Beholder', 'Orc', 'Dragon')")
        
        if search_query:
            with st.spinner("Searching ancient scrolls..."):
                try:
                    response = requests.get(f"https://api.open5e.com/monsters/?search={search_query}")
                    if response.status_code == 200:
                        results = response.json().get('results', [])
                        if results:
                            for monster in results[:5]:
                                with st.container():
                                    st.markdown(f"### {monster['name']} (CR: {monster['challenge_rating']})")
                                    st.write(f"**HP:** {monster['hit_points']} | **AC:** {monster['armor_class']} | **Speed:** {monster['speed']}")
                                    st.write(f"*Size:* {monster['size']} {monster['type']} ({monster['alignment']})")
                                    
                                    col_a, col_b = st.columns(2)
                                    with col_a:
                                        if st.button(f"➕ Add {monster['name']} to Initiative", key=f"add_{monster['slug']}"):
                                            st.session_state.combatants.append({
                                                "name": monster['name'], 
                                                "init": random.randint(1, 20), 
                                                "hp": monster['hit_points'], 
                                                "status": "Healthy"
                                            })
                                            st.session_state.combatants = sorted(st.session_state.combatants, key=lambda x: x['init'], reverse=True)
                                            st.success(f"{monster['name']} joined the fray!")
                                    
                                    with col_b:
                                        monster_stats_text = f"{monster['name']} (CR: {monster['challenge_rating']})\nHP: {monster['hit_points']} | AC: {monster['armor_class']}\nSpeed: {monster['speed']} | Size: {monster['size']}\nType: {monster['type']}\n\nDescription: {monster.get('description', 'No description available.')}"
                                        st.download_button(
                                            label=f"📥 Download {monster['name']} Stats",
                                            data=monster_stats_text,
                                            file_name=f"{monster['slug']}_stats.txt",
                                            mime="text/plain",
                                            key=f"dl_{monster['slug']}"
                                        )
                                    st.markdown("---")
                        else:
                            st.warning("No monsters found.")
                    else:
                        st.error("Connection to Bestiary API failed.")
                except Exception as e:
                    st.error(f"Error fetching data: {e}")

    elif page == "🎨 Image Generator":
        st.title("🎨 AI Image Artificer")
        prompt = st.text_area("Description")
        if st.button("Forge Image"):
            if not openai_key: st.error("Enter OpenAI Key in Sidebar")
            else:
                client = OpenAI(api_key=openai_key)
                response = client.images.generate(model="dall-e-3", prompt=prompt)
                st.image(response.data[0].url)

    elif page == "📚 PDF-Lore Chat":
        st.title("📚 PDF-Lore Chat")
        pdf = st.file_uploader("Upload Lore", type="pdf")
        q = st.text_input("Ask a question:")
        if pdf and q and st.button("Query"):
            reader = PyPDF2.PdfReader(pdf)
            text = "".join([p.extract_text() for p in reader.pages[:3]])
            st.write(get_ai_response(f"Context: {text}\nQuestion: {q}", llm_provider, user_api_key))

    # --- 🎲 QUICK DICE ROLLER ---
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
