import streamlit as st
import pandas as pd

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="DM Co-Pilot", page_icon="🐉", layout="wide")

# --- LOAD DATA ---
@st.cache_data
def load_monster_data():
    try:
        df = pd.read_csv("monsters.csv")
        return df
    except FileNotFoundError:
        return None

monster_df = load_monster_data()

# --- SIDEBAR NAVIGATION ---
st.sidebar.title("🐉 DM Co-Pilot")
st.sidebar.markdown("Your all-in-one Campaign Management Platform.")

# TIP JAR
st.sidebar.markdown("---")
st.sidebar.subheader("☕ Support the Creator")
st.sidebar.write("If this tool saved your campaign, consider throwing a gold piece my way!")
st.sidebar.markdown("[**☕ Tip the Developer**](https://buymeacoffee.com/calebmccombs)")

# API Key Input 
st.sidebar.markdown("---")
st.sidebar.subheader("⚙️ Settings")

with st.sidebar.expander("❓ How to get a free API Key"):
    st.write("1. Go to [GroqCloud Console](https://console.groq.com/keys).")
    st.write("2. Log in or create a completely free account.")
    st.write("3. Click **Create API Key**.")
    st.write("4. Copy the key and paste it in the box below!")
    st.caption("Note: Groq's Meta Llama 3.1 API is currently 100% free to use!")

groq_api_key = st.sidebar.text_input("Enter Groq API Key:", type="password")

# Create the menu buttons (6 PILLARS)
page = st.sidebar.radio(
    "Navigation",
    ["🤝 Campaign Matchmaker", "⚔️ Encounter Architect", "📜 Session Scribe", "🎭 Quick Improv Tools", "🌍 Worldbuilder's Forge", "🎲 Skill Challenge Architect"]
)

st.sidebar.markdown("---")
st.sidebar.caption("Powered by Python, Pandas, SQL & Meta Llama 3.1 (Groq)")

# --- PILLAR 1: CAMPAIGN MATCHMAKER ---
if page == "🤝 Campaign Matchmaker":
    st.title("🤝 Campaign Matchmaker")
    st.write("Filter players by timezone and playstyle, and let Llama 3.1 analyze bios for table compatibility.")
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("🐉 Dungeon Master Profile")
        dm_timezone = st.selectbox("DM Timezone", ["PST", "MST", "CST", "EST", "GMT"])
        dm_style = st.slider("DM Playstyle (0=Heavy Combat, 100=Heavy Roleplay)", 0, 100, 50)
        dm_pitch = st.text_area("Campaign Pitch", "A grimdark, high-stakes campaign set in a cursed forest. Death is permanent.")
        
    with col2:
        st.subheader("🛡️ Player Profile")
        player_timezone = st.selectbox("Player Timezone", ["PST", "MST", "CST", "EST", "GMT"], index=0)
        player_style = st.slider("Player Preference (0=Heavy Combat, 100=Heavy Roleplay)", 0, 100, 80)
        player_bio = st.text_area("Player Bio", "I love deep character interactions and solving mysteries. Not a huge fan of dungeon crawls.")

    st.markdown("---")
    if st.button("Run Matchmaker Engine", type="primary"):
        style_difference = abs(dm_style - player_style)
        if dm_timezone != player_timezone:
            st.error("❌ Match Failed: Timezone Mismatch. Players dropped from queue.")
        elif style_difference > 20:
            st.warning(f"⚠️ Match Failed: Playstyle difference is {style_difference} points. Your logic requires a difference of 20 or less.")
        else:
            st.success("✅ Match Passed! Sending to Llama 3.1...")
            if not groq_api_key:
                st.info("💡 Enter your Groq API key in the sidebar to unlock Llama 3.1's AI analysis!")
            else:
                with st.spinner("Analyzing compatibility..."):
                    try:
                        from groq import Groq
                        client = Groq(api_key=groq_api_key)
                        prompt = f"""
                        ACT AS A MATCHMAKER. 
                        DM Pitch: '{dm_pitch}'. 
                        Player Bio: '{player_bio}'. 
                        Give a compatibility score and a 2-sentence campaign intro blending both.
                        """
                        chat_completion = client.chat.completions.create(messages=[{"role": "user", "content": prompt}], model="llama-3.1-8b-instant")
                        st.write(chat_completion.choices[0].message.content)
                    except Exception as e:
                        st.error(f"Error connecting to Groq: {e}")

