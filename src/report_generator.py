"""
report_generator.py
-------------------
Generates a full IEEE event report section-by-section using RAG.

For each section, the pipeline:
  1. Retrieves the most similar section from previous-year reports (RAG).
  2. Uses that section as a style/format reference.
  3. Prompts llama3 to write the new section matching the previous style exactly.

The user provides all factual content via text descriptions — the model
only handles style, structure, and professional language.
"""

import ollama

from .config       import TEXT_MODEL, REPORT_GUIDELINES, TOP_K_SECTIONS
from .vector_store import KnowledgeStore


# ── Section generation prompt ──────────────────────────────────────────────────

_SECTION_PROMPT = """{guidelines}

━━━ STYLE REFERENCE — same section from previous year's report ━━━
Study this section carefully. Match its heading style, sentence structure,
paragraph length, and level of detail EXACTLY:

Previous year's "{section_name}" section:
---
{reference_content}
---

━━━ YOUR TASK ━━━
Write the "{section_name}" section for this year's event report.

Facts and details provided by the organiser (use ONLY these — do not invent):
---
{user_facts}
---

Rules:
- Match the FORMAT, STYLE, and LENGTH of the previous year's section above.
- Past tense throughout. Third person only — no "we", "I", "our", or "you".
- UK English spelling. Formal, institutional tone.
- Use ONLY the facts supplied above — do not fabricate any detail.
- End with a smooth closing sentence — no abrupt endings.
- Return ONLY the section text (include the heading). No preamble or commentary.
"""


_FALLBACK_SECTION_PROMPT = """{guidelines}

Write the "{section_name}" section of a formal IEEE event report.

Facts and details provided by the organiser (use ONLY these — do not invent):
---
{user_facts}
---

Rules:
- Past tense throughout. Third person only — no "we", "I", "our", or "you".
- UK English spelling. Formal, institutional, academic tone.
- Use ONLY the facts supplied above.
- End with a smooth closing sentence.
- Return ONLY the section text with its heading. No preamble.
"""

# Optional sections — skipped entirely if the user provides no content
OPTIONAL_SECTIONS = {"sdg_impact", "ieee_goals", "acknowledgement"}
CORE_SECTIONS = {"introduction", "about_the_speaker", "about_the_event", "description", "conclusion"}

OPTIONAL_SECTION_KEYWORDS = {
    "about_the_speaker": (
        "speaker", "resource person", "guest", "expert", "trainer", "mentor",
        "professor", "prof.", "dr.", "mr.", "mrs.", "ms.",
    ),
    "sdg_impact": ("sdg", "sustainable development", "sustainability", "goal "),
    "ieee_goals": ("ieee goal", "ieee vision", "ieee mission", "technical awareness", "professional development"),
    "acknowledgement": ("acknowledge", "acknowledgement", "thanks", "gratitude", "sponsor", "faculty coordinator"),
}


# ── Helper ─────────────────────────────────────────────────────────────────────

def _ollama_text(prompt: str, model: str = TEXT_MODEL) -> str:
    try:
        resp = ollama.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp["message"]["content"].strip()
    except Exception as e:
        raise ConnectionError(f"Ollama not running. (ollama serve)\n{e}")


def _should_use_session_points(section_key: str, session_points: str) -> bool:
    if not session_points:
        return False
    if section_key in CORE_SECTIONS:
        return True
    text = session_points.lower()
    return any(keyword in text for keyword in OPTIONAL_SECTION_KEYWORDS.get(section_key, ()))


def _section_facts_from_session_points(section_name: str, session_points: str) -> str:
    return (
        f"Event notes supplied by the organiser:\n{session_points}\n\n"
        f"Use these notes to write only the '{section_name}' section. "
        "Select the relevant facts for this section, keep the chronology clear, "
        "and do not add names, dates, numbers, outcomes, SDGs, or acknowledgements "
        "that are not present in the notes."
    )


# ── Main functions ─────────────────────────────────────────────────────────────

def generate_section(
    section_name: str,
    user_facts:   str,
    store:        KnowledgeStore,
    model:        str = TEXT_MODEL,
) -> str:
    """
    Generate one report section using a RAG-retrieved style reference.

    Args:
        section_name : Display name of the section (e.g. "Introduction").
        user_facts   : User's text description of the content for this section.
        store        : Loaded KnowledgeStore.
        model        : Ollama text model.

    Returns:
        Generated section text (heading + body), past tense, third person.
    """
    query     = f"{section_name}: {user_facts}"
    retrieved = store.retrieve(query, top_k=TOP_K_SECTIONS, kind="section")

    if retrieved:
        ref  = retrieved[0]
        text = _ollama_text(_SECTION_PROMPT.format(
            guidelines        = REPORT_GUIDELINES,
            section_name      = section_name,
            reference_content = ref.get("content", ref["text"]),
            user_facts        = user_facts,
        ), model)
    else:
        text = _ollama_text(_FALLBACK_SECTION_PROMPT.format(
            guidelines   = REPORT_GUIDELINES,
            section_name = section_name,
            user_facts   = user_facts,
        ), model)

    return text


def generate_full_report(
    event_details: dict[str, str],
    store:         KnowledgeStore,
    model:         str = TEXT_MODEL,
) -> dict[str, str]:
    """
    Generate a complete report section by section.

    The section order follows the official report structure:
      Title → Introduction → About the Speaker (optional) →
      About the Event → Description → Results / Outcomes (optional) →
      Conclusion → Acknowledgement

    Optional sections (About the Speaker, Results / Outcomes) are skipped
    if the user provides no content for them.

    Args:
        event_details : Dict mapping section keys to user-provided fact text.
                        Keys should match REPORT_SECTIONS from config.
                        e.g. {
                          "title":               "IEEE Student Branch Induction 2024",
                          "introduction":        "The event was held on 10th March…",
                          "about_the_speaker":   "Dr. Mehta, Professor of ECE…",
                          "about_the_event":     "Date: 10 March 2024, Venue: …",
                          "description":         "The event commenced at 10:00 AM…",
                          "results_and_outcomes":"82 students were inducted…",     # optional
                          "conclusion":          "The event successfully met…",
                          "acknowledgement":     "The organisers thank Prof. Shah…",
                        }
        store  : Loaded KnowledgeStore.
        model  : Ollama text model.

    Returns:
        Ordered dict mapping section display name → generated section text.
    """
    # Human-readable display names for each section key
    display_names = {
        "title":             "Title",
        "introduction":      "Introduction",
        "about_the_speaker": "About the Speaker",
        "about_the_event":   "About the Event",
        "description":       "Description",
        "conclusion":        "Conclusion",
        "sdg_impact":        "SDG Impact",
        "ieee_goals":        "IEEE Goals and Vision Achieved",
        "acknowledgement":   "Acknowledgement",
    }

    generated = {}
    session_points = event_details.get("session_points", "").strip()

    for section_key, display_name in display_names.items():
        user_facts = event_details.get(section_key, "").strip()
        if not user_facts and section_key != "title" and _should_use_session_points(section_key, session_points):
            user_facts = _section_facts_from_session_points(display_name, session_points)

        # Skip optional sections if no content provided
        if not user_facts and section_key in OPTIONAL_SECTIONS:
            continue

        # Skip entirely empty sections
        if not user_facts:
            continue

        # Title is returned as-is (no generation needed)
        if section_key == "title":
            generated[section_key] = user_facts   # use snake_case key
            continue

        generated[section_key] = generate_section(  # use snake_case key
            section_name = display_name,
            user_facts   = user_facts,
            store        = store,
            model        = model,
        )

    return generated
