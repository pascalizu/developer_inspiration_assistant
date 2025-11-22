# app.py — now super clean and config-driven
import streamlit as st
import re
from config import settings, config
from assistant import ask

# --------------------------------------------------------------
# Page & Style
# --------------------------------------------------------------
st.set_page_config(page_title="Developer Inspiration Assistant", page_icon="Light Bulb", layout="wide")
st.title("Light Bulb Developer Inspiration Assistant")
st.markdown("Ask about ReadyTensor projects • Use `tag \"Best RAG Implementation\"` to filter by award")

# --------------------------------------------------------------
# LLM Key (via config.py)
# --------------------------------------------------------------
llm = st.secrets.get("GROQ_API_KEY", settings.groq_api_key)
if not llm:
    st.error("GROQ_API_KEY missing!")
    st.stop()

# --------------------------------------------------------------
# Session State
# --------------------------------------------------------------
if "messages" not in st with st.session_state:
    st.session_state.messages = []

for role, msg in st.session_state.messages:
    st.chat_message(role).write(msg)

# --------------------------------------------------------------
# Input
# --------------------------------------------------------------
if prompt := st.chat_input("e.g., tag \"Most Innovative Project\" or just ask anything..."):
    # Parse award
    award_match = re.search(r'tag\s*["\']([^"\']+)["\']', prompt, re.IGNORECASE)
    award = award_match.group(1).strip() if award_match else None
    
    st.chat_message("user").write(prompt)
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            response, docs = ask(prompt, award)
        
        st.write(response)
        
        # Debug sidebar
        with st.sidebar.expander("Debug • Retrieved Docs"):
            st.write(f"**Award filter:** `{award or 'none'}`")
            st.write(f"**Retrieved:** {len(docs)} projects")
            for d in docs:
                st.caption(f"**{d.metadata['title']}** (ID: {d.metadata['id']})")
                st.text(d.page_content[:200] + "...")

    st.session_state.messages.extend([("user", prompt), ("assistant", response)])