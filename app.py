# app.py
import os
import re
import difflib
import streamlit as st
from dotenv import load_dotenv, find_dotenv

# ----------------------------------------------------------------------
# 1. ENV / API KEY
# ----------------------------------------------------------------------
load_dotenv()  # local .env (ignored in git)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    st.error(
        "GROQ_API_KEY not found!  \n"
        "Add it to **Streamlit → Settings → Secrets** (cloud)  \n"
        "or create a `.env` file locally."
    )
    st.stop()
else:
    st.success(f"GROQ_API_KEY loaded ({GROQ_API_KEY[:7]}…)")

# ----------------------------------------------------------------------
# 2. IMPORTS (after key check – avoids loading heavy libs if we stop)
# ----------------------------------------------------------------------
try:
    from fuzzywuzzy import fuzz
    FUZZY_AVAILABLE = True
except ImportError:                     # type: ignore
    FUZZY_AVAILABLE = False

from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_groq import ChatGroq
from langchain.prompts import ChatPromptTemplate
from langchain.schema.runnable import RunnablePassthrough
from langchain.schema.output_parser import StrOutputParser

# ----------------------------------------------------------------------
# 3. CONFIG
# ----------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHROMA_DIR = os.path.join(BASE_DIR, "chroma_db")

embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

vectorstore = Chroma(
    persist_directory=CHROMA_DIR,
    embedding_function=embeddings,
)

llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    api_key=GROQ_API_KEY,
)

# ----------------------------------------------------------------------
# 4. PROMPT TEMPLATE
# ----------------------------------------------------------------------
template = """
You are the **Developer Inspiration Assistant**.  
Use **only** the context below (ReadyTensor publications) to answer the question.

- List **up to 5** projects that match the requested award.  
- Include **title**, **ID**, and **awards** from metadata.  
- A project matches if the award appears in the metadata *awards* field **or** in the chunk text (case-insensitive, minor spelling variations allowed).  
- If fewer than 5 matches exist, list all.  
- If **no** matches or the context is irrelevant, reply:  
  `"I don’t have enough information from ReadyTensor publications to list projects for this award."`

Context:
{context}

Question: {question}

Answer clearly, citing the source (title + ID).
"""
prompt = ChatPromptTemplate.from_template(template)

# ----------------------------------------------------------------------
# 5. CORE ASK FUNCTION (unchanged logic, just wrapped in spinner later)
# ----------------------------------------------------------------------
def ask_assistant(query: str, award: str | None = None, top_k: int = 500):
    try:
        # ------------------------------------------------------------------
        # 5.1 Retrieval + optional award filter
        # ------------------------------------------------------------------
        award_norm = award.strip().lower() if award else None

        if award_norm:
            # Text-search first, then fuzzy-filter
            retriever = vectorstore.as_retriever(search_kwargs={"k": top_k})
            docs = retriever.invoke(award_norm)

            filtered = []
            for doc in docs:
                awards_str = doc.metadata.get("awards", "none").lower()
                content = doc.page_content.lower()

                # exact match
                if award_norm in awards_str or award_norm in content:
                    filtered.append(doc)
                    continue

                # fuzzy match
                if FUZZY_AVAILABLE:
                    if any(fuzz.ratio(award_norm, a.lower()) > 70 for a in awards_str.split(" | ")):
                        filtered.append(doc)
                        continue
                else:
                    if any(difflib.SequenceMatcher(None, award_norm, a.lower()).ratio() > 0.7
                           for a in awards_str.split(" | ")):
                        filtered.append(doc)
                        continue

            # Deduplicate by ID & keep ≤5
            seen = set()
            unique = []
            for d in filtered:
                pid = d.metadata["id"]
                if pid not in seen:
                    unique.append(d)
                    seen.add(pid)
            docs = unique[:5]
        else:
            retriever = vectorstore.as_retriever(search_kwargs={"k": top_k})
            docs = retriever.invoke(query)

            seen = set()
            unique = []
            for d in docs:
                pid = d.metadata["id"]
                if pid not in seen:
                    unique.append(d)
                    seen.add(pid)
            docs = unique[:5]

        # ------------------------------------------------------------------
        # 5.2 Build context string
        # ------------------------------------------------------------------
        context_lines = [
            f"Title: {d.metadata['title']}\n"
            f"ID: {d.metadata['id']}\n"
            f"Awards: {d.metadata['awards']}\n"
            f"Content: {d.page_content}"
            for d in docs
        ]
        context = "\n\n".join(context_lines)

        # ------------------------------------------------------------------
        # 5.3 RAG chain
        # ------------------------------------------------------------------
        rag_chain = (
            {"context": lambda _: context, "question": RunnablePassthrough()}
            | prompt
            | llm
            | StrOutputParser()
        )

        # ------------------------------------------------------------------
        # 5.4 Debug output (optional – hide in prod if you want)
        # ------------------------------------------------------------------
        st.write("**Debug – retrieved IDs:**", [d.metadata["id"] for d in docs])
        st.write(f"**Filtered to {len(docs)}** unique projects (award: `{award_norm or 'none'}`)")

        return rag_chain.invoke(query)

    except Exception as e:
        return f"Error while generating response: {e}"

# ----------------------------------------------------------------------
# 6. UI
# ----------------------------------------------------------------------
st.set_page_config(page_title="Developer Inspiration Assistant", page_icon="Light Bulb", layout="wide")
st.title("Light Bulb Developer Inspiration Assistant")
st.markdown("Ask about ReadyTensor publications or list projects with a specific **award** (e.g. *tag \"Best Overall Project\"*).")

# Chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

for role, txt in st.session_state.messages:
    if role == "user":
        st.markdown(f"**You:** {txt}")
    else:
        st.markdown(f"**Assistant:** {txt}")

# ----------------------------------------------------------------------
# 7. INPUT FORM
# ----------------------------------------------------------------------
st.markdown("---")
with st.form("chat_form", clear_on_submit=True):
    user_input = st.text_input(
        "Your question / command:",
        placeholder='e.g. tag "Best Overall Project" List 5 projects from this category'
    )
    submitted = st.form_submit_button("Send")

if submitted and user_input:
    # ------------------------------------------------------------------
    # 7.1 Extract award (your original regex + a few shortcuts)
    # ------------------------------------------------------------------
    award = None
    lower = user_input.lower()

    # regex: tag 'something'
    m = re.search(r"tag\s*['\"]([^'\"]+)['\"]", user_input, re.IGNORECASE)
    if m:
        award = m.group(1)

    # shortcuts
    elif "most innovative" in lower:
        award = "most innovative project"
    elif "best overall" in lower:
        award = "best overall project"

    st.caption(f"**Parsed award:** `{award or 'none'}`")

    # ------------------------------------------------------------------
    # 7.2 CALL ASSISTANT – WITH NICE SPINNER
    # ------------------------------------------------------------------
    with st.spinner("**Generating inspiration…** Light Bulb"):
        response = ask_assistant(user_input, award=award)

    # ------------------------------------------------------------------
    # 7.3 Store & refresh
    # ------------------------------------------------------------------
    st.session_state.messages.append(("user", user_input))
    st.session_state.messages.append(("assistant", response))
    st.rerun()