import streamlit as st
import pandas as pd
import streamlit_analytics2 as streamlit_analytics
import random
from datetime import datetime
import os

# --- 🚑 TRAFFIC SURGE PATCH FOR ANALYTICS ---
import streamlit_analytics2.display as sa2_display
if not hasattr(sa2_display, "original_show_results"):
    sa2_display.original_show_results = sa2_display.show_results

def safe_show_results(data, reset_data, unsafe_password):
    safe_data = data.copy()
    safe_data["widgets"] = data.get("widgets", {}).copy()
    return sa2_display.original_show_results(safe_data, reset_data, unsafe_password)

sa2_display.show_results = safe_show_results
# --------------------------------------------

# --- 🐛 LOGGING & CONFIG ---
st.set_page_config(page_title="DM Co-Pilot | Masterwork Edition", page_icon="🐉", layout="wide")

# --- 🚦 ROUTING: DETECT ANALYTICS MODE ---
is_analytics = st.query_params.get("analytics") == "on"

if is_analytics:
    # --- 🟢 HIGH-CONTRAST ANALYST MODE (BRIGHT GREEN) ---
    st.markdown("""
        <style>
        [data-testid="stAppViewContainer"] {
            background-color: #0e1117 !important;
            background-image: none !important;
        }
        html, body, [class*="st-"], p, span, label, li, h1, h2, h3, div {
            color: #00FF00 !important; 
            font-family: monospace !important;
        }
        svg text {
            fill: #00FF00 !important;
        }
        
        .stButton>button { 
            background-color: #000000 !important; 
            color: #00FF00 !important; 
            font-family: monospace !important; 
            font-weight: bold !important;
            width: 100%; 
            border-radius: 5px;
            border: 2px solid #00FF00 !important;
            font-size: 1.1rem !important;
            transition: 0.3s;
        }
        .stButton>button:hover {
            background-color: #00FF00 !important; 
            color: #000000 !important; 
        }
        </style>
        """, unsafe_allow_html=True)

else:
    # --- 🌌 MASTERWORK HACKER THEME (BLACK & NEON GREEN) ---
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=MedievalSharp&display=swap');

        /* 1. Main Background */
        [data-testid="stAppViewContainer"] {
            background-color: #000000 !important;
            background-image: none !important;
        }

        /* 2. Global Text & Headers */
        [data-testid="stAppViewContainer"] p, 
        [data-testid="stAppViewContainer"] span, 
        [data-testid="stAppViewContainer"] label, 
        [data-testid="stAppViewContainer"] li {
            color: #00FF00 !important;
            font-family: 'monospace', sans-serif !important;
        }

        [data-testid="stAppViewContainer"] h1, 
        [data-testid="stAppViewContainer"] h2, 
        [data-testid="stAppViewContainer"] h3 {
            font-family: 'MedievalSharp', cursive;
            color: #00FF00 !important;
            text-shadow: 0 0 10px #00FF00;
        }

        /* 3. Sidebar Navigation */
        [data-testid="stSidebar"] {
            background-color: #000000 !important;
            border-right: 2px solid #00FF00 !important;
        }
        
        [data-testid="stSidebar"] p, [data-testid="stSidebar"] span {
            color: #00FF00 !important;
            font-family: monospace !important;
        }

        /* 4. Radio Buttons */
        [data-testid="stSidebar"] div[data-baseweb="radio"] > div:first-child {
            background-color: #000000 !important;
            border: 2px solid #00FF00 !important;
        }
        [data-testid="stSidebar"] div[data-baseweb="radio"] div[role="radio"][aria-checked="true"] > div:first-child {
            background-color: #00FF00 !important;
        }

        /* 5. Output Cards & Result Boxes */
        .stat-card {
            background-color: #0a0a0a !important;
            border: 1px solid #00FF00 !important;
            padding: 25px;
            border-radius: 8px;
            border-left: 10px solid #00FF00 !important;
            color: #00FF00 !important;
            font-family: monospace !important;
            box-shadow: 0 0 15px rgba(0, 255, 0, 0.1);
            margin-bottom: 20px;
        }

        /* 6. Inputs & Text Areas */
        input, select, textarea, div[data-baseweb="select"] > div {
            background-color: #000000 !important;
            color: #00FF00 !important;
            border: 1px solid #00FF00 !important;
        }

        /* 7. Action Buttons */
        .stButton>button {
            background-color: #000000 !important;
            color: #00FF00 !important;
            font-family: monospace !important;
            border: 2px solid #00FF00 !important;
            width: 100%;
            transition: 0.3s;
        }
        .stButton>button:hover {
            background-color: #00FF00 !important;
            color: #000000 !important;
            border: 2px solid #000000 !important;
        }
        </style>
    """, unsafe_allow_html=True)
# --- ⚖️ RECHARGE TIER LOGIC ---
def get_item_balance_rules(rarity):
    rules = {
        "Common": "1d4 charges, regains 1d4 at dawn.",