# --- PILLAR 2: ENCOUNTER ARCHITECT ---
elif page == "⚔️ Encounter Architect":
    st.title("⚔️ Encounter Architect")
    st.write("Math-free combat balancing and active encounter tracking.")
    tab1, tab2 = st.tabs(["🐉 Official 5.5e Monsters", "🛠️ Homebrew CR Calculator"])
    
    with tab1:
        st.subheader("Active Combat Tracker")
        if monster_df is not None:
            min_cr, max_cr = st.slider("Select Challenge Rating (CR) Range", 0, 30, (1, 5))
            filtered_df = monster_df[(monster_df['CR'] >= min_cr) & (monster_df['CR'] <= max_cr)]
            combat_df = filtered_df[['Name', 'Sourcebook', 'CR', 'HP', 'AC', 'DPR']].copy()
            combat_df.insert(3, 'Current HP', combat_df['HP'])
            st.caption("Double-click any cell in the 'Current HP' column to actively track damage!")
            st.data_editor(combat_df, width="stretch", hide_index=True)
            st.scatter_chart(filtered_df, x='CR', y='HP', color='#ff4b4b')
        else:
            st.error("⚠️ `monsters.csv` not found!")

    with tab2:
        st.subheader("Homebrew Monster CR Estimator")
        col_hp, col_ac, col_dmg = st.columns(3)
        with col_hp: homebrew_hp = st.number_input("Hit Points (HP)", min_value=1, value=50)
        with col_ac: homebrew_ac = st.number_input("Armor Class (AC)", min_value=1, value=13)
        with col_dmg: homebrew_dpr = st.number_input("Damage Per Round (DPR)", min_value=1, value=10)
        if st.button("Calculate Estimated CR"):
            final_cr = max(0, round(((homebrew_hp / 15) + ((homebrew_ac - 13) / 2) + (homebrew_dpr / 5)) / 2))
            st.success(f"⚔️ **Estimated Challenge Rating: CR {final_cr}**")

# --- PILLAR 3: SESSION SCRIBE ---
elif page == "📜 Session Scribe":
    st.title("📜 Session Scribe")
    st.write("Paste raw bullet points below, and the AI will rewrite them into a narrative summary.")
    raw_notes = st.text_area("Session Notes", height=200)
    if st.button("Generate Epic Summary", type="primary"):
        if raw_notes and groq_api_key:
            with st.spinner("Weaving notes into a story..."):
                try:
                    from groq import Groq
                    client = Groq(api_key=groq_api_key)
                    prompt = f"""
                    Turn these D&D session notes into a dramatic 3-paragraph journal entry: 
                    {raw_notes}
                    """
                    chat_completion = client.chat.completions.create(messages=[{"role": "user", "content": prompt}], model="llama-3.1-8b-instant")
                    story = chat_completion.choices[0].message.content
                    st.write(story)
                    st.download_button("📥 Download for Notion/Obsidian (.md)", story, "session_summary.md", "text/markdown", width="stretch")
                except Exception as e: st.error(e)
        else: st.warning("Please enter notes and an API key.")

# --- PILLAR 4: QUICK IMPROV TOOLS ---
elif page == "🎭 Quick Improv Tools":
    st.title("🎭 Quick Improv Tools")
    st.write("For when your players completely ignore your prepared notes.")
    
    with st.expander("🧙‍♂️ The 'Oh Crap' NPC Generator"):
        npc_prompt = st.text_input("Who did the party just talk to?", "A suspicious tavern keeper with a limp")
        if st.button("Generate NPC") and groq_api_key:
            with st.spinner("Summoning NPC..."):
                from groq import Groq
                client = Groq(api_key=groq_api_key)
                prompt = f"""
                Create a D&D NPC: '{npc_prompt}'. 
                Give Name, Quirk, and Secret.
                """
                res = client.chat.completions.create(messages=[{"role": "user", "content": prompt}], model="llama-3.1-8b-instant").choices[0].message.content
                st.write(res)
                st.download_button("💾 Download NPC Card", res, "NPC_Card.md", "text/markdown", width="stretch")
                
    with st.expander("💰 The 'Loot Anxiety' Curer"):
        party_level = st.slider("Average Party Level", 1, 20, 3)
        loot_location = st.text_input("Location Found", "A dusty goblin treasury")
        if st.button("Forge Balanced Loot") and groq_api_key:
            with st.spinner("Forging item..."):
                from groq import Groq
                client = Groq(api_key=groq_api_key)
                prompt = f"""
                Create ONE balanced, flavorful D&D magic item for a Level {party_level} party found in '{loot_location}'. 
                Format: Name, Appearance, Mechanic.
                """
                res = client.chat.completions.create(messages=[{"role": "user", "content": prompt}], model="llama-3.1-8b-instant").choices[0].message.content
                st.write(res)
                st.download_button("💾 Download Loot Card", res, "Loot_Card.md", "text/markdown", width="stretch")

    with st.expander("🍻 The Tavern Generator"):
        tavern_wealth = st.selectbox("Tavern Wealth Level", ["Grimey Slum", "Working Class", "Adventurer's Hub", "High-Society District"])
        if st.button("Generate Tavern") and groq_api_key:
            with st.spinner("Pouring drinks..."):
                from groq import Groq
                client = Groq(api_key=groq_api_key)
                prompt = f"""
                Create a D&D tavern in a {tavern_wealth} area. 
                Provide: 1. Tavern Name. 2. Barkeep's name/personality. 3. Signature Drink/Dish. 4. One juicy local rumor.
                """
                res = client.chat.completions.create(messages=[{"role": "user", "content": prompt}], model="llama-3.1-8b-instant").choices[0].message.content
                st.write(res)
                st.download_button("💾 Download Tavern Notes", res, "Tavern_Notes.md", "text/markdown", width="stretch")
                
    with st.expander("🛍️ The Magic Shop Inventory"):
        shop_vibe = st.text_input("Shop Vibe", "A shady back-alley dwarven vendor")
        shop_level = st.slider("Party Level (Scales Gold Costs)", 1, 20, 4)
        if st.button("Generate Inventory") and groq_api_key:
            with st.spinner("Stocking shelves..."):
                from groq import Groq
                client = Groq(api_key=groq_api_key)
                prompt = f"""
                Create a D&D magic shop inventory for '{shop_vibe}'. 
                Generate exactly 5 items. Provide a Markdown table with columns: Item Name, Brief Description, and GP Cost (balanced for level {shop_level} characters).
                """
                res = client.chat.completions.create(messages=[{"role": "user", "content": prompt}], model="llama-3.1-8b-instant").choices[0].message.content
                st.write(res)
                st.download_button("💾 Download Shop Inventory", res, "Magic_Shop.md", "text/markdown", width="stretch")

