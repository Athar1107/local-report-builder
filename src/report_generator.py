"""
report_generator.py
-------------------
Generates a full IEEE event report section-by-section.

The generator uses only the organiser's supplied event facts for report
content. Indexed reports may still be required by the app workflow, but their
raw text is not passed into the LLM during report generation. This prevents
facts from older events from leaking into a newly generated report.
"""

import ollama

from .config import REPORT_GUIDELINES, TEXT_MODEL
from .vector_store import KnowledgeStore


_SECTION_PROMPT = """{guidelines}

Write the "{section_name}" section for the event report.

Facts and details provided by the organiser (use ONLY these; do not invent):
---
{user_facts}
---

Rules:
- Mention only the event name, date, venue, speaker, participant count,
  organiser, result, activity, and acknowledgement details that appear in the
  organiser facts above.
- UN Sustainable Development Goals may be selected only when they are clearly
  associated with the event notes.
- Do not copy, infer, or reuse facts from indexed reports or previous events.
- If a detail is missing, omit it instead of guessing.
- Past tense throughout. Third person only; do not use "we", "I", "our", "us",
  or "you".
- UK English spelling. Formal, institutional tone.
- End with a smooth closing sentence.
- Return ONLY the section text with its heading. No preamble or commentary.
"""


# Optional sections are skipped unless the organiser's notes explicitly mention
# details that belong in them. About the Speaker is a core section for this
# report format.
OPTIONAL_SECTIONS = {
    "ieee_goals",
    "acknowledgement",
}

CORE_SECTIONS = {
    "introduction",
    "about_the_speaker",
    "about_the_event",
    "conclusion",
    "sdg_impact",
}

UN_SDG_GOALS = """
UN Sustainable Development Goals:
1. No Poverty
2. Zero Hunger
3. Good Health and Well-being
4. Quality Education
5. Gender Equality
6. Clean Water and Sanitation
7. Affordable and Clean Energy
8. Decent Work and Economic Growth
9. Industry, Innovation and Infrastructure
10. Reduced Inequalities
11. Sustainable Cities and Communities
12. Responsible Consumption and Production
13. Climate Action
14. Life Below Water
15. Life on Land
16. Peace, Justice and Strong Institutions
17. Partnerships for the Goals
""".strip()

OPTIONAL_SECTION_KEYWORDS = {
    "about_the_speaker": (
        "speaker",
        "resource person",
        "guest",
        "expert",
        "trainer",
        "mentor",
        "professor",
        "prof.",
        "dr.",
        "mr.",
        "mrs.",
        "ms.",
    ),
    "sdg_impact": (
        "sdg",
        "sustainable development",
        "sustainability",
        "goal ",
    ),
    "ieee_goals": (
        "ieee goal",
        "ieee goals",
        "ieee vision",
        "ieee mission",
        "technical awareness",
        "professional development",
    ),
    "acknowledgement": (
        "acknowledge",
        "acknowledgement",
        "thanks",
        "gratitude",
        "sponsor",
        "faculty coordinator",
        "coordinator",
        "support",
    ),
}

SECTION_SESSION_INSTRUCTIONS = {
    "about_the_speaker": (
        "For About the Speaker, use only speaker, trainer, guest, or resource "
        "person details found in the notes. If no speaker name or speaker role "
        "is present, keep the section generic and do not invent a person."
    ),
    "about_the_event": (
        "For About the Event, include the event metadata and the session "
        "description together: date, time, venue, participants, format, "
        "chronological flow, activities, highlights, and outcomes when present. "
        "Do not create a separate Description section from these same notes."
    ),
    "sdg_impact": (
        "For SDG Impact, identify the UN Sustainable Development Goals that are "
        "clearly associated with the event. Use the official goal number and "
        "name, then explain the connection to the event in one formal sentence "
        "per goal. Do not include a goal unless the event notes support it.\n\n"
        f"{UN_SDG_GOALS}"
    ),
}


def _ollama_text(prompt: str, model: str = TEXT_MODEL) -> str:
    try:
        resp = ollama.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp["message"]["content"].strip()
    except Exception as exc:
        raise ConnectionError(f"Ollama not running. (ollama serve)\n{exc}") from exc


def _should_use_session_points(section_key: str, session_points: str) -> bool:
    if not session_points:
        return False
    if section_key in CORE_SECTIONS:
        return True
    if section_key == "description":
        return False

    text = session_points.lower()
    return any(keyword in text for keyword in OPTIONAL_SECTION_KEYWORDS.get(section_key, ()))


def _section_facts_from_session_points(
    section_name: str,
    event_name: str,
    session_points: str,
    section_key: str,
) -> str:
    instruction = SECTION_SESSION_INSTRUCTIONS.get(
        section_key,
        f"Use these notes to write only the '{section_name}' section.",
    )
    return (
        f"Event name: {event_name}\n\n"
        f"Event notes supplied by the organiser:\n{session_points}\n\n"
        f"{instruction} "
        "Select only the relevant facts for this section, keep the chronology "
        "clear, and do not add any names, dates, numbers, outcomes, SDGs, or "
        "acknowledgements that are not supported by the notes."
    )


def generate_section(
    section_name: str,
    user_facts: str,
    store: KnowledgeStore,
    model: str = TEXT_MODEL,
) -> str:
    """
    Generate one report section using only user-supplied event facts.

    The `store` parameter is kept for API compatibility with the existing app,
    but raw indexed-report text is not sent to the LLM. That keeps previous
    event names, speakers, dates, venues, and outcomes out of new reports.
    """
    _ = store
    return _ollama_text(
        _SECTION_PROMPT.format(
            guidelines=REPORT_GUIDELINES,
            section_name=section_name,
            user_facts=user_facts,
        ),
        model,
    )


def generate_full_report(
    event_details: dict[str, str],
    store: KnowledgeStore,
    model: str = TEXT_MODEL,
) -> dict[str, str]:
    """
    Generate a complete report section by section.

    event_details can either contain per-section facts or one `session_points`
    field. When `session_points` is supplied, it is reused carefully for each
    section while optional sections are generated only when matching details are
    present.
    """
    display_names = {
        "title": "Title",
        "introduction": "Introduction",
        "about_the_speaker": "About the Speaker",
        "about_the_event": "About the Event",
        "description": "Description",
        "conclusion": "Conclusion",
        "sdg_impact": "SDG Impact",
        "ieee_goals": "IEEE Goals and Vision Achieved",
        "acknowledgement": "Acknowledgement",
    }

    generated = {}
    event_name = event_details.get("title", "").strip()
    session_points = event_details.get("session_points", "").strip()

    for section_key, display_name in display_names.items():
        user_facts = event_details.get(section_key, "").strip()
        if (
            not user_facts
            and section_key != "title"
            and _should_use_session_points(section_key, session_points)
        ):
            user_facts = _section_facts_from_session_points(
                section_name=display_name,
                event_name=event_name,
                session_points=session_points,
                section_key=section_key,
            )

        if not user_facts and section_key in OPTIONAL_SECTIONS:
            continue
        if not user_facts:
            continue

        if section_key == "title":
            generated[section_key] = user_facts
            continue

        generated[section_key] = generate_section(
            section_name=display_name,
            user_facts=user_facts,
            store=store,
            model=model,
        )

    return generated
