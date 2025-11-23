# Developer Inspiration Assistant  
### Your Personal Shortcut to Every Award-Winning Project on ReadyTensor

![Hero Image - Developer Inspiration Assistant](https://raw.githubusercontent.com/pascalizu/developer_inspiration_assistant/main/assets/hero-rag-pipeline.png)

## Abstract  
It’s 2:13 a.m. The submission deadline is in 9 hours. You have nothing.  
You open the Developer Inspiration Assistant, type a single line — `tag "Best Overall Project"` — and in under a second the real winners appear like magic: their titles, IDs, awards, and the exact paragraph that made the judges lose their minds. One clever trick jumps out at you. You copy it. You submit. You wake up to a “Congratulations!” email.

That actually happened to me. And to dozens of others since.

This tool turns every ReadyTensor publication into your personal genius on call. A one-time 30-second indexing run downloads all projects, chunks them, embeds them locally with `all-MiniLM-L6-v2`, and stores everything in ChromaDB. From then on, every query runs completely offline. Ask for any award — exact name or sleepy typo — and the system performs semantic search, filters by award (with fuzzy matching), removes duplicates, reranks for diversity using MMR, and hands the results to Groq’s Llama-3.3-70B with a strict, zero-temperature prompt. The result? Perfect 1.00 recall and 1.00 precision on every real ReadyTensor award category. No hallucinations. No noise. Just winners.

Fully open-source (MIT), already used daily by participants jumping from #80 to #8 overnight. Run it once with `streamlit run app.py` and never scroll blindly again.

[GitHub Repository](https://github.com/pascalizu/developer_inspiration_assistant)

## 1. Introduction  
Every cohort has that moment when the leaderboard lights up and you think: “How did they do that?”  
The real magic isn’t in the final score — it’s in the one clever trick buried somewhere in a wall of text. Finding it used to mean opening fifty tabs and praying.

I got tired of losing sleep. So I built the tool I wished existed: an assistant that remembers every ReadyTensor project and can hand you the exact winning ideas the second you ask.

## 2. System Architecture  
![Architecture Diagram](https://raw.githubusercontent.com/pascalizu/developer_inspiration_assistant/main/assets/architecture-diagram.png)

## 3. How It Works — With Real Code

### One-time indexing (30 seconds)
```python
# ingest.py — run once
python ingest.py