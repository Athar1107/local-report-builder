from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.caption_generator import generate_captions
from src.config import DATA_DIR, IMAGES_DIR, OUTPUTS_DIR, REPORTS_DIR, VECTOR_STORE_PATH
from src.image_handler import get_image_info, validate_image
from src.indexer import index_report
from src.report_builder import build_docx
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
    for path in (DATA_DIR, REPORTS_DIR, IMAGES_DIR, OUTPUTS_DIR, VECTOR_STORE_PATH.parent):
        path.mkdir(parents=True, exist_ok=True)


def load_store() -> KnowledgeStore:
    store = KnowledgeStore(VECTOR_STORE_PATH)
    store.load()
    return store


def store_stats() -> dict:
    store = load_store()
    sources = []
    for source in store.sources():
        sources.append({
            "name": source,
            "captions": sum(1 for item in store.metadata if item.get("source") == source and item.get("kind") == "caption"),
            "sections": sum(1 for item in store.metadata if item.get("source") == source and item.get("kind") == "section"),
        })

    return {
        "exists": VECTOR_STORE_PATH.exists(),
        "path": str(VECTOR_STORE_PATH),
        "total": len(store),
        "captions": store.count("caption"),
        "sections": store.count("section"),
        "sources": sources,
    }


def output_files() -> list[dict]:
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    files = []
    for path in sorted(OUTPUTS_DIR.iterdir(), key=lambda item: item.stat().st_mtime, reverse=True):
        if not path.is_file():
            continue
        files.append({
            "name": path.name,
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
    if not event_name:
        return api_error(ValueError("Add an event name before generating a report."))

    event_details = {"title": event_name}
    for key, _label, _help in SECTION_FIELDS:
        event_details[key] = request.form.get(key, "").strip()

    if not any(value for key, value in event_details.items() if key != "title"):
        return api_error(ValueError("Add details to at least one report section."))

    try:
        store = load_store()
        if len(store) == 0:
            raise ValueError("Knowledge store is empty. Index a previous report first.")

        generated = generate_full_report(event_details, store)
        out_path = build_docx(event_name=event_name, sections=generated)
        return jsonify({
            "ok": True,
            "message": f"Report generated: {out_path.name}",
            "result": {"file": out_path.name, "sections": generated},
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
