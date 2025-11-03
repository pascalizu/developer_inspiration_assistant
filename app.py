# app.py
import streamlit as st
import os
import re
import difflib
from dotenv import load_dotenv, find_dotenv

# --------------------------------------------------------------
# 1. PAGE CONFIG + CODE-RAIN SPINNER CSS
# --------------------------------------------------------------
st.set_page_config(page_title="Developer Inspiration Assistant", page_icon="Light Bulb", layout="wide")

st.markdown("""
<style>
.stSpinner > div > div {
    background: linear-gradient(90deg, #6366f1, #8b5cf6);
    animation: code-rain 2s infinite linear;
    height: 6px !important;
    border-radius: 3px;
}
@keyframes code-rain { 0% { transform: translateX(-100%); } 100% { transform: translateX(100%); } }
</style>
""", unsafe_allow_html=True)

# --------------------------------------------------------------
# 2. ENV + API KEY (global, tested early)
# --------------------------------------------------------------
dotenv_path = find_dotenv()
if dotenv_path:
    load_dotenv(dotenv_path, override=True)
    st.sidebar.success(f"Loaded .env from {dotenv_path}")
else:
    st.sidebar.warning("No .env – using Streamlit Secrets.")

api_key = os.getenv("GROQ_API_KEY")
if not api_key:
    st.error(
        "**GROQ_API_KEY missing!**\n\n"
        "- **Local**: create `.env` with `GROQ_API_KEY=gsk_…`\n"
        "- **Cloud**: add to **Settings → Secrets**"
    )
    st.stop()

# --------------------------------------------------------------
# 3. HEAVY IMPORTS (after key is confirmed)
# --------------------------------------------------------------
try:
    from langchain_groq import ChatGroq
    from langchain_chroma import Chroma
    from langchain_huggingface import HuggingFaceEmbeddings
    from langchain.prompts import ChatPromptTemplate
    from langchain.schema.output_parser import StrOutputParser
    from fuzzywuzzy import fuzz
    FUZZY_AVAILABLE = True
except ImportError as e:
    st.error(f"Import failed: {e}\n\nRun `poetry install` again.")
    st.stop()

# --------------------------------------------------------------
# 4. CHROMA DB
# --------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHROMA_DIR = os.path.join(BASE_DIR, "chroma_db")

if not os.path.exists(CHROMA_DIR):
    st.error(f"Chroma DB not found at `{CHROMA_DIR}`\n\nRun your ingestion script first.")
    st.stop()

embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
vectorstore = Chroma(persist_directory=CHROMA_DIR, embedding_function=embeddings)

# --------------------------------------------------------------
# 5. DETERMINISTIC LLM (no Pydantic warnings)
# --------------------------------------------------------------
llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    groq_api_key=api_key,
    temperature=0,                     # deterministic
    max_tokens=500,
    model_kwargs={                     # <-- top_p & seed go here
        "top_p": 1,
        "seed": 42
    }
)
st.sidebar.success("LLM ready (deterministic)")

# --------------------------------------------------------------
# 6. PROMPT TEMPLATE
# --------------------------------------------------------------
template = """
You are the Developer Inspiration Assistant. 
Use ONLY the following context from ReadyTensor publications to answer the user’s question.
List up to 5 projects that match the requested award, including their titles, IDs, and awards from metadata.
A project matches if the award appears in the metadata awards or the chunk content (case-insensitive, allowing minor variations).
If fewer than 5 projects match, list all available matches.
If no projects match or the context is irrelevant, say "I don’t have enough information from ReadyTensor publications to list projects for this award."

Context:
{context}

Question: {question}

Answer as clearly and helpfully as possible, citing the source publication (title and ID).
"""
prompt = ChatPromptTemplate.from_template(template)

