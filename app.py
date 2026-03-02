import streamlit as st
import pandas as pd
import streamlit_analytics2 as streamlit_analytics
import json 
import PyPDF2 
# We ripped out chromadb and added our lightweight math libraries!
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="DM Co-Pilot", page_icon="🐉", layout="wide")

# --- ANALYTICS SETUP ---
ANALYTICS_PASSWORD = st.secrets["analytics_password"]

with streamlit_analytics.track(unsafe_password=ANALYTICS_PASSWORD):

    # --- LOAD DATA ---
    @st.cache_data
    def load_monster_data():
        try:
            df = pd.read_csv("monsters.csv")
            return df
        except FileNotFoundError:
            return None

    @st.cache_data
    def load_spell_data():
        try:
            df = pd.read_csv("spells.csv")
            return df
        except FileNotFoundError:
            return None

    monster_df = load_monster_data()
    spell_df = load_spell_data()

    # --- SIDEBAR NAVIGATION ---
    st.sidebar.title("🐉 DM Co-Pilot")
    st.sidebar.markdown("Your all-in-one Campaign Management Platform.")

    st.sidebar.markdown("---")
    st.sidebar.subheader("☕ Support the Creator")
    st.sidebar.write("If this tool saved your campaign, consider throwing a gold piece my way!")
    st.sidebar.markdown("[**☕ Tip the Developer**](https://buymeacoffee.com/calebmccombs)")

    # --- AI PROVIDER SETTINGS ---
    st.sidebar.markdown("---")
    st.sidebar.subheader("⚙️ AI Settings")

    llm_provider = st.sidebar.radio("AI Provider", ["☁️ Groq (Cloud)", "💻 Ollama (Local)"])

    groq_api_key = ""
    local_model = ""

    if llm_provider == "☁️ Groq (Cloud)":
        with st.sidebar.expander("❓ How to get a free API Key"):
            st.write("1. Go to [GroqCloud Console](https://console.groq.com/keys).")
            st.write("2. Log in or create a completely free account.")
            st.write("3. Click **Create API Key**.")
            st.write("4. Copy the key and paste it in the box below!")
            st.caption("Note: Groq's Meta Llama 3.1 API is currently 100% free to use!")
        groq_api_key = st.sidebar.text_input("Enter Groq API Key:", type="password")
    else:
        st.sidebar.success("Running completely offline!")
        local_model = st.sidebar.selectbox("Select Local Model", ["llama3.1", "llama3", "mistral"])
        st.sidebar.caption("Make sure the Ollama app is running on your machine.")
        st.sidebar.warning("Note: Local mode only works when running the app locally on your computer, not via the live web URL.")

    # --- MAIN NAVIGATION ---
    page = st.sidebar.radio(
        "Navigation",
        [
            "🤝 Campaign Matchmaker", 
            "⚔️ Encounter Architect", 
            "📜 Session Scribe", 
            "🎭 Quick Improv Tools", 
            "🌍 Worldbuilder's Forge", 
            "🎲 Skill Challenge Architect",
            "🧠 Campaign Analyst"
        ]
    )
    st.sidebar.markdown("---")
    st.sidebar.caption("Powered by Python, Pandas, SQL & Meta Llama 3.1")

    # ==========================================
    # --- AI HELPER FUNCTION ---
    # ==========================================
    def get_ai_response(prompt_text):
        if llm_provider == "☁️ Groq (Cloud)":
            if not groq_api_key:
                st.warning("⚠️ Please enter your Groq API key in the sidebar.")
                st.stop()
            try:
                from groq import Groq
                client = Groq(api_key=groq_api_key)
                chat_completion = client.chat.completions.create(
                    messages=[{"role": "user", "content": prompt_text}], 
                    model="llama-3.1-8b-instant"
                )
                return chat_completion.choices[0].message.content
            except Exception as e:
                st.error(f"Error connecting to Groq: {e}")
                st.stop()
        else:
            try:
                import ollama
                response = ollama.chat(
                    model=local_model, 
                    messages=[{"role": "user", "content": prompt_text}]
                )
                return response['message']['content']
            except Exception as e:
                st.error(f"Error connecting to local Ollama: {e}. Is the Ollama app running?")
                st.stop()

    # ==========================================
    # --- APP PILLARS ---
    # ==========================================

    if page == "🤝 Campaign Matchmaker":
        st.title("🤝 Campaign Matchmaker")
        st.write("Filter players by timezone and playstyle, and let the AI analyze bios for table compatibility.")
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
                st.success("✅ Match Passed! Sending to AI...")
                with st.spinner("Analyzing compatibility..."):
                    prompt = f"ACT AS A MATCHMAKER. DM Pitch: '{dm_pitch}'. Player Bio: '{player_bio}'. Give a compatibility score and a 2-sentence campaign intro blending both."
                    result = get_ai_response(prompt)
                    st.write(result)

    elif page == "⚔️ Encounter Architect":
        st.title("⚔️ Encounter Architect")
        st.write("Math-free combat balancing and active encounter tracking.")
        
        tab1, tab2, tab3 = st.tabs(["🐉 Official 5.5e Monsters", "🛠️ Homebrew CR Calculator", "✨ Spell Grimoire"])
        
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
                
        with tab3:
            st.subheader("Interactive Spell Grimoire")
            if spell_df is not None:
                st.write("Filter and search through the arcane archives.")
                if 'Level' in spell_df.columns:
                    min_lvl, max_lvl = st.slider("Select Spell Level Range", 0, 9, (0, 3))
                    filtered_spells = spell_df[(spell_df['Level'] >= min_lvl) & (spell_df['Level'] <= max_lvl)]
                else:
                    filtered_spells = spell_df
                st.dataframe(filtered_spells, width="stretch", hide_index=True)
            else:
                st.info("⚠️ `spells.csv` not found! To use this feature, upload a CSV file named 'spells.csv' to your GitHub repository with columns like 'Name', 'Level', and 'Description'.")

    elif page == "📜 Session Scribe":
        st.title("📜 Session Scribe")
        st.write("Generate an epic narrative summary of your last session from raw text or audio.")
        
        tab_text, tab_audio = st.tabs(["📝 Text Notes", "🎙️ Live Audio Transcription"])
        
        with tab_text:
            raw_notes = st.text_area("Paste Raw Session Notes", height=200)
            if st.button("Generate Epic Summary", type="primary"):
                if raw_notes:
                    with st.spinner("Weaving notes into a story..."):
                        prompt = f"Turn these D&D session notes into a dramatic 3-paragraph journal entry: {raw_notes}"
                        result = get_ai_response(prompt)
                        st.write(result)
                        st.download_button("📥 Download for Notion/Obsidian (.md)", result, "session_summary.md", "text/markdown", width="stretch")
                else: 
                    st.warning("Please enter notes to summarize.")
                    
        with tab_audio:
            st.info("Upload a voice memo recap of your session. The AI will transcribe it and turn it into a journal entry!")
            audio_file = st.file_uploader("Upload Audio (.mp3, .wav, .m4a)", type=["mp3", "wav", "m4a"])
            
            if st.button("Transcribe & Summarize", type="primary"):
                if llm_provider == "💻 Ollama (Local)":
                    st.error("⚠️ Audio transcription currently requires the Groq Cloud API. Please switch providers in the sidebar to use this feature.")
                elif not groq_api_key:
                    st.warning("⚠️ Please enter your Groq API key in the sidebar.")
                elif audio_file:
                    with st.spinner("🎙️ Transcribing audio with Whisper (this might take a minute)..."):
                        try:
                            from groq import Groq
                            client = Groq(api_key=groq_api_key)
                            
                            transcription = client.audio.transcriptions.create(
                                file=(audio_file.name, audio_file.getvalue()),
                                model="whisper-large-v3"
                            )
                            transcript_text = transcription.text
                            st.success("✅ Transcription complete! Now weaving into a story...")
                            
                            with st.expander("👀 View Raw Transcript"):
                                st.write(transcript_text)
                            
                            with st.spinner("Weaving transcript into a story..."):
                                prompt = f"Turn these transcribed D&D session notes into a dramatic 3-paragraph journal entry: {transcript_text}"
                                result = get_ai_response(prompt)
                                st.write(result)
                                st.download_button("📥 Download Summary (.md)", result, "audio_summary.md", "text/markdown", width="stretch")
                                
                        except Exception as e:
                            st.error(f"Error during audio transcription: {e}")
                else:
                    st.warning("Please upload an audio file.")

    elif page == "🎭 Quick Improv Tools":
        st.title("🎭 Quick Improv Tools")
        st.write("For when your players completely ignore your prepared notes.")
        
        with st.expander("🧙‍♂️ The 'Oh Crap' NPC Generator"):
            npc_prompt = st.text_input("Who did the party just talk to?", "A suspicious tavern keeper with a limp")
            if st.button("Generate NPC"):
                with st.spinner("Summoning NPC..."):
                    prompt = f"Create a D&D NPC: '{npc_prompt}'. Give Name, Quirk, and Secret."
                    result = get_ai_response(prompt)
                    st.write(result)
                    st.download_button("💾 Download NPC Card", result, "NPC_Card.md", "text/markdown", width="stretch")
                    
        with st.expander("💰 The 'Loot Anxiety' Curer"):
            party_level = st.slider("Average Party Level", 1, 20, 3)
            loot_location = st.text_input("Location Found", "A dusty goblin treasury")
            
            if st.button("Forge Balanced Loot"):
                with st.spinner("Forging item..."):
                    prompt = f"""Act as an expert D&D 5e game designer. Create ONE balanced, flavorful magic item for a Level {party_level} party found in '{loot_location}'.

You MUST respond with ONLY a valid JSON object. Do NOT wrap the output in markdown code blocks. Do NOT include any conversational text before or after the JSON.

Use this exact JSON structure:
{{
  "name": "Item Name",
  "type": "weapon",
  "system": {{
    "description": {{
      "value": "Detailed appearance and mechanical effects go here."
    }},
    "source": "DM Co-Pilot",
    "rarity": "rare",
    "price": {{
      "value": 500,
      "denomination": "gp"
    }},
    "attunement": true
  }}
}}"""
                    raw_result = get_ai_response(prompt) 
                    
                    try:
                        json_data = json.loads(raw_result) 
                        st.success("✅ Item successfully forged!")
                        st.json(json_data) 
                        st.download_button(
                            label="📥 Export for Foundry VTT (.json)", 
                            data=raw_result, 
                            file_name="magic_item.json", 
                            mime="application/json",
                            width="stretch" 
                        )
                    except json.JSONDecodeError:
                        st.error("⚠️ The AI failed to format the item correctly. Please click Forge again!")
                        st.code(raw_result) 

        with st.expander("🍻 The Tavern Generator"):
            tavern_wealth = st.selectbox("Tavern Wealth Level", ["Grimey Slum", "Working Class", "Adventurer's Hub", "High-Society District"])
            if st.button("Generate Tavern"):
                with st.spinner("Pouring drinks..."):
                    prompt = f"Create a D&D tavern in a {tavern_wealth} area. Provide: 1. Tavern Name. 2. Barkeep's name/personality. 3. Signature Drink/Dish. 4. One juicy local rumor."
                    result = get_ai_response(prompt)
                    st.write(result)
                    st.download_button("💾 Download Tavern Notes", result, "Tavern_Notes.md", "text/markdown", width="stretch")
                    
        with st.expander("🛍️ The Magic Shop Inventory"):
            shop_vibe = st.text_input("Shop Vibe", "A shady back-alley dwarven vendor")
            shop_level = st.slider("Party Level (Scales Gold Costs)", 1, 20, 4)
            if st.button("Generate Inventory"):
                with st.spinner("Stocking shelves..."):
                    prompt = f"Create a D&D magic shop inventory for '{shop_vibe}'. Generate exactly 5 items. Provide a Markdown table with columns: Item Name, Brief Description, and GP Cost (balanced for level {shop_level} characters)."
                    result = get_ai_response(prompt)
                    st.write(result)
                    st.download_button("💾 Download Shop Inventory", result, "Magic_Shop.md", "text/markdown", width="stretch")

    elif page == "🌍 Worldbuilder's Forge":
        st.title("🌍 Worldbuilder's Forge")
        col_type, col_theme = st.columns(2)
        with col_type: lore_type = st.selectbox("What are we building?", ["A bustling city", "A forgotten ruin", "A powerful faction", "A pantheon deity"])
        with col_theme: lore_theme = st.text_input("Core Theme or Vibe", "Steampunk but with corrupted magic crystals")
        if st.button("Forge Lore", type="primary"):
            with st.spinner(f"Forging {lore_type.lower()}..."):
                prompt = f"Subject: {lore_type}. Theme: {lore_theme}. Output in Markdown: ### 👁️ Visual Description, ### 📜 Key History, ### 🪝 Hidden Plot Hook."
                result = get_ai_response(prompt)
                st.write(result)
                st.download_button("📥 Download Lore for Obsidian/Notion (.md)", result, "world_lore.md", "text/markdown", width="stretch")

    elif page == "🎲 Skill Challenge Architect":
        st.title("🎲 Skill Challenge Architect")
        st.write("Instantly generate cinematic skill challenges for chases, escapes, and hazards.")
        scenario = st.text_area("What cinematic scenario is the party facing?", "Fleeing a collapsing volcanic temple while carrying a heavy artifact.")
        if st.button("Generate Skill Challenge", type="primary"):
            with st.spinner("Designing obstacles..."):
                prompt = f"""Act as an expert D&D 5e game designer. Create a 3-stage Skill Challenge for this scenario: "{scenario}".
                Output EXACTLY 3 stages. For each stage, provide:
                - **The Obstacle:** What is happening right now?
                - **Primary Skill:** The most obvious skill to use (and its DC).
                - **Creative Alternative:** Another way players might solve it.
                - **Failure Consequence:** What happens if they fail this specific check?"""
                result = get_ai_response(prompt)
                st.success("🎲 **Skill Challenge Ready:**")
                st.write(result)
                st.download_button(label="📥 Download Challenge (.md)", data=result, file_name="skill_challenge.md", mime="text/markdown", width="stretch")

    # ==========================================
    # --- CAMPAIGN ANALYST & WIKI (SCIKIT-LEARN FIX) ---
    # ==========================================
    elif page == "🧠 Campaign Analyst":
        st.title("🧠 Campaign Analyst & Wiki")
        
        tab_analyst, tab_wiki = st.tabs(["📝 Past Session Analyzer", "📚 Campaign Wiki (RAG)"])
        
        with tab_analyst:
            st.write("Paste your previous session summaries here. The AI will analyze your campaign, find forgotten plot threads, and predict what you should prep next.")
            past_sessions = st.text_area(
                "Past Session Notes/Summaries", 
                height=300, 
                placeholder="Paste the text from your previous sessions here..."
            )
            
            if st.button("Analyze Campaign", type="primary"):
                if not past_sessions:
                    st.warning("⚠️ Please paste some session notes to analyze!")
                else:
                    with st.spinner("Analyzing campaign data..."):
                        prompt = f"""Act as an expert D&D Campaign Manager and Narrative Analyst.
                        Analyze the following past session summaries:
                        {past_sessions}
                        Provide a detailed report structured EXACTLY with these 3 Markdown headers:
                        ### 🧵 Unresolved Plot Threads
                        ### 🧠 Player Psychology
                        ### 🔮 Next Session Prep Recommendations"""
                        result = get_ai_response(prompt)
                        st.success("🧠 **Campaign Analysis Complete:**")
                        st.write(result)
                        st.download_button("📥 Download Analysis (.md)", result, "campaign_analysis.md", "text/markdown", width="stretch")
        
        with tab_wiki:
            st.write("Upload a massive lore PDF, and the app will chop it into manageable data chunks for the AI to read.")
            
            uploaded_pdf = st.file_uploader("Upload Campaign Lore (PDF)", type="pdf")
            
            if uploaded_pdf is not None:
                st.success(f"✅ Loaded: {uploaded_pdf.name}")
                
                with st.spinner("Extracting text from PDF..."):
                    pdf_reader = PyPDF2.PdfReader(uploaded_pdf)
                    raw_text = ""
                    for page in pdf_reader.pages:
                        raw_text += page.extract_text() + "\n"
                        
                with st.spinner("Chopping text into chunks..."):
                    words = raw_text.split()
                    chunk_size = 500
                    chunks = [' '.join(words[i:i + chunk_size]) for i in range(0, len(words), chunk_size)]
                    
                st.success(f"🔪 Successfully chopped into {len(chunks)} searchable chunks!")
                
                # --- NEW SCIKIT-LEARN RAG LOGIC ---
                if len(chunks) > 0:
                    with st.spinner("🧠 Converting chunks into mathematical vectors (this takes just a second)..."):
                        vectorizer = TfidfVectorizer()
                        tfidf_matrix = vectorizer.fit_transform(chunks)
                    
                    st.success("✅ AI Memory successfully built! The document is ready to be searched.")
                    
                    st.markdown("---")
                    st.subheader("💬 Chat with your Lore")
                    
                    user_question = st.chat_input("Ask a question about the uploaded document...")
                    
                    if user_question:
                        with st.chat_message("user"):
                            st.write(user_question)
                            
                        with st.spinner("Searching the archives..."):
                            # Transform the question and calculate similarity
                            question_vec = vectorizer.transform([user_question])
                            similarities = cosine_similarity(question_vec, tfidf_matrix).flatten()
                            
                            # Get the top 3 most similar chunks
                            top_3_indices = similarities.argsort()[-3:][::-1]
                            top_chunks = [chunks[i] for i in top_3_indices]
                            
                            retrieved_context = "\n\n".join(top_chunks)
                            
                            rag_prompt = f"""Act as the Dungeon Master's assistant. Use ONLY the following context to answer the question. If the answer is not in the context, say "I cannot find this in the uploaded lore."
                            
                            CONTEXT:
                            {retrieved_context}
                            
                            QUESTION:
                            {user_question}"""
                            
                            answer = get_ai_response(rag_prompt)
                            
                            with st.chat_message("assistant"):
                                st.write(answer)
                                
                                with st.expander("👀 View Retrieved Context"):
                                    st.write(retrieved_context)