from __future__ import annotations

import math
import sys
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.caption_generator import generate_captions
from src.config import (
    DATA_DIR,
    DOCS_OUTPUT_DIR,
    IMAGES_DIR,
    OUTPUTS_DIR,
    PDF_OUTPUT_DIR,
    REPORTS_DIR,
    VECTOR_STORE_PATH,
)
from src.image_handler import get_image_info, validate_image
from src.indexer import index_report
from src.report_builder import build_docx, build_pdf
from src.report_generator import generate_full_report
from src.vector_store import KnowledgeStore


app = Flask(__name__)
app.config["SECRET_KEY"] = "ieee-report-generator-local-ui"
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024
CORS(app, resources={r"/api/*": {"origins": "*"}})

ALLOWED_REPORTS = {".pdf", ".docx"}
ALLOWED_IMAGES = {".jpg", ".jpeg", ".png", ".webp", ".gif"}

SECTION_FIELDS = [
    ("introduction", "Introduction", "Purpose, context, and relevance of the event."),
    ("about_the_speaker", "About the Speaker", "Speaker name, role, expertise, and affiliation."),
    ("about_the_event", "About the Event", "Date, time, venue, participants, and event format."),
    ("description", "Description", "Chronological flow, sessions, activities, and highlights."),
    ("conclusion", "Conclusion", "Impact, closing remarks, and key takeaways."),
    ("sdg_impact", "SDG Impact", "Relevant SDGs and how the event contributed."),
    ("ieee_goals", "IEEE Goals", "IEEE goals or branch vision achieved through the event."),
    ("acknowledgement", "Acknowledgement", "Faculty, sponsors, organisers, and supporters."),
]


def ensure_dirs() -> None:
    for path in (
        DATA_DIR,
        REPORTS_DIR,
        IMAGES_DIR,
        OUTPUTS_DIR,
        DOCS_OUTPUT_DIR,
        PDF_OUTPUT_DIR,
        VECTOR_STORE_PATH.parent,
    ):
        path.mkdir(parents=True, exist_ok=True)


def load_store() -> KnowledgeStore:
    store = KnowledgeStore(VECTOR_STORE_PATH)
    store.load()
    return store


def count_report_files_on_disk() -> int:
    """PDF/DOCX files in data/reports (may exceed what is embedded in the vector store)."""
    if not REPORTS_DIR.exists():
        return 0
    n = 0
    for path in REPORTS_DIR.iterdir():
        if path.is_file() and path.suffix.lower() in ALLOWED_REPORTS:
            n += 1
    return n


def knowledge_index_pct(total: int, captions: int, sections: int, source_count: int) -> float:
    """
    0–100 figure from vector-store counts only (not an LLM benchmark).
    Same inputs as captions / sections / total in /api/status.
    """
    if total <= 0:
        return 0.0
    raw = (
        11.0 * math.log1p(captions)
        + 9.0 * math.log1p(sections)
        + 6.5 * math.log1p(max(source_count, 1))
    )
    return round(min(100.0, raw), 1)


def store_stats() -> dict:
    store = load_store()
    sources = []
    for source in store.sources():
        sources.append({
            "name": source,
            "captions": sum(1 for item in store.metadata if item.get("source") == source and item.get("kind") == "caption"),
            "sections": sum(1 for item in store.metadata if item.get("source") == source and item.get("kind") == "section"),
        })

    captions = store.count("caption")
    sections = store.count("section")
    total = len(store)
    source_count = len(sources)
    reports_on_disk = count_report_files_on_disk()

    return {
        "exists": VECTOR_STORE_PATH.exists(),
        "path": str(VECTOR_STORE_PATH),
        "total": total,
        "captions": captions,
        "sections": sections,
        "sources": sources,
        "reports_on_disk": reports_on_disk,
        "knowledge_index_pct": knowledge_index_pct(total, captions, sections, source_count),
    }


def prediction_confidence(score: float | None) -> float:
    """Convert cosine similarity from the FAISS store into a readable 0-100 score."""
    if score is None:
        return 0.0
    return round(max(0.0, min(1.0, float(score))) * 100, 1)


def rag_prediction(query: str, kind: str = "section", top_k: int = 5) -> dict:
    store = load_store()
    if len(store) == 0:
        raise ValueError("Knowledge store is empty. Index a previous report first.")

    query = query.strip()
    if not query:
        raise ValueError("Enter a query before checking prediction.")
    if kind not in {"caption", "section"}:
        raise ValueError("Prediction type must be caption or section.")

    matches = store.retrieve(query, top_k=top_k, kind=kind)
    top_score = matches[0]["score"] if matches else None
    return {
        "query": query,
        "kind": kind,
        "prediction": matches[0]["text"] if matches else "",
        "confidence_pct": prediction_confidence(top_score),
        "note": "Confidence is retrieval similarity, not supervised model accuracy.",
        "matches": [
            {
                "text": item.get("text", ""),
                "source": item.get("source", "unknown"),
                "heading": item.get("heading", ""),
                "score": round(float(item.get("score", 0.0)), 4),
                "confidence_pct": prediction_confidence(item.get("score")),
            }
            for item in matches
        ],
    }


