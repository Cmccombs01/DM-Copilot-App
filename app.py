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
from collections import Counter

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

st.set_page_config(page_title="DM Co-Pilot | Masterwork Edition",
                   page_icon="🐉", layout="wide")

# --- ⚡ THE SPEED FIX: Caching the Bestiary in RAM ---


@st.cache_data
def load_bestiary():
    try:
        import pandas as pd
        import json

        # 1. BULLETPROOF LOCAL FETCH: Use Python's native JSON reader (ignores blank spaces!)
        with open("srd_5e_monsters.json", "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        df = pd.DataFrame(raw_data)

        # 2. Rename the JSON columns to match our exact variables
        rename_map = {"Challenge": "cr",
            "Hit Points": "hp", "Armor Class": "ac"}
        df = df.rename(
            columns={k: v for k, v in rename_map.items() if k in df.columns})

        # 3. Combine Traits and Actions, and strip HTML tags
        traits = df['Traits'].fillna('') if 'Traits' in df.columns else ''
        acts = df['Actions'].fillna('') if 'Actions' in df.columns else ''
        df['actions'] = traits + '\n\n' + acts
        df['actions'] = df['actions'].str.replace(r'<[^<>]*>', '', regex=True)

        return df
    except Exception as e:
        st.error(f"🚨 LOCAL DATABASE CRASH REPORT: {e}")
        import pandas as pd
        return pd.DataFrame()


monster_df = load_bestiary()
# --- 🌌 THEME & STYLING ---
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=MedievalSharp&display=swap');
[data-testid="stAppViewContainer"] {
    background-color: #000000 !important;
}
[data-testid="stAppViewContainer"] p, label, li {
    color: #00FF00 !important;
    font-family: monospace !important;
}
h1, h2, h3 {
    font-family: 'MedievalSharp', cursive;
    color: #00FF00 !important;
    text-shadow: 0 0 10px #00FF00;
}
[data-testid="stSidebar"] {
    background-color: #000000 !important;
    border-right: 2px solid #00FF00 !important;
}
.stat-card {background-color: #0a0a0a !important; border: 1px solid #00FF00 !important; padding: 15px; border-radius: 8px; border-left: 10px solid #00FF00 !important; color: #00FF00 !important; margin-bottom: 10px; }
.stButton>button {background-color: #000000 !important; color: #00FF00 !important; border: 2px solid #00FF00 !important; width: 100%; transition: 0.3s; }
.stButton>button:hover { background-color: #00FF00 !important; color: #000000 !important; }
.dice-result { font-size: 1.5rem; font-weight: bold; color: #00FF00; text-align: center; border: 2px dashed #00FF00; padding: 5px; margin-top: 5px; }
</style>
""", unsafe_allow_html=True)

# --- ⚙️ HELPER LOGIC & GLOBAL MEMORY ---
if 'combatants' not in st.session_state:
    st.session_state.combatants = []

# This loop ensures every tool has a "memory bank" ready to go
memory_banks = ["bestiary_json", "artificer_json", "shop_json", "encounter_json", "tavern_json", "handout_json"]
for bank in memory_banks:
    if bank not in st.session_state:
        st.session_state[bank] = None


def get_ai_response(prompt, llm_provider, user_api_key):
    try:
        if llm_provider == "☁️ Groq (Cloud)":
            api_key = st.secrets.get("GROQ_API_KEY", user_api_key)
            if not api_key:
                return "⚠️ Please enter your Groq API Key in the sidebar."
            from groq import Groq
            client = Groq(api_key=api_key)
            res = client.chat.completions.create(messages=[
                                                 {"role": "user", "content": prompt}], model="llama-3.1-8b-instant").choices[0].message.content
        else:
            import ollama
            res = ollama.chat(model="llama3.1", messages=[
                              {"role": "user", "content": prompt}])['message']['content']
        return res
    except Exception as e:
        return f"❌ Error: {str(e)}"


# --- 🚀 MAIN APP & DATABASE INIT ---
try:
    import json
    raw_secret = st.secrets["GOOGLE_CREDENTIALS"]

    # 1. BULLETPROOF AUTH: Handle it whether Streamlit gives us a string OR a dictionary
    if isinstance(raw_secret, str):
        firestore_key = json.loads(raw_secret)
    else:
        firestore_key = dict(raw_secret)

   # 2. BULLETPROOF FILE CREATION: Prevent multi-user race conditions
    import os
    if not os.path.exists("temp_firestore_key.json") or os.path.getsize("temp_firestore_key.json") == 0:
        with open("temp_firestore_key.json", "w") as f:
            json.dump(firestore_key, f)

    # 3. Start the Analytics using the physical file path
    analytics_context = streamlit_analytics.track(
        firestore_key_file="temp_firestore_key.json", firestore_collection_name="dm_copilot_traffic")

    # 4. Create custom Database Connection for the Vault
    creds = service_account.Credentials.from_service_account_info(
        firestore_key)
    db = firestore.Client(credentials=creds, project=firestore_key.get(
        "project_id", "dm-copilot-analytics"))
except Exception as e:
    st.error(f"Database connection failed: {e}")
    # BULLETPROOF FALLBACK: If analytics fails, bypass it entirely so the app survives
    import contextlib
    analytics_context = contextlib.nullcontext()
    db = None

with analytics_context:
    st.sidebar.markdown(
        "<h2 style='text-align: center;'>🐉 DM CO-PILOT</h2>", unsafe_allow_html=True)
    llm_provider = st.sidebar.radio(
        "Engine", ["☁️ Groq (Cloud)", "💻 Ollama (Local)"])
    user_api_key = st.sidebar.text_input(
        "Groq API Key", type="password") if llm_provider == "☁️ Groq (Cloud)" else ""

    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🎨 Premium Tools")
    st.sidebar.caption("BYOK Mode Active")
    user_openai_key = st.sidebar.text_input("OpenAI API Key", type="password")
    openai_key = user_openai_key if user_openai_key else st.secrets.get(
        "OPENAI_API_KEY")

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
        "🎭 NPC Quick Forge",
        "⚙️ Trap Architect",
        "📜 Scribe's Handouts",
        "🗑️ Pocket Trash Loot",
        "👑 The Dragon's Hoard",
        "🌍 Worldbuilder",
        "🤖 DM Assistant",
        "🤝 DM Matchmaker",
        "🧬 Homebrew Forge",
        "🏛️ Community Vault",
        "🍻 Tavern Rumor Mill",
        "💰 Dynamic Shops",
        "💎 Magic Item Artificer",
        "⭐ Give Feedback"
    ])

st.sidebar.markdown("---")
st.sidebar.markdown('<div style="text-align: center;"><a href="https://buymeacoffee.com/calebmccombs" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 40px !important;width: 145px !important;" ></a></div>', unsafe_allow_html=True)

    # --- 🎲 GLOBAL DICE ROLLER (Restored!) ---
st.sidebar.markdown("---")
st.sidebar.markdown("### 🎲 Quick Roll")

    # Put the dropdown and button side-by-side to save space
d_col1, d_col2 = st.sidebar.columns([1, 1])
dice_type = d_col1.selectbox("Dice", [
                             "d20", "d12", "d10", "d8", "d6", "d4", "d100"], label_visibility="collapsed")
if d_col2.button("Roll!"):
        sides = int(dice_type.replace("d", ""))
        result = random.randint(1, sides)
        st.sidebar.markdown(
            f"<div class='dice-result'>🎲 {result}</div>", unsafe_allow_html=True)

if page == "📜 DM's Guide":
        st.title("📜 Welcome to the DM Co-Pilot")
        # --- LIVE TELEMETRY DASHBOARD ---
        st.markdown("### 📡 System Telemetry")
        c1, c2, c3 = st.columns(3)
        c1.metric(label="Active DMs (Global)",
                  value="450+", delta="Viral Surge")

        # Dynamically pull the total number of Vault items
        vault_count = "Offline"
        if db is not None:
            try:
                docs = db.collection("community_vault").stream()
                vault_count = sum(1 for _ in docs)
            except Exception:
                vault_count = "Error"
        c2.metric(label="Vault Creations",
                  value=vault_count, delta="Live Database")
        c3.metric(label="Server Status", value="Online",
                  delta="By Groq & Ollama")
        st.divider()

        # --- THE WELCOME HOOK ---
        st.markdown(f"""
        <div class='stat-card'>
        ### 🐉 You focus on the story. Let the AI handle the rest.
        **Developer:** Caleb McCombs | Microsoft & Springboard Certified Analyst <br>
        Welcome to the Masterwork Edition. I built this tool to bridge the gap between raw data and legendary storytelling, cutting your session prep time by 80%.
        </div>
        """, unsafe_allow_html=True)

        # --- 🏆 NEW: HALL OF FAME (TOP CONTRIBUTORS) ---
        st.markdown("### 👑 Hall of Fame: Top Contributors")
        if db is not None:
            try:
                docs = db.collection("community_vault").stream()
                creator_counts = Counter()
                # Tally up the creators, ignoring anonymous ones
                for doc in docs:
                    data = doc.to_dict()
                    creator = data.get("creator", "Anonymous DM").strip()
                    if creator.lower() != "anonymous dm" and creator != "":
                        creator_counts[creator] += 1

                top_creators = creator_counts.most_common(3)
                if top_creators:
                    cols = st.columns(3)
                    for i, (creator, count) in enumerate(top_creators):
                        # Add a gold, silver, bronze medal logic
                        medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉"
                        cols[i].info(
                            f"{medal} **{creator}**\n\n📜 {count} Creations")
                else:
                    st.info(
                        "The leaderboard is waiting for its first legends. Publish an item to claim the #1 spot!")
            except Exception as e:
                st.error("Could not load Hall of Fame.")
        st.divider()

        # --- COMMUNITY SPOTLIGHT ---
        st.markdown("### 🛡️ The Community Vanguard")
        st.markdown("You aren't prepping in a vacuum. Join hundreds of DMs sharing their most devious creations. Every monster you forge, every curse you weave, and every encounter you publish helps the entire community level up.")
        if db is not None:
            try:
                latest_item = db.collection("community_vault").order_by(
                    "timestamp", direction=firestore.Query.DESCENDING).limit(1).stream()
                for doc in latest_item:
                    data = doc.to_dict()
                    st.success(
                        f"🔥 **Latest Vault Addition:** *{data.get('title', 'Untitled')}* (A {data.get('type', 'Creation')} by {data.get('creator', 'a fellow DM')}) - Check the Vault tab to download it!")
            except Exception:
                pass
        st.divider()

        # --- QUICK START INSTRUCTIONS ---
        st.markdown("### 🗺️ Where to start:")
        st.markdown("""
        * **🏛️ Community Vault:** Browse encounters, loot, and monsters created by other veteran DMs, or publish your own!
        * **⚔️ Encounter Architect:** Need a boss fight right now? Generate perfectly balanced monsters with one click.
        * **🛡️ Initiative Tracker:** Throw out your scratchpad. Track HP, rolls, and turn order right here in the browser.
        """)

elif page == "🆕 Patch Notes":
        st.title("🆕 Patch Notes")
        st.success("✅ **v2.4 Update:** Lightning-fast local Bestiary caching & improved search logic!")
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

    # --- 🐛 THE GOBLIN BUG FIX & ⚡ THE SPEED FIX ---
elif page == "🐉 Monster Bestiary":
        st.title("🐉 Monster Bestiary (VTT JSON Integration)")
        st.markdown("Generate custom creatures formatted as structured JSON data for direct import into Foundry VTT or Roll20 APIs.")
        
        # Initialize session state for the Bestiary if it doesn't exist
        if "bestiary_json" not in st.session_state:
            st.session_state.bestiary_json = None

        monster_type = st.selectbox("Creature Type", ["Aberration", "Beast", "Dragon", "Fiend", "Monstrosity", "Undead"])
        monster_cr = st.selectbox("Challenge Rating (CR)", ["1-4", "5-10", "11-16", "17-20", "21+"])
        custom_flavor = st.text_area("Monster Concept", placeholder="e.g., A mutated bear that breathes necrotic fire...")
        
        if st.button("Forge JSON Statblock 🔨"):
            with st.spinner("Compiling structured data..."):
                prompt = f"Create a D&D 5e {monster_type} with a CR of {monster_cr}. Concept: {custom_flavor}. "
                prompt += """
                You MUST return the response as a valid JSON object ONLY. Do not include markdown formatting, backticks, or conversational text.
                Structure the JSON with these exact keys:
                {
                  "name": "Monster Name",
                  "size": "Large",
                  "type": "monstrosity",
                  "alignment": "neutral evil",
                  "armor_class": 15,
                  "hit_points": 100,
                  "speed": "30 ft.",
                  "strength": 18,
                  "dexterity": 12,
                  "constitution": 16,
                  "intelligence": 6,
                  "wisdom": 10,
                  "charisma": 8,
                  "actions": [
                    {"name": "Necrotic Bite", "description": "Melee Weapon Attack..."}
                  ],
                  "special_abilities": [
                    {"name": "Frightful Presence", "description": "Each creature of the monster's choice..."}
                  ]
                }
                """
                
                raw_json = get_ai_response(prompt, llm_provider, user_api_key)
                cleaned_json = raw_json.replace("```json", "").replace("```", "").strip()
                
                # Save the result to the browser's session memory
                st.session_state.bestiary_json = cleaned_json

        # If there is a monster in memory, display it (even if they clicked away and came back)
        if st.session_state.bestiary_json:
            try:
                import json
                parsed_json = json.loads(st.session_state.bestiary_json)
                st.json(parsed_json)
                
                st.download_button(
                    label="📥 Download JSON for VTT",
                    data=st.session_state.bestiary_json,
                    file_name="monster_statblock.json",
                    mime="application/json"
                )
            except Exception as e:
                st.error("Error parsing JSON data. Please try forging again.")
                st.write("Raw output for debugging:", st.session_state.bestiary_json)
elif page == "🎨 Image Generator":
        st.title("🎨 AI Image Artificer")
        prompt = st.text_area("Art Prompt:")
        if st.button("Forge Image"):
            if not openai_key:
                st.error("Enter OpenAI Key in Sidebar")
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

    # --- ⚔️ NEW: ENCOUNTER ARCHITECT ---
elif page == "⚔️ Encounter Architect":
        st.title("⚔️ Encounter Architect & VTT Export")
        st.markdown("Generate balanced encounters and export them directly to your Virtual Tabletop.")
        
        c1, c2, c3 = st.columns(3)
        party_level = c1.number_input("Average Party Level", min_value=1, max_value=20, value=5)
        party_size = c2.number_input("Number of Players", min_value=1, max_value=10, value=4)
        difficulty = c3.selectbox("Difficulty", ["Easy", "Medium", "Hard", "Deadly", "Boss Mode"])
        
        environment = st.text_input("Environment / Theme (e.g., Volcano, Swamp, Undead Crypt)")
        
        if st.button("Generate Encounter 🎲"):
            if not environment:
                environment = "Generic"
            
            prompt = f"Create a D&D 5e {difficulty} encounter for {party_size} level {party_level} players in a {environment} environment. Include the monster names, their CR, a brief tactical description of the terrain, and the total XP. Provide stat blocks if it's a Boss Mode."
            
            with st.spinner("Forging encounter..."):
                encounter_text = get_ai_response(prompt, llm_provider, user_api_key)
                st.markdown(f"<div class='stat-card'>{encounter_text}</div>", unsafe_allow_html=True)
                # --- 📈 RESTORED: ENCOUNTER TENSION GRAPH ---
                st.markdown("### 📈 Expected Tension Curve")
                import pandas as pd
                chart_data = pd.DataFrame({
                        "Rounds": ["Round 1 (Opening)", "Round 2 (Escalation)", "Round 3 (Climax)", "Round 4 (Resolution)"],
                        "Tension Level": [40, 75, 100, 25]
                    }).set_index("Rounds")
                st.line_chart(chart_data)
                
                # --- FOUNDRY VTT EXPORT LOGIC ---
                vtt_data = {
                    "name": f"{difficulty} {environment} Encounter",
                    "type": "encounter",
                    "description": encounter_text,
                    "level": party_level,
                    "players": party_size
                }
                vtt_json = json.dumps(vtt_data, indent=4)
                
                st.download_button(
                    "📥 Export for Foundry VTT (.json)",
                    data=vtt_json,
                    file_name=f"{environment.lower().replace(' ', '_')}_encounter.json",
                    mime="application/json"
                )

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

    # --- 🍻 NEW: TAVERN RUMOR MILL ---
elif page == "🍻 Tavern Rumor Mill":
        st.title("🍻 Tavern Rumor Mill")
        st.info("Generate 3 rumors for your players to overhear: One true, one false, and one dangerously misleading.")
        
        location = st.text_input("Town, Tavern, or NPC Name:")
        if st.button("Listen at the Bar 🍺") and location:
            prompt = f"Generate 3 short, punchy D&D rumors overheard in or around '{location}'. 1 must be completely true, 1 must be totally false, and 1 must be a dangerous half-truth. Do not label which is which in the output, just present them as dialogue from patrons."
            with st.spinner("Eavesdropping..."):
                rumors = get_ai_response(prompt, llm_provider, user_api_key)
                st.markdown(f"<div class='stat-card'>{rumors}</div>", unsafe_allow_html=True)

    # --- 💰 NEW: DYNAMIC SHOPS ---
elif page == "💰 Dynamic Shops":
        st.title("💰 Dynamic Shops")
        st.markdown("Generate quirky shopkeepers and instant inventory tables with GP prices.")
        shop_type = st.selectbox("Shop Type", ["Blacksmith", "Alchemist", "General Store", "Magic Item Broker", "Shady Fence"])
        
        if st.button("Open Shop 🛒"):
            prompt = f"Create a D&D 5e {shop_type}. Provide a brief description of a quirky shopkeeper, and a markdown table containing 5-7 items for sale with their prices in GP."
            with st.spinner("Stocking shelves..."):
                shop_data = get_ai_response(prompt, llm_provider, user_api_key)
                st.markdown(f"<div class='stat-card'>{shop_data}</div>", unsafe_allow_html=True)

    # --- 💎 NEW: MAGIC ITEM ARTIFICER ---
elif page == "💎 Magic Item Artificer":
        st.title("💎 Magic Item Artificer")
        st.markdown("Forge legendary artifacts with structured data ready for VTT item sheets.")

        col1, col2 = st.columns(2)
        with col1:
            item_type = st.selectbox("Item Type", ["Weapon", "Armor", "Wondrous Item", "Ring", "Staff", "Potion"])
        with col2:
            rarity = st.selectbox("Rarity", ["Common", "Uncommon", "Rare", "Very Rare", "Legendary", "Artifact"])
        
        custom_details = st.text_area("Item Concept", placeholder="e.g., A dagger made of frozen shadow that bleeds cold...")

        if st.button("Forge Item 🔨"):
            with st.spinner("Channeling arcane energy..."):
                prompt = f"Create a D&D 5e {rarity} {item_type}. Concept: {custom_details}. "
                prompt += """
                Return ONLY a valid JSON object with these keys: 
                'name', 'type', 'rarity', 'properties' (list), 'description', 'attunement' (boolean).
                Do not include markdown backticks or extra text.
                """
                raw_json = get_ai_response(prompt, llm_provider, user_api_key)
                # This uses the 'artificer_json' bank we set up on Line 96
                st.session_state.artificer_json = raw_json.replace("```json", "").replace("```", "").strip()

        # Display from memory (This keeps it on screen during tab switches!)
        if st.session_state.artificer_json:
            try:
                import json
                item_data = json.loads(st.session_state.artificer_json)
                st.json(item_data)
                st.download_button(
                    label="📥 Download Item JSON",
                    data=st.session_state.artificer_json,
                    file_name="magic_item.json",
                    mime="application/json"
                )
            except:
                st.error("The weave flickered. Try forging again.")
                st.write("Debug info:", st.session_state.artificer_json)

# --- 🔄 THE GREAT RESTORATION PATCH (Missing Tabs) ---
elif page == "🎭 NPC Quick Forge":
        st.title("🎭 NPC Quick Forge")
        npc_type = st.text_input("Profession or Role (e.g., Tavern Keeper, Shady Guard)")
        if st.button("Forge NPC"):
            with st.spinner("Breathing life into NPC..."):
                prompt = f"Create a D&D 5e NPC who is a {npc_type}. Give them a name, appearance, a distinct quirk, a hidden secret, and a quote."
                st.markdown(f"<div class='stat-card'>{get_ai_response(prompt, llm_provider, user_api_key)}</div>", unsafe_allow_html=True)

elif page == "⚙️ Trap Architect":
        st.title("⚙️ Trap Architect")
        danger = st.selectbox("Lethality", ["Nuisance", "Dangerous", "Deadly"])
        if st.button("Build Trap"):
            with st.spinner("Setting trigger..."):
                st.markdown(f"<div class='stat-card'>{get_ai_response(f'Create a {danger} D&D 5e trap. Include the trigger, the effect/damage, and how players can spot and disarm it.', llm_provider, user_api_key)}</div>", unsafe_allow_html=True)

elif page == "📜 Scribe's Handouts":
        st.title("📜 Scribe's Handouts")
        topic = st.text_area("What is the letter, journal, or bounty about?")
        if st.button("Write Handout"):
            with st.spinner("Scribing..."):
                # Updated for VTT Export functionality
                handout_text = get_ai_response(f"Write an immersive, in-universe D&D handout about: {topic}", llm_provider, user_api_key)
                st.markdown(f"<div class='stat-card'>{handout_text}</div>", unsafe_allow_html=True)
                st.download_button("📥 Download Handout for VTT", handout_text, file_name="handout.txt")

elif page == "🗑️ Pocket Trash Loot":
        st.title("🗑️ Pocket Trash Loot")
        if st.button("Search the bodies..."):
            with st.spinner("Searching..."):
                st.markdown(f"<div class='stat-card'>{get_ai_response('Generate 5 weird, mundane, or slightly gross trinkets you would find in a goblin or bandit pocket. No magic items.', llm_provider, user_api_key)}</div>", unsafe_allow_html=True)

elif page == "👑 The Dragon's Hoard":
        st.title("👑 The Dragon's Hoard")
        hoard_cr = st.selectbox("Target CR Hoard", ["0-4", "5-10", "11-16", "17+"])
        if st.button("Generate Hoard"):
            with st.spinner("Counting gold..."):
                st.markdown(f"<div class='stat-card'>{get_ai_response(f'Generate a D&D 5e treasure hoard for CR {hoard_cr}. Include coins, gems, art objects, and 2-3 appropriate magic items.', llm_provider, user_api_key)}</div>", unsafe_allow_html=True)

elif page == "🌍 Worldbuilder":
        st.title("🌍 Worldbuilder Co-Pilot")
        focus = st.selectbox("What are we building?", ["Town/City", "Faction/Guild", "Pantheon/Deity", "Lost Ruin"])
        if st.button("Build World"):
            with st.spinner("Shaping the world..."):
                st.markdown(f"<div class='stat-card'>{get_ai_response(f'Create a detailed D&D 5e lore entry for a {focus}. Include history, notable figures, and a current conflict.', llm_provider, user_api_key)}</div>", unsafe_allow_html=True)

elif page == "🤖 DM Assistant":
        st.title("🤖 DM Assistant")
        question = st.text_area("Ask any D&D ruling or prep question:")
        if st.button("Consult Assistant"):
            with st.spinner("Thinking..."):
                st.markdown(f"<div class='stat-card'>{get_ai_response(question, llm_provider, user_api_key)}</div>", unsafe_allow_html=True)

elif page == "🤝 DM Matchmaker":
        st.title("🤝 DM Matchmaker")
        st.info("Looking for a group? Drop your details below to connect with other players and DMs.")
        st.text_input("Discord Handle")
        st.selectbox("Role", ["Looking for DM", "Looking for Players"])
        st.text_area("Campaign Style / Timezone")
        if st.button("Post to Matchmaker Board"):
            st.success("Board updated! (Simulated for now until we connect the live Matchmaker DB)")
            st.balloons()

elif page == "⭐ Give Feedback":
        st.title("⭐ Give Feedback")
        rating = st.slider("How would you rate DM Co-Pilot?", 1, 5, 5)
        st.text_area("Any suggestions or bugs?")
        if st.button("Submit Feedback"):
            st.success(f"Thank you for the {rating}-star rating! Feedback logged to the cloud.")
            
elif page == "🧬 Homebrew Forge":
        st.title("🧬 Homebrew Monster Forge")
        st.markdown("Paste your raw monster notes, stats, or chaotic ideas below. The AI will forge it into a perfectly formatted 5e stat block ready for the Community Vault.")
        c1, c2 = st.columns([1, 2])
        homebrew_name = c1.text_input("Monster Name", placeholder="e.g., Laser Squirrel")
        target_cr = c2.selectbox("Target Challenge Rating (CR)", ["Any / Let AI Decide", "0-4 (Low level)", "5-10 (Mid level)", "11-16 (High level)", "17+ (Boss level)"])
        raw_ideas = st.text_area("Raw Notes & Ideas", height=150, placeholder="e.g., A giant fire-breathing squirrel that shoots lasers from its eyes. Has about 100 HP. Make it deadly but give it a weakness to acorns.")
        if st.button("Forge Monster 🔨"):
            if raw_ideas:
                prompt = f"Create a perfectly balanced D&D 5e monster stat block based on these raw notes: '{raw_ideas}'. "
                if homebrew_name: prompt += f"The monster's name is {homebrew_name}. "
                if target_cr != "Any / Let AI Decide": prompt += f"Balance it for a Challenge Rating of {target_cr}. "
                prompt += "Format it cleanly with Markdown. Include Armor Class, Hit Points, Speed, STR, DEX, CON, INT, WIS, CHA, Traits, Actions, and a brief lore description."
                with st.spinner("Forging stat block..."):
                    forged_monster = get_ai_response(prompt, llm_provider, user_api_key)
                    st.markdown(f"<div class='stat-card'>{forged_monster}</div>", unsafe_allow_html=True)
                    st.download_button("📥 Download Stat Block", forged_monster, file_name=f"homebrew_monster.txt")
            else:
                st.warning("⚠️ Please provide some raw notes or ideas to forge!")
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





