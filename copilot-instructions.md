# 🐉 DM Co-Pilot | Community Edition AI Instructions

Hello, AI Assistant. You are working on the 'Community Edition' of DM Co-Pilot.
Goal: Maintain a stable, modular, and open-source TTRPG toolkit for the D&D 5e community.

## 🚨 THE PUBLIC SAFETY PROTOCOL (Community Standard)

1.  **Bring Your Own Key (BYOK):** Always maintain the logic that allows users to input their own Groq and OpenAI keys via the sidebar. 
2.  **Standard Infrastructure:** Assume the user is running this on a standard hobbyist tier (Local machine or basic cloud). Do NOT implement Blaze-tier-specific logic here.
3.  **Surgical Strikes:** Keep code updates clean and under 50 lines per injection.
4.  **The Privacy Wall:** NEVER mention private production IDs, internal billing account details, or proprietary 'Oracle' server URLs in this repository.
5.  **Indentation Shield:** Follow strict 4-space indentation to prevent "Goblin" crashes in Streamlit.

## 🎯 CURRENT OBJECTIVE: COMMUNITY STABILITY (v8.6)
- *Status:* ✅ v8.6 STABLE.
- *Core Focus:* Ensure the VTT Bridge remains compatible with the most common Foundry VTT and Roll20 modules.
- *Performance:* Aim for high reliability on standard hardware. 

## 🏗️ THE COMMUNITY ROADMAP
1. **BYOK Protocol** (DONE): Secure key handling via Streamlit secrets and sidebar inputs.
2. **Monster Lab** (DONE): Markdown-based creature drafting for easy community editing.
3. **VTT Translation** (DONE): Standard JSON schema exports for VTT interoperability.
4. **Universal Systems** (PLANNED): Expanding support for systems beyond D&D 5e.

## 🧪 DEVELOPER LOGS
* **v8.6:** Implemented standard session handling and the 'Firebird UX' split-pane editor.
* **v8.0:** Initial open-source refactor for community accessibility.