def output_files() -> list[dict]:
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    files = []
    for path in sorted(OUTPUTS_DIR.rglob("*"), key=lambda item: item.stat().st_mtime, reverse=True):
        if not path.is_file():
            continue
        if path.name == ".gitkeep":
            continue
        relative_name = path.relative_to(OUTPUTS_DIR).as_posix()
        files.append({
            "name": relative_name,
            "display_name": path.name,
            "folder": path.parent.relative_to(OUTPUTS_DIR).as_posix() if path.parent != OUTPUTS_DIR else "",
            "size_kb": max(1, round(path.stat().st_size / 1024)),
            "modified": datetime.fromtimestamp(path.stat().st_mtime).strftime("%d %b %Y, %I:%M %p"),
        })
    return files


def save_upload(upload, destination: Path, allowed_extensions: set[str]) -> Path:
    if not upload or not upload.filename:
        raise ValueError("Choose a file before running this action.")

    filename = secure_filename(upload.filename)
    suffix = Path(filename).suffix.lower()
    if suffix not in allowed_extensions:
        raise ValueError(f"Unsupported file type. Allowed: {', '.join(sorted(allowed_extensions))}")

    destination.mkdir(parents=True, exist_ok=True)
    target = destination / filename
    if target.exists():
        target = destination / f"{target.stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{target.suffix}"
    upload.save(target)
    return target


def api_error(exc: Exception, status: int = 400):
    return jsonify({"ok": False, "error": str(exc)}), status


@app.get("/")
def api_home():
    return jsonify({
        "name": "IEEE Report Studio API",
        "status": "running",
        "frontend": "Run the React app from ./frontend with npm run dev.",
    })


@app.get("/api/status")
def api_status():
    ensure_dirs()
    return jsonify({"ok": True, "stats": store_stats(), "outputs": output_files(), "sections": SECTION_FIELDS})


@app.post("/api/predict")
def api_predict():
    ensure_dirs()
    try:
        payload = request.get_json(silent=True) or request.form
        query = payload.get("query", "")
        kind = payload.get("kind", "section")
        top_k = int(payload.get("top_k", 5))
        top_k = max(1, min(top_k, 10))
        return jsonify({"ok": True, "result": rag_prediction(query, kind, top_k)})
    except Exception as exc:
        return api_error(exc)


@app.post("/api/index")
def api_index_document():
    ensure_dirs()
    try:
        report_path = save_upload(request.files.get("report"), REPORTS_DIR, ALLOWED_REPORTS)
        result = index_report(str(report_path))
        store = load_store()
        store.add(result["captions"] + result["sections"])
        store.save()
        return jsonify({
            "ok": True,
            "message": f"Indexed {len(result['captions'])} captions and {len(result['sections'])} sections from {report_path.name}.",
            "indexed": {"captions": len(result["captions"]), "sections": len(result["sections"]), "source": report_path.name},
            "stats": store_stats(),
        })
    except Exception as exc:
        return api_error(exc)


@app.post("/api/caption")
def api_caption_image():
    ensure_dirs()
    description = request.form.get("description", "").strip()
    if not description:
        return api_error(ValueError("Add a short image description before generating captions."))

    try:
        store = load_store()
        if len(store) == 0:
            raise ValueError("Knowledge store is empty. Index a previous report first.")

        image_path = save_upload(request.files.get("image"), IMAGES_DIR, ALLOWED_IMAGES)
        validate_image(str(image_path))
        info = get_image_info(str(image_path))
        captions = generate_captions(str(image_path), description, store)

        OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
        out_file = OUTPUTS_DIR / f"{info['stem']}_captions.txt"
        out_file.write_text(
            f"Image: {info['filename']}\nDescription: {description}\n\n"
            + "\n\n".join(f"Variation {idx + 1}:\n{caption}" for idx, caption in enumerate(captions)),
            encoding="utf-8",
        )
        return jsonify({
            "ok": True,
            "message": "Captions generated and saved to outputs.",
            "result": {"image": info, "description": description, "captions": captions, "file": out_file.name},
            "outputs": output_files(),
        })
    except Exception as exc:
        return api_error(exc)


@app.post("/api/report")
def api_report_document():
    ensure_dirs()
    event_name = request.form.get("event", "").strip()
    session_points = request.form.get("session_points", "").strip()
    output_format = request.form.get("output_format", "docx").strip().lower()
    if not event_name:
        return api_error(ValueError("Add an event name before generating a report."))
    if output_format not in {"docx", "pdf"}:
        return api_error(ValueError("Choose DOCX or PDF as the output format."))

    event_details = {"title": event_name, "session_points": session_points}
    for key, _label, _help in SECTION_FIELDS:
        event_details[key] = request.form.get(key, "").strip()

    if not session_points and not any(value for key, value in event_details.items() if key not in {"title", "session_points"}):
        return api_error(ValueError("Add the session points before generating a report."))

    try:
        store = load_store()
        if len(store) == 0:
            raise ValueError("Knowledge store is empty. Index a previous report first.")

        generated = generate_full_report(event_details, store)
        if output_format == "pdf":
            out_path = build_pdf(event_name=event_name, sections=generated)
        else:
            out_path = build_docx(event_name=event_name, sections=generated)
        output_name = out_path.relative_to(OUTPUTS_DIR).as_posix()
        return jsonify({
            "ok": True,
            "message": f"Report generated: {out_path.name}",
            "result": {"file": output_name, "display_name": out_path.name, "format": output_format, "sections": generated},
            "outputs": output_files(),
        })
    except Exception as exc:
        return api_error(exc)


@app.get("/api/outputs/<path:filename>")
def download_output(filename: str):
    return send_from_directory(OUTPUTS_DIR, filename, as_attachment=True)


if __name__ == "__main__":
    ensure_dirs()
    app.run(host="127.0.0.1", port=5000, debug=False)
