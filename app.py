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

# TIP JAR (MONETIZATION)
st.sidebar.markdown("---")
st.sidebar.subheader("☕ Support the Creator")
st.sidebar.write("If this tool saved your campaign, consider throwing a gold piece my way!")
# YOUR CUSTOM TIP LINK:
st.sidebar.markdown("[**☕ Tip the Developer**](https://buymeacoffee.com/calebmccombs)")

# API Key Input 
st.sidebar.markdown("---")
st.sidebar.subheader("⚙️ Settings")

# THE NEW API WALKTHROUGH
with st.sidebar.expander("❓ How to get a free API Key"):
    st.write("1. Go to [GroqCloud Console](https://console.groq.com/keys).")
    st.write("2. Log in or create a completely free account.")
    st.write("3. Click **Create API Key**.")
    st.write("4. Copy the key and paste it in the box below!")
    st.caption("Note: Groq's Meta Llama 3.1 API is currently 100% free to use!")

groq_api_key = st.sidebar.text_input("Enter Groq API Key:", type="password")

# Create the menu buttons
page = st.sidebar.radio(
    "Navigation",
    ["🤝 Campaign Matchmaker", "⚔️ Encounter Architect", "📜 Session Scribe", "🎭 Quick Improv Tools"]
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
        st.write("### Match Results:")
        style_difference = abs(dm_style - player_style)
        
        if dm_timezone != player_timezone:
            st.error("❌ Match Failed: Timezone Mismatch. Players dropped from queue.")
        elif style_difference > 20:
            st.warning(f"⚠️ Match Failed: Playstyle difference is {style_difference} points. Your logic requires a difference of 20 or less.")
        else:
            st.success(f"✅ Match Passed! Timezones align and playstyles are within range. Sending to Llama 3.1...")
            
            if not groq_api_key:
                st.info("💡 Enter your Groq API key in the sidebar to unlock Llama 3.1's AI analysis!")
            else:
                with st.spinner("Llama 3.1 is analyzing text compatibility..."):
                    try:
                        from groq import Groq
                        client = Groq(api_key=groq_api_key)
                        prompt = f"""
                        ACT AS A PROFESSIONAL NARRATIVE DESIGNER AND MATCHMAKER.
                        - DM Playstyle Score: {dm_style}/100
                        - DM Campaign Pitch: "{dm_pitch}"
                        - Player Playstyle Score: {player_style}/100
                        - Player Bio: "{player_bio}"
                        TASK: Give this match a Compatibility Score out of 100%. Then, write a short, exciting 2-sentence campaign intro that blends the DM's pitch with what the Player wants.
                        """
                        chat_completion = client.chat.completions.create(
                            messages=[{"role": "user", "content": prompt}],
                            model="llama-3.1-8b-instant", 
                        )
                        st.success("🎯 **AI Matchmaker Output:**")
                        st.write(chat_completion.choices[0].message.content)
                    except Exception as e:
                        st.error(f"Error connecting to Groq: {e}")

# --- PILLAR 2: ENCOUNTER ARCHITECT ---
elif page == "⚔️ Encounter Architect":
    st.title("⚔️ Encounter Architect")
    st.write("Math-free combat balancing and homebrew creation tools.")
    
    tab1, tab2 = st.tabs(["🐉 Official 5.5e Monsters", "🛠️ Homebrew CR Calculator"])
    
    with tab1:
        st.subheader("Filter the 5.5e Monster Database")
        if monster_df is not None:
            min_cr, max_cr = st.slider("Select Challenge Rating (CR) Range", 0, 30, (1, 5))
            filtered_df = monster_df[(monster_df['CR'] >= min_cr) & (monster_df['CR'] <= max_cr)]
            
            st.write(f"Found **{len(filtered_df)}** monsters in that CR range.")
            
            st.markdown("##### 📊 CR vs. Hit Points Analysis")
            st.scatter_chart(filtered_df, x='CR', y='HP', color='#ff4b4b')
            
            # FIXED: use_container_width is now width="stretch"
            st.dataframe(filtered_df[['Name', 'Sourcebook', 'CR', 'HP', 'AC', 'DPR']], width="stretch")
        else:
            st.error("⚠️ `monsters.csv` not found! Please make sure it is saved in the same folder as `app.py`.")

    with tab2:
        st.subheader("Homebrew Monster CR Estimator")
        st.write("Input your custom monster's stats to calculate its approximate Challenge Rating.")
        
        col_hp, col_ac, col_dmg = st.columns(3)
        with col_hp:
            homebrew_hp = st.number_input("Hit Points (HP)", min_value=1, value=50)
        with col_ac:
            homebrew_ac = st.number_input("Armor Class (AC)", min_value=1,