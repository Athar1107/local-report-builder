"""
indexer.py
----------
Extracts two types of content from previous-year reports:

  1. IMAGE CAPTIONS  — figure labels, photo descriptions, caption text.
                       Used by the Caption Generator via RAG retrieval.

  2. REPORT SECTIONS — intro, objectives, activities, outcomes, conclusion, etc.
                       Used by the Report Generator to match format & style.

NOTE: This module uses ZERO Ollama/LLM calls.
      Pure regex + rule-based parsing — fast, reliable, no crashes.
      Ollama is only used at generation time (caption_generator, report_generator).
"""

import re
from pathlib import Path

import fitz           # PyMuPDF
from docx import Document

from .config import TEXT_MODEL


# ── Document readers ───────────────────────────────────────────────────────────

def read_pdf(path: str) -> str:
    doc   = fitz.open(path)
    pages = [page.get_text() for page in doc]
    doc.close()
    return "\n".join(pages)


def read_docx(path: str) -> str:
    doc = Document(path)
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def read_document(file_path: str) -> str:
    """Read text from a PDF or DOCX file."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    ext = path.suffix.lower()
    if ext == ".pdf":
        return read_pdf(file_path)
    elif ext == ".docx":
        return read_docx(file_path)
    raise ValueError(f"Unsupported format '{ext}'. Use .pdf or .docx.")


# ── Caption extraction (pure regex, no LLM) ────────────────────────────────────

_CAPTION_PATTERNS = [
    r"(?:Fig(?:ure)?\.?\s*\d+\s*[:\-\.]\s*)(.{10,200})",
    r"(?:Photo\s*\d+\s*[:\-\.]\s*)(.{10,200})",
    r"(?:Image\s*\d+\s*[:\-\.]\s*)(.{10,200})",
    r"(?:Plate\s*\d+\s*[:\-\.]\s*)(.{10,200})",
    r"(?:Caption\s*[:\-]\s*)(.{10,200})",
    r"(?:Photograph\s*\d*\s*[:\-\.]\s*)(.{10,200})",
    r"(?:Pic(?:ture)?\s*\d*\s*[:\-\.]\s*)(.{10,200})",
]

_IMAGE_KEYWORDS = [
    "presenting", "receiving", "delivering", "addressing", "demonstrating",
    "posing", "standing", "seated", "gathered", "participants", "attendees",
    "audience", "ceremony", "award", "felicitation", "inauguration",
    "ribbon", "lighting", "lamp", "inaugurat", "chief guest", "speaker",
    "workshop", "session", "panel", "group photo", "team photo",
]

def _is_caption_like(line: str) -> bool:
    line_l = line.lower()
    if len(line) < 12 or len(line) > 220:
        return False
    if not any(kw in line_l for kw in _IMAGE_KEYWORDS):
        return False
    if line.isupper() and len(line) < 40:
        return False
    if re.match(r"^\d+\.\s+\w", line) and len(line) > 120:
        return False
    return True


def extract_captions(file_path: str, model: str = TEXT_MODEL) -> list:
    raw    = read_document(file_path)
    source = Path(file_path).name
    found  = []

    # Pass 1: explicit figure/photo/caption labels
    for pat in _CAPTION_PATTERNS:
        for m in re.finditer(pat, raw, re.IGNORECASE):
            full = m.group(0).strip()
            if full and len(full) > 10:
                found.append(full)

    # Pass 2: short lines that look like captions
    for line in raw.splitlines():
        line = line.strip()
        if _is_caption_like(line):
            found.append(line)

    # Deduplicate
    seen   = set()
    unique = []
    for c in found:
        key = re.sub(r"\s+", " ", c.lower().strip())
        if key not in seen and len(c.strip()) > 10:
            seen.add(key)
            unique.append(c)

    # Fallback: descriptive sentences as style samples
    if not unique:
        for sent in re.split(r"(?<=[.!?])\s+", raw):
            sent = sent.strip()
            if 20 < len(sent) < 180 and any(kw in sent.lower() for kw in _IMAGE_KEYWORDS):
                unique.append(sent)
            if len(unique) >= 20:
                break

    return [{"text": cap, "kind": "caption", "source": source} for cap in unique]


# ── Section extraction (pure text parsing, no LLM) ────────────────────────────

_SECTION_HEADINGS = [
    r"abstract", r"introduction", r"about\s+the\s+\w+", r"objectives?",
    r"event\s+overview", r"programme", r"program", r"schedule",
    r"activities", r"description", r"proceedings", r"highlights",
    r"results?(\s+and\s+outcomes?)?", r"outcomes?", r"impact",
    r"conclusion", r"recommendations?", r"acknowledgements?",
    r"vote\s+of\s+thanks", r"speakers?\s+profile", r"chief\s+guest",
    r"guest\s+of\s+honour", r"resource\s+persons?", r"background",
    r"methodology", r"key\s+takeaways?", r"feedback", r"photographs?",
    r"gallery", r"summary", r"overview",
]

_HEADING_RE = re.compile(
    r"^\s*(?:\d+[\.\)]\s*)?(" + "|".join(_SECTION_HEADINGS) + r")\s*[:\-]?\s*$",
    re.IGNORECASE | re.MULTILINE,
)

_ALLCAPS_HEADING_RE = re.compile(r"^[A-Z][A-Z\s\-&/]{3,50}$")

_SECTION_KEYWORDS = ["introduction", "conclusion", "overview", "outcome",
                     "description", "acknowledgement", "activities",
                     "objective", "summary", "background"]


def _looks_like_heading(line: str) -> bool:
    line = line.strip()
    if not line:
        return False
    if _HEADING_RE.match(line):
        return True
    if _ALLCAPS_HEADING_RE.match(line) and len(line) < 60:
        return True
    words = line.split()
    if 1 <= len(words) <= 8 and all(w[0].isupper() for w in words if w.isalpha()):
        if any(kw in line.lower() for kw in _SECTION_KEYWORDS):
            return True
    return False


def extract_sections(file_path: str, model: str = TEXT_MODEL) -> list:
    raw    = read_document(file_path)
    source = Path(file_path).name
    lines  = raw.splitlines()

    sections      = []
    current_head  = None
    current_lines = []

    def _flush():
        if current_head and current_lines:
            content = " ".join(current_lines).strip()
            content = re.sub(r"\s{2,}", " ", content)
            if len(content) > 40:
                sections.append({
                    "text":    f"{current_head}: {content}",
                    "heading": current_head,
                    "content": content,
                    "kind":    "section",
                    "source":  source,
                })

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if _looks_like_heading(stripped):
            _flush()
            current_head  = stripped.rstrip(":-").strip()
            current_lines = []
        elif current_head is not None:
            current_lines.append(stripped)

    _flush()

    # Fallback: paragraph chunks if heading detection found nothing
    if not sections:
        paragraphs = [p.strip() for p in re.split(r"\n{2,}", raw) if len(p.strip()) > 80]
        for i, para in enumerate(paragraphs[:20]):
            sections.append({
                "text":    para,
                "heading": f"Paragraph {i+1}",
                "content": para,
                "kind":    "section",
                "source":  source,
            })

    return sections


# ── Full pipeline ──────────────────────────────────────────────────────────────

def index_report(file_path: str, model: str = TEXT_MODEL) -> dict:
    """
    Full indexing pipeline — NO LLM calls, runs in seconds.
    Returns: { "captions": [...], "sections": [...], "source": filename }
    """
    captions = extract_captions(file_path, model)
    sections = extract_sections(file_path, model)
    return {
        "captions": captions,
        "sections": sections,
        "source":   Path(file_path).name,
    }
