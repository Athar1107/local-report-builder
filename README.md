# IEEE Report Generator + Caption Generator

Fully local. No API key. No internet after setup.
Uses **Ollama** (LLaVA + llama3) + **sentence-transformers** + **FAISS**.

---

## What It Does

Two pipelines share one RAG knowledge base built from previous-year reports:

```
Previous Year Report (PDF / DOCX)
           │
           ├─── Captions  ──► KnowledgeStore (kind="caption")
           │                         │
           └─── Sections  ──► KnowledgeStore (kind="section")
                                     │
              ┌──────────────────────┴─────────────────────┐
              │                                            │
    ★ CAPTION GENERATOR                        ★ REPORT GENERATOR
              │                                            │
    New image + your text              Your text descriptions per section
              │                                            │
    RAG retrieves top-5                RAG retrieves matching
    similar past captions              past sections for style
              │                                            │
    LLaVA generates                    llama3 generates each
    3 IEEE caption variations          section in previous style
              │                                            │
    outputs/<image>_captions.txt       outputs/<event>_<date>.docx
```

---

## Project Structure

```
ieee_report_gen/
│
├── main.py                    ← CLI entry point
├── requirements.txt
├── README.md
│
├── src/
│   ├── __init__.py
│   ├── config.py              ← All settings, IEEE guidelines
│   ├── indexer.py             ← Extracts captions + sections from reports
│   ├── embedder.py            ← sentence-transformers (local)
│   ├── vector_store.py        ← Unified FAISS store (captions + sections)
│   ├── image_handler.py       ← Image validation + base64 encoding
│   ├── caption_generator.py   ← RAG + LLaVA → 3 IEEE captions
│   ├── report_generator.py    ← RAG + llama3 → report sections
│   └── report_builder.py      ← Assembles sections into formatted DOCX
│
├── data/
│   ├── reports/               ← Drop previous-year PDFs / DOCX here
│   └── images/                ← Drop new event images here
│
├── vector_store/
│   └── knowledge.pkl          ← Auto-created after indexing
│
└── outputs/                   ← Generated .txt captions + .docx reports
```

---

## Setup

```bash
# 1. Install Ollama and pull models
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llava
ollama pull llama3
ollama serve              # keep this running

# 2. Python environment
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Frontend setup (Node.js required)
cd frontend
npm install
cd ..
```

---

## Running the Web UI (Frontend + Backend)

To use the graphical interface, you need to start both the backend server and the frontend application.

**1. Start the Flask Backend:**
Open a terminal in the project root:
```bash
source .venv/bin/activate   # On Windows: .venv\Scripts\activate
python app.py
```
*The backend API will run on http://127.0.0.1:5000*

**2. Start the React Frontend:**
Open a second terminal:
```bash
cd frontend
npm run dev
```
*Vite will start the frontend (typically on http://127.0.0.1:5173). Open the provided local URL in your browser.*

---

## CLI Usage

### Step 1 — Index a previous-year report *(once per report)*
```bash
python main.py index --report data/reports/annual_report_2023.pdf
```
Extracts captions and report sections, embeds them, saves to `vector_store/knowledge.pkl`.

---

### Step 2A — Generate captions for a new image
```bash
python main.py caption \
  --image data/images/award_night.jpg \
  --text  "Award ceremony at the IEEE student branch annual event"
```

**Output:** 3 IEEE-style caption variations printed + saved to `outputs/`.

Batch (entire folder):
```bash
python main.py caption-batch \
  --folder data/images/ \
  --text   "IEEE student branch technical workshop"
```

---

### Step 2B — Generate a full event report
```bash
python main.py report \
  --event      "IEEE Student Branch Induction 2024" \
  --intro      "The induction ceremony was held on 10th March 2024 at CHARUSAT University." \
  --objectives "To welcome new members and present the annual technical roadmap." \
  --activities "Three sessions: orientation talk, live demo, and technical quiz." \
  --outcomes   "82 new members inducted. Guest lecture delivered by Dr. R. Mehta." \
  --conclusion "The event met its objectives and set the tone for the academic year."
```

**Output:** Formatted `.docx` report saved to `outputs/`.

You can provide any combination of sections — omit sections you don't need.

---

### Utility
```bash
python main.py status   # show knowledge store contents
python main.py clear    # wipe the knowledge store
```

---

## Output Examples

**Caption output** (`outputs/award_night_captions.txt`):
```
Variation 1:
Participants receiving recognition at the IEEE student branch award ceremony.

Variation 2:
Delegates gathering during the annual award presentation at the branch event.

Variation 3:
Student members acknowledging achievement at the formal IEEE award ceremony.
```

**Report output** (`outputs/IEEE_Student_Branch_Induction_2024_20240310_1430.docx`):
A formatted Word document with sections matching the previous year's style.

---

## Configuration

All settings in `src/config.py`:

| Setting | Default | Purpose |
|---|---|---|
| `VISION_MODEL` | `llava` | Ollama model for caption generation |
| `TEXT_MODEL` | `llama3` | Ollama model for report generation |
| `EMBED_MODEL` | `all-MiniLM-L6-v2` | Embedding model |
| `TOP_K_CAPTIONS` | `5` | Past captions retrieved per image |
| `TOP_K_SECTIONS` | `3` | Past sections retrieved per report section |
