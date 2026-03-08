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

# --- NEW: FIRESTORE IMPORTS FOR THE VAULT ---
from google.oauth2 import service_account
from google.cloud import firestore

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

# --- 🚀 MAIN APP & DATABASE INIT ---
try:
    # 1. Load the secrets
    firestore_key = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
    
    # 2. Start the Analytics
    analytics_context = streamlit_analytics.track(firestore_key_file=firestore_key, firestore_collection_name="dm_copilot_traffic")
    
    # 3. Create custom Database Connection for the Vault
    creds = service_account.Credentials.from_service_account_info(firestore_key)
    db = firestore.Client(credentials=creds, project=firestore_key["project_id"])

except Exception as e:
    st.error(f"Database connection failed: {e}")
    analytics_context = streamlit_analytics.track()
    db = None # Failsafe if secrets are missing

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
        "📜 Session Recap",
        "🛡️ Initiative Tracker",
        "🐉 Monster Bestiary",
        "🎨 Image Generator", 
        "📚 PDF-Lore Chat", 
        "⚔️ Encounter Architect",
        "🏛️ Community Vault", 
        "🍻 Tavern Rumor Mill", 
        "💰 Dynamic Shops", 
        "💎 Magic Item Artificer"
    ])

    st.sidebar.markdown("---")
    st.sidebar.markdown('<div style="text-align: center;"><a href="https://buymeacoffee.com/calebmccombs" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 40px !important;width: 145px !important;" ></a></div>', unsafe_allow_html=True)

    if page == "📜 DM's Guide":
        st.title("📜 Welcome to the DM Co-Pilot")
        st.markdown(f"""
        <div class='stat-card'>
        ### System Online
        **Developer:** Caleb McCombs | Microsoft & Springboard Certified Analyst
        <br>Bridge the gap between raw data and legendary storytelling.
        </div>
        """, unsafe_allow_html=True)
        st.info("Select a tool from the sidebar to begin your adventure.")

    elif page == "🆕 Patch Notes":
        st.title("🆕 Patch Notes")
        st.success("✅ **v2.3 Update:** Added AI Session Chronicler for player recaps!")
        st.success("✅ **v2.2 Update:** Monster Bestiary now includes text stat block exports.")

    elif page == "📜 Session Recap":
        st.title("📜 AI Session Chronicler")
        st.info("Paste your raw notes (NPCs, loot, kills) and I'll forge a professional recap.")
        raw_notes = st.text_area("Your Notes:", height=200)
        if st.button("Generate Recap"):
            prompt = f"Summarize these notes into a dramatic recap for players with sections for 'Major Events', 'Loot', and 'Remaining Mysteries':\n\n{raw_notes}"
            recap = get_ai_response(prompt, llm_provider, user_api_key)
            st.markdown(f"<div class='stat-card'>{recap}</div>", unsafe_allow_html=True)
            st.download_button("📥 Download Recap", recap, file_name="session_recap.txt")

    elif page == "🛡️ Initiative Tracker":
        st.title("🛡️ Initiative Tracker v2.1")
        with st.expander("➕ Add Combatant"):
            c1, c2, c3 = st.columns(3)
            name = c1.text_input("Name")
            init = c2.number_input("Roll", value=10)
            hp = c3.number_input("HP", value=15)
            if st.button("Add"):
                st.session_state.combatants.append({"name": name, "init": init, "hp": hp})
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
        search_query = st.text_input("Search monster...")
        if search_query:
            response = requests.get(f"https://api.open5e.com/monsters/?search={search_query}")
            if response.status_code == 200:
                results = response.json().get('results', [])
                for monster in results[:3]:
                    st.markdown(f"### {monster['name']} (CR: {monster['challenge_rating']})")
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button(f"➕ Add to Initiative", key=f"add_{monster['slug']}"):
                            st.session_state.combatants.append({"name": monster['name'], "init": random.randint(1,20), "hp": monster['hit_points']})
                            st.success(f"{monster['name']} added!")
                    with c2:
                        data = f"{monster['name']}\nHP: {monster['hit_points']} | AC: {monster['armor_class']}\n{monster.get('description', '')}"
                        st.download_button("📥 Download Stats", data, file_name=f"{monster['slug']}.txt")
                    st.markdown("---")

    elif page == "🎨 Image Generator":
        st.title("🎨 AI Image Artificer")
        prompt = st.text_area("Art Prompt:")
        if st.button("Forge Image"):
            if not openai_key: st.error("Enter OpenAI Key in Sidebar")
            else:
                client = OpenAI(api_key=openai_key)
                response = client.images.generate(model="dall-e-3", prompt=prompt)
                st.image(response.data[0].url)

    elif page == "📚 PDF-Lore Chat":
        st.title("📚 PDF-Lore Chat")
        pdf = st.file_uploader("Upload PDF", type="pdf")
        q = st.text_input("Question:")
        if pdf and q and st.button("Query"):
            reader = PyPDF2.PdfReader(pdf)
            text = "".join([p.extract_text() for p in reader.pages[:3]])
            st.write(get_ai_response(f"Context: {text}\nQuestion: {q}", llm_provider, user_api_key))

    # --- 🏛️ NEW: COMMUNITY VAULT LOGIC ---
    elif page == "🏛️ Community Vault":
        st.title("🏛️ The Community Vault")
        st.markdown("Welcome to the Vault! Share your best generated monsters, encounters, and items with the 400+ DMs using DM Co-Pilot.")
        
        if db is None:
            st.error("Database connection offline. Cannot access the Vault.")
        else:
            with st.expander("➕ Publish a New Creation", expanded=False):
                creator_name = st.text_input("Your DM Name / Handle", value="Anonymous DM")
                creation_title = st.text_input("Name of this Creation", placeholder="e.g., The Shadow Goblin Ambush")
                creation_type = st.selectbox("Type", ["Monster", "Encounter", "Loot Hoard", "Magic Item"])
                creation_content = st.text_area("Paste the Content/JSON here:")
                
                if st.button("Publish to Vault 🚀"):
                    if creation_title and creation_content:
                        try:
                            doc_ref = db.collection("community_vault").document()
                            doc_ref.set({
                                "creator": creator_name,
                                "title": creation_title,
                                "type": creation_type,
                                "content": creation_content,
                                "timestamp": firestore.SERVER_TIMESTAMP
                            })
                            st.success(f"Legendary! '{creation_title}' is now in the Community Vault.")
                            st.balloons()
                        except Exception as e:
                            st.error(f"Failed to publish. Error: {e}")
                    else:
                        st.warning("Please provide a title and content!")
            
            st.divider()
            
            st.subheader("🔍 Browse Community Creations")
            if st.button("🔄 Refresh Vault"):
                pass 
                
            try:
                vault_docs = db.collection("community_vault").order_by("timestamp", direction=firestore.Query.DESCENDING).limit(10).stream()
                
                found_items = False
                for doc in vault_docs:
                    found_items = True
                    data = doc.to_dict()
                    with st.expander(f"{data.get('type', 'Item')} | {data.get('title', 'Untitled')} (by {data.get('creator', 'Unknown')})"):
                        st.text(data.get('content', 'No content available.'))
                        st.download_button("📥 Download", data.get('content', ''), file_name=f"{data.get('title', 'vault_item')}.txt", key=doc.id)
                
                if not found_items:
                    st.info("The Vault is currently empty. Be the first to publish something!")
            except Exception as e:
                st.error(f"Could not load the Vault. Error: {e}")

    # --- 🔐 PASSWORD PROTECTED ADMIN DASHBOARD ---
    st.sidebar.markdown("---")
    if st.sidebar.checkbox("🛠️ Admin Dashboard"):
        password = st.sidebar.text_input("Enter Dev Password", type="password")
        if password == "Caleb2026": 
            try:
                st.sidebar.success("Access Granted")
                streamlit_analytics.show_results()
            except Exception as e:
                st.sidebar.warning("Dashboard error during surge.")
        elif password:
            st.sidebar.error("Access Denied")
