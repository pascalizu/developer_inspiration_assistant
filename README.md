# Developer Inspiration Assistant

**Find award-winning ReadyTensor projects — and *turn them into your next breakthrough*.**

![Streamlit Demo](docs/assets/screenshot.png)  
*(Screenshot of `app.py` – replace after first run)*

---

## What It Does

| Feature | Why It Matters |
|--------|----------------|
| **Search by award** (`tag "Best Overall Project"`) | Instantly surface the *best* work on ReadyTensor |
| **Rich context** – title, ID, awards, full description | No more hunting through pages |
| **Inspiration-first** – shows *why* a project won | Learn architecture, techniques, presentation |
| **Streamlit UI + CLI** | Use in browser or terminal |

> **Dataset** = **All ReadyTensor publications** (scraped & indexed nightly)

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/pasca/developer_inspiration_assistant.git
cd developer_inspiration_assistant

# 2. Install
"C:\Program Files\Python310\python.exe" -m pip install -r requirements.txt

# 3. Add Groq API key
echo GROQ_API_KEY=your_key_here > .env

# 4. Run!
# • Web UI
"C:\Program Files\Python310\python.exe" -m streamlit run app.py

# • CLI
"C:\Program Files\Python310\python.exe" assistant.py
## License

This project is licensed under the **MIT License** – see the [LICENSE](LICENSE) file for details.