# --------------------------------------------------------------
# 7. ASK FUNCTION (core logic + debug)
# --------------------------------------------------------------
def ask_assistant(query: str, award: str | None = None, top_k: int = 500):
    try:
        award_norm = award.strip().lower() if award else None
        retriever = vectorstore.as_retriever(search_kwargs={"k": top_k})

        if award_norm:
            docs = retriever.invoke(award_norm)

            # fuzzy post-filter
            filtered = []
            for doc in docs:
                a_str = doc.metadata.get("awards", "none").lower()
                content = doc.page_content.lower()
                if award_norm in a_str or award_norm in content:
                    filtered.append(doc)
                    continue
                if FUZZY_AVAILABLE and any(fuzz.ratio(award_norm, a.lower()) > 70 for a in a_str.split(" | ")):
                    filtered.append(doc)
                    continue
                if any(difflib.SequenceMatcher(None, award_norm, a.lower()).ratio() > 0.7 for a in a_str.split(" | ")):
                    filtered.append(doc)

            # dedup & limit
            seen = set()
            docs = [d for d in filtered if d.metadata["id"] not in seen and not seen.add(d.metadata["id"])][:5]
        else:
            docs = retriever.invoke(query)
            seen = set()
            docs = [d for d in docs if d.metadata["id"] not in seen and not seen.add(d.metadata["id"])][:5]

        context = "\n".join([
            f"Title: {d.metadata['title']}\n"
            f"ID: {d.metadata['id']}\n"
            f"Awards: {d.metadata['awards']}\n"
            f"Content: {d.page_content}"
            for d in docs
        ])

        # simple chain (no RunnablePassthrough needed)
        chain = (
            {"context": lambda _: context, "question": lambda _: query}
            | prompt
            | llm
            | StrOutputParser()
        )

        # debug sidebar
        with st.sidebar.expander("Debug Logs"):
            st.write("**IDs:**", [d.metadata["id"] for d in docs])
            st.write(f"**Filtered:** {len(docs)} (award: `{award_norm or 'none'}`)")
            for i, d in enumerate(docs[:3]):
                st.write(f"Doc {i+1}: {d.page_content[:100]}...")

        return chain.invoke({})

    except Exception as e:
        return f"Error: {e}"

# --------------------------------------------------------------
# 8. UI + CACHING + REGENERATE
# --------------------------------------------------------------
st.title("Light Bulb Developer Inspiration Assistant")
st.markdown("Ask about ReadyTensor projects or list by award (e.g., *tag \"Best Overall Project\"*).")

# session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "cache" not in st.session_state:
    st.session_state.cache = {}

# chat history
for role, txt in st.session_state.messages:
    st.markdown(f"**{role.capitalize()}:** {txt}")

# regenerate button
if st.session_state.messages and st.button("Regenerate Last Response"):
    if len(st.session_state.messages) >= 2:
        last_q = st.session_state.messages[-2][1]
        award = re.search(r"tag\s*['\"]([^'\"]+)['\"]", last_q, re.IGNORECASE)
        award = award.group(1).lower() if award else None
        with st.spinner("Regenerating..."):
            new_resp = ask_assistant(last_q, award)
            st.session_state.messages[-1] = ("assistant", new_resp)
            key = f"{last_q}_{award}"
            st.session_state.cache.pop(key, None)
        st.rerun()

# input form
st.markdown("---")
with st.form("chat_form", clear_on_submit=True):
    user_input = st.text_input(
        "Your query:",
        placeholder='tag "Best Overall Project" List 5 projects'
    )
    submitted = st.form_submit_button("Send")

if submitted and user_input:
    # parse award
    award = None
    lower = user_input.lower()
    if "tag" in lower:
        m = re.search(r"tag\s*['\"]([^'\"]+)['\"]", user_input, re.IGNORECASE)
        if m:
            award = m.group(1).lower()
    elif "most innovative" in lower:
        award = "most innovative project"
    elif "best overall" in lower:
        award = "best overall project"

    st.caption(f"**Parsed award:** `{award or 'none'}`")

    cache_key = f"{user_input}_{award}"
    if cache_key in st.session_state.cache:
        response = st.session_state.cache[cache_key]
        st.info("Using cached response")
    else:
        with st.spinner("**Generating inspiration...** Light Bulb"):
            response = ask_assistant(user_input, award)
        st.session_state.cache[cache_key] = response

    st.session_state.messages.append(("user", user_input))
    st.session_state.messages.append(("assistant", response))
    st.rerun()