# --- PILLAR 5: WORLDBUILDER'S FORGE ---
elif page == "🌍 Worldbuilder's Forge":
    st.title("🌍 Worldbuilder's Forge")
    col_type, col_theme = st.columns(2)
    with col_type: lore_type = st.selectbox("What are we building?", ["A bustling city", "A forgotten ruin", "A powerful faction", "A pantheon deity"])
    with col_theme: lore_theme = st.text_input("Core Theme or Vibe", "Steampunk but with corrupted magic crystals")
    if st.button("Forge Lore", type="primary") and groq_api_key:
        with st.spinner(f"Forging {lore_type.lower()}..."):
            from groq import Groq
            client = Groq(api_key=groq_api_key)
            prompt = f"""
            Subject: {lore_type}. 
            Theme: {lore_theme}. 
            Output in Markdown: ### 👁️ Visual Description, ### 📜 Key History, ### 🪝 Hidden Plot Hook.
            """
            res = client.chat.completions.create(messages=[{"role": "user", "content": prompt}], model="llama-3.1-8b-instant").choices[0].message.content
            st.write(res)
            st.download_button("📥 Download Lore for Obsidian/Notion (.md)", res, "world_lore.md", "text/markdown", width="stretch")

# --- PILLAR 6: SKILL CHALLENGE ARCHITECT ---
elif page == "🎲 Skill Challenge Architect":
    st.title("🎲 Skill Challenge Architect")
    st.write("Instantly generate cinematic skill challenges for chases, escapes, and hazards.")
    scenario = st.text_area("What cinematic scenario is the party facing?", "Fleeing a collapsing volcanic temple while carrying a heavy artifact.")
    if st.button("Generate Skill Challenge", type="primary"):
        if not groq_api_key:
            st.info("💡 Enter your Groq API key in the sidebar to unlock this feature!")
        else:
            with st.spinner("Designing obstacles..."):
                try:
                    from groq import Groq
                    client = Groq(api_key=groq_api_key)
                    prompt = f"""
                    Act as an expert D&D 5e game designer. Create a 3-stage Skill Challenge for this scenario: "{scenario}".
                    Output EXACTLY 3 stages. For each stage, provide:
                    - **The Obstacle:** What is happening right now?
                    - **Primary Skill:** The most obvious skill to use (and its DC).
                    - **Creative Alternative:** Another way players might solve it.
                    - **Failure Consequence:** What happens if they fail this specific check?
                    """
                    chat_completion = client.chat.completions.create(
                        messages=[{"role": "user", "content": prompt}],
                        model="llama-3.1-8b-instant", 
                    )
                    challenge_output = chat_completion.choices[0].message.content
                    st.success("🎲 **Skill Challenge Ready:**")
                    st.write(challenge_output)
                    st.download_button(
                        label="📥 Download Challenge (.md)",
                        data=challenge_output,
                        file_name="skill_challenge.md",
                        mime="text/markdown",
                        width="stretch"
                    )
                except Exception as e:
                    st.error(f"Error connecting to Groq: {e}")