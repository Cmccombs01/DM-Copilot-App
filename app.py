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
                        prompt = f"ACT AS A MATCHMAKER. DM Pitch: '{dm_pitch}'. Player Bio