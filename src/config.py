"""
config.py
---------
All settings in one place. Edit here — no other file needs touching.
"""

from pathlib import Path

# Paths
BASE_DIR          = Path(__file__).resolve().parent.parent
DATA_DIR          = BASE_DIR / "data"
REPORTS_DIR       = DATA_DIR / "reports"
IMAGES_DIR        = DATA_DIR / "images"
VECTOR_STORE_DIR  = BASE_DIR / "vector_store"
OUTPUTS_DIR       = BASE_DIR / "outputs"
DOCS_OUTPUT_DIR   = OUTPUTS_DIR / "docs"
PDF_OUTPUT_DIR    = OUTPUTS_DIR / "pdf"
VECTOR_STORE_PATH = VECTOR_STORE_DIR / "knowledge.pkl"

# Ollama models
VISION_MODEL = "llava"
TEXT_MODEL   = "llama3.2"  # Use llama3.2 (already installed) or try: ollama pull llama3.1

# Embedding model
EMBED_MODEL = "all-MiniLM-L6-v2"

# RAG settings
TOP_K_CAPTIONS = 5
TOP_K_SECTIONS = 3

# Image settings
SUPPORTED_IMAGE_FORMATS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
MAX_IMAGE_SIZE_MB       = 20

# Report sections order (matches Alumni Connect structure)
REPORT_SECTIONS = [
    "introduction",
    "about_the_speaker",
    "about_the_event",
    "description",
    "conclusion",
    "sdg_impact",
    "ieee_goals",
    "acknowledgement",
]

# Sections that are skipped if the user provides no text
OPTIONAL_SECTIONS = {
    "about_the_speaker",
    "sdg_impact",
    "ieee_goals",
    "acknowledgement",
}

# Caption guidelines
CAPTION_GUIDELINES = """
STRICT CAPTION GUIDELINES:

LANGUAGE:   UK English (organised, colour, centre, recognise).
TONE:       Strictly formal and viewer-based. Written from the perspective of
            a viewer observing the scene. Institutional and composed.
            The viewer only observes and reports.
TENSE:      Present continuous preferred (e.g. "Participants demonstrating").
            Avoid passive voice.
STYLE:      8-15 words. No slang, emojis, pronouns (we/you/I/our), or
            promotional language.
FOCUS:      Describe only what is directly visible. Name the activity type
            if discernible (workshop, panel discussion, award ceremony,
            hands-on session, technical presentation).
AVOID:
- "We are proud to..."
- "An amazing event..."
- Passive constructions
- Emojis or hashtags
- Any emotional language
"""

# Report writing guidelines
REPORT_GUIDELINES = """
STRICT REPORT WRITING GUIDELINES:

LANGUAGE:
- UK English spelling (organised, colour, centre, recognise, programme).
- Grammatical accuracy and formal vocabulary throughout.

TONE:
- Formal, institutional, and academic.
- Professional — suitable for official IEEE documentation.
- Slightly energetic ONLY for competitive events (gaming, hackathon, robotics).
- Preserve the tone supplied by the user in their input text.

TENSE:
- Past tense throughout the entire report.

PERSON:
- Third person only. Do NOT use "we", "I", "you", "our", or "us".

STRUCTURE:
  1. Title
  2. Introduction
  3. About the Speaker       (only if a speaker is mentioned)
  4. About the Event         (date, time, venue, participants)
  5. Description             (chronological flow)
  6. Results / Outcomes      (only if results are mentioned)
  7. Conclusion
  8. Acknowledgement

WRITING RULES:
- Smooth, logical transitions between paragraphs.
- Avoid repetition, redundancy, and abruptness.
- Use ONLY the facts provided — do not invent any detail.
- Simple yet creative language — formal does not mean dull.
- No grammatical errors or spelling mistakes.
- Every section must close with a concluding sentence.

AVOID:
- First-person pronouns (we, I, our, us, you)
- Invented facts
- Bullet points in body text
- Slang or informal vocabulary
- Exaggerated language (incredible, groundbreaking)
- Abrupt endings
"""
