"""
caption_generator.py
--------------------
Generates 3 IEEE-style caption variations for an image.

Pipeline:
  user text description
        │
        ▼
  KnowledgeStore.retrieve(kind="caption")   ← top-5 past captions from RAG
        │
        ▼
  LLaVA  ←  image + text + retrieved captions + IEEE guidelines
        │
        ▼
  3 × IEEE-style caption variations
"""

import re

import ollama

from .config        import VISION_MODEL, CAPTION_GUIDELINES, TOP_K_CAPTIONS
from .image_handler import encode_image_b64
from .vector_store  import KnowledgeStore


# ── Prompt ─────────────────────────────────────────────────────────────────────

_CAPTION_PROMPT = """{guidelines}

━━━ STYLE REFERENCE — captions from previous year's report ━━━
Study these carefully. Match their house style, length, and phrasing:

{style_examples}

━━━ YOUR TASK ━━━
Look at the image and write exactly 3 caption variations.
Description of this image: {description}

FORMAT — return ONLY this:
1. [caption]
2. [caption]
3. [caption]

Each must be 8–15 words, follow ALL guidelines, and offer a different angle.
"""


# ── Parser ─────────────────────────────────────────────────────────────────────

def _parse(raw: str, n: int = 3) -> list[str]:
    """Extract n captions from numbered model output."""
    parts = re.split(r"\n\s*(?:Variation\s*)?\d+[.):\-]\s*", raw.strip())
    parts = [p.strip().strip('"').strip("'") for p in parts
             if 4 < len(p.strip().split()) <= 25]
    if len(parts) >= n:
        return parts[:n]
    # fallback: non-empty lines of plausible length
    parts = [p.strip() for p in raw.splitlines()
             if 4 < len(p.strip().split()) <= 25]
    return (parts + ["[caption not generated]"] * n)[:n]


# ── Main function ──────────────────────────────────────────────────────────────

def generate_captions(
    image_path:  str,
    description: str,
    store:       KnowledgeStore,
    model:       str = VISION_MODEL,
) -> list[str]:
    """
    Generate 3 IEEE-style caption variations for a new image.

    Args:
        image_path  : Path to the image file.
        description : User-provided text description of the image.
                      Used as the RAG query and generation context.
        store       : Loaded KnowledgeStore (must contain caption entries).
        model       : Ollama vision model name.

    Returns:
        List of 3 caption strings.
    """
    # 1. Retrieve top-k most similar past captions from RAG store
    retrieved = store.retrieve(description, top_k=TOP_K_CAPTIONS, kind="caption")

    if not retrieved:
        raise ValueError(
            "No captions in knowledge store. "
            "Run: python main.py index --report <file>"
        )

    style_examples = "\n".join(
        f"  Example {i+1}: {r['text']}"
        for i, r in enumerate(retrieved)
    )

    prompt = _CAPTION_PROMPT.format(
        guidelines    = CAPTION_GUIDELINES,
        style_examples= style_examples,
        description   = description,
    )

    img_b64 = encode_image_b64(image_path)

    try:
        response = ollama.chat(
            model=model,
            messages=[{
                "role":    "user",
                "content": prompt,
                "images":  [img_b64],
            }],
        )
    except Exception as e:
        raise ConnectionError(f"Ollama not running. (ollama serve)\n{e}")

    return _parse(response["message"]["content"].strip())
