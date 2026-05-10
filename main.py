"""
main.py
-------
IEEE Report Generator & Caption Generator — fully local, no API.
Uses Ollama (LLaVA + llama3) + sentence-transformers + FAISS.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ONE-TIME SETUP
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ollama pull llava && ollama pull llama3
  ollama serve                           # keep running in background
  pip install -r requirements.txt

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WORKFLOW
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Step 1 — Index previous year's report (run once per report)
  python main.py index --report data/reports/annual_2023.pdf

Step 2A — Generate captions for a new image
  python main.py caption \\
    --image data/images/award_night.jpg \\
    --text  "Award ceremony at the IEEE student branch annual event"

Step 2B — Generate a full event report from your text descriptions
  python main.py report \\
    --event "IEEE Student Branch Induction 2024" \\
    --intro       "The induction was held on 10th March 2024 at CHARUSAT..." \\
    --objectives  "To welcome new members and present the annual roadmap..." \\
    --activities  "Three sessions were conducted: orientation, demo, quiz..." \\
    --outcomes    "82 new members inducted. Guest lecture by Dr. Mehta..." \\
    --conclusion  "The event successfully achieved its stated objectives..."

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
UTILITY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  python main.py status   # show knowledge store contents
  python main.py clear    # wipe the knowledge store
"""

import argparse
import sys
from pathlib import Path

# ── Path fix: ensure project root is always on sys.path ───────────────────────
_PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_PROJECT_ROOT))

# ── Sanity check: make sure src/ folder exists next to main.py ────────────────
_SRC_DIR = _PROJECT_ROOT / "src"
if not _SRC_DIR.exists():
    print("\n❌  ERROR: 'src' folder not found.")
    print(f"   main.py is at : {_PROJECT_ROOT / 'main.py'}")
    print(f"   Expected src/ at: {_SRC_DIR}")
    print("\n   Your folder must look like this:")
    print("     ieee_report_gen/")
    print("     ├── main.py")
    print("     ├── requirements.txt")
    print("     └── src/")
    print("         ├── __init__.py")
    print("         ├── config.py")
    print("         ├── indexer.py")
    print("         ├── embedder.py")
    print("         ├── vector_store.py")
    print("         ├── image_handler.py")
    print("         ├── caption_generator.py")
    print("         ├── report_generator.py")
    print("         └── report_builder.py")
    print("\n   Make sure all src/ files are in the same folder as main.py.\n")
    sys.exit(1)

from rich.console import Console
from rich.panel   import Panel
from rich.table   import Table
from rich         import box

from src.config           import OUTPUTS_DIR, VECTOR_STORE_PATH, TOP_K_CAPTIONS
from src.indexer          import index_report
from src.vector_store     import KnowledgeStore
from src.image_handler    import validate_image, get_image_info, discover_images
from src.caption_generator import generate_captions
from src.report_generator  import generate_full_report
from src.report_builder    import build_docx

console = Console()


# ── Helpers ────────────────────────────────────────────────────────────────────

def _load_store() -> KnowledgeStore:
    store = KnowledgeStore(VECTOR_STORE_PATH)
    store.load()
    return store


def _require_store(store: KnowledgeStore) -> None:
    if len(store) == 0:
        console.print(
            "[yellow]Knowledge store is empty.[/]\n"
            "Run:  [bold]python main.py index --report <file>[/]"
        )
        sys.exit(1)


def _print_captions(captions: list[str], label: str = "") -> None:
    prefix = f"[dim]{label}[/] — " if label else ""
    for i, cap in enumerate(captions, 1):
        console.print(Panel(
            f"[bold white]{cap}[/]",
            title=f"{prefix}[green]Variation {i}[/]",
            border_style="green",
            padding=(0, 2),
        ))


# ── Command: index ─────────────────────────────────────────────────────────────

def cmd_index(args) -> None:
    """Index a previous-year report — extracts both captions and sections."""
    if not Path(args.report).exists():
        console.print(f"[red]File not found:[/] {args.report}")
        sys.exit(1)

    store = _load_store()
    console.rule(f"[bold]Indexing: {Path(args.report).name}")

    # ── Extract captions ──────────────────────────────────────────────────────
    console.print("[dim]Step 1/3 — Extracting image captions…[/]")
    result = index_report(args.report)

    captions = result["captions"]
    sections = result["sections"]

    if captions:
        tbl = Table("#", "Caption", box=box.SIMPLE)
        for i, c in enumerate(captions, 1):
            tbl.add_row(str(i), c["text"][:95] + ("…" if len(c["text"]) > 95 else ""))
        console.print(tbl)
    else:
        console.print("  [dim]No captions found.[/]")

    # ── Extract sections ──────────────────────────────────────────────────────
    console.print(f"\n[dim]Step 2/3 — Extracted {len(sections)} report sections:[/]")
    if sections:
        tbl2 = Table("#", "Section heading", "Content preview", box=box.SIMPLE)
        for i, s in enumerate(sections, 1):
            preview = s.get("content", s["text"])[:70]
            tbl2.add_row(str(i), s.get("heading", "—"), preview + "…")
        console.print(tbl2)
    else:
        console.print("  [dim]No sections found.[/]")

    # ── Embed & save ──────────────────────────────────────────────────────────
    console.print(f"\n[dim]Step 3/3 — Embedding and saving to knowledge store…[/]")
    store.add(captions + sections)
    store.save()

    console.print(
        f"\n[green]✓[/] Indexed [bold]{len(captions)}[/] captions + "
        f"[bold]{len(sections)}[/] sections from "
        f"[italic]{result['source']}[/].  "
        f"Total in store: [bold]{len(store)}[/]"
    )


# ── Command: caption ───────────────────────────────────────────────────────────

def cmd_caption(args) -> None:
    """Generate 3 IEEE captions for a single image using RAG."""
    store = _load_store()
    _require_store(store)

    console.rule("[bold]Caption Generator")

    try:
        path = validate_image(args.image)
        info = get_image_info(args.image)
    except (FileNotFoundError, ValueError) as e:
        console.print(f"[red]Error:[/] {e}")
        sys.exit(1)

    console.print(
        f"  [bold]★ Image      :[/] [cyan]{info['filename']}[/]  "
        f"[dim]{info['width']}×{info['height']} px  {info['size_kb']} KB[/]"
    )
    console.print(
        f"  [bold]★ Description:[/] [italic white]{args.text}[/]\n"
    )

    try:
        captions = generate_captions(
            image_path  = args.image,
            description = args.text,
            store       = store,
        )
    except (ValueError, ConnectionError) as e:
        console.print(f"[red]Error:[/] {e}")
        sys.exit(1)

    console.print()
    _print_captions(captions)

    # Save
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    out_file = OUTPUTS_DIR / f"{info['stem']}_captions.txt"
    out_file.write_text(
        f"Image      : {info['filename']}\n"
        f"Description: {args.text}\n"
        + "─" * 60 + "\n\n"
        + "\n\n".join(f"Variation {i+1}:\n{c}" for i, c in enumerate(captions)),
        encoding="utf-8",
    )
    console.print(f"\n[dim]Saved → {out_file}[/]")


# ── Command: caption-batch ─────────────────────────────────────────────────────

def cmd_caption_batch(args) -> None:
    """Generate captions for every image in a folder."""
    store = _load_store()
    _require_store(store)

    try:
        images = discover_images(args.folder)
    except NotADirectoryError as e:
        console.print(f"[red]Error:[/] {e}")
        sys.exit(1)

    if not images:
        console.print(f"[yellow]No images found in '{args.folder}'.[/]")
        sys.exit(0)

    console.rule(f"[bold]Batch Caption — {len(images)} image(s)")
    shared_text = args.text or ""
    results = []

    for img_path in images:
        console.print(f"\n[bold cyan]━━ {img_path.name} ━━[/]")
        try:
            captions = generate_captions(
                image_path  = str(img_path),
                description = shared_text or img_path.stem.replace("_", " "),
                store       = store,
            )
            _print_captions(captions, img_path.name)
            results.append({"image": img_path.name, "captions": captions, "ok": True})
        except Exception as e:
            console.print(f"  [red]Failed:[/] {e}")
            results.append({"image": img_path.name, "captions": [], "ok": False, "err": str(e)})

    console.rule("[bold]Batch Summary")
    tbl = Table("Image", "Status", "Variation 1 preview", box=box.SIMPLE)
    for r in results:
        status  = "[green]✓[/]" if r["ok"] else f"[red]✗ {r.get('err','')}[/]"
        preview = r["captions"][0][:65] + "…" if r.get("captions") else "—"
        tbl.add_row(r["image"], status, preview)
    console.print(tbl)
    console.print(f"\n[green]Done.[/] Captions saved to [bold]{OUTPUTS_DIR}/[/]")


# ── Command: report ────────────────────────────────────────────────────────────

def cmd_report(args) -> None:
    """Generate a full event report DOCX from user text descriptions."""
    store = _load_store()
    _require_store(store)

    console.rule(f"[bold]Report Generator: {args.event}")

    # Map CLI args → section keys (Alumni Connect structure)
    event_details = {
        "title":             args.event,
        "introduction":      getattr(args, "intro",           "") or "",
        "about_the_speaker": getattr(args, "speaker",         "") or "",
        "about_the_event":   getattr(args, "about",           "") or "",
        "description":       getattr(args, "description",     "") or "",
        "conclusion":        getattr(args, "conclusion",      "") or "",
        "sdg_impact":        getattr(args, "sdg",             "") or "",
        "ieee_goals":        getattr(args, "goals",           "") or "",
        "acknowledgement":   getattr(args, "acknowledgement", "") or "",
    }

    # Show what will be generated
    provided = {k: v for k, v in event_details.items() if v.strip() and k != "title"}
    console.print(f"  Sections to generate: [bold]{', '.join(provided.keys())}[/]\n")

    if not provided:
        console.print("[red]Error:[/] Provide at least one section (--intro, --about, --description, etc.)")
        sys.exit(1)

    # Generate each section
    from src.report_generator import generate_full_report
    try:
        generated = generate_full_report(event_details, store)
    except ConnectionError as e:
        console.print(f"[red]Error:[/] {e}")
        sys.exit(1)

    display = {
        "title":             "Title",
        "introduction":      "Introduction",
        "about_the_speaker": "About the Speaker",
        "about_the_event":   "About the Event",
        "description":       "Description",
        "conclusion":        "Conclusion",
        "sdg_impact":        "SDG Impact",
        "ieee_goals":        "IEEE Goals",
        "acknowledgement":   "Acknowledgement",
    }
    for section_key in generated:
        console.print(f"  [green]✓[/] {display.get(section_key, section_key)}")

    # Build DOCX
    console.print("\n  [dim]→ Building DOCX…[/]")
    out_path = build_docx(event_name=args.event, sections=generated)

    console.print(Panel(
        f"[bold white]{out_path.name}[/]\n"
        f"[dim]{len(generated)} sections  ·  {out_path.stat().st_size // 1024} KB[/]",
        title="[green]Report Generated[/]",
        border_style="green",
        padding=(0, 2),
    ))
    console.print(f"[dim]Saved → {out_path}[/]")


# ── Command: status ────────────────────────────────────────────────────────────

def cmd_status(_args) -> None:
    store = _load_store()
    console.rule("[bold]Knowledge Store Status")
    console.print(f"[dim]Store path : {VECTOR_STORE_PATH}[/]")
    console.print(f"[dim]File exists: {VECTOR_STORE_PATH.exists()}[/]")

    if len(store) == 0:
        console.print("[yellow]Store is empty — run: python main.py index --report <file>[/]")
        return

    console.print(f"  Total entries   : [bold]{len(store)}[/]")
    console.print(f"  Captions indexed: [bold]{store.count('caption')}[/]")
    console.print(f"  Sections indexed: [bold]{store.count('section')}[/]")
    console.print(f"  Store file      : [dim]{VECTOR_STORE_PATH}[/]\n")
    console.print(f"  Sources:")
    for src in store.sources():
        n_cap = sum(1 for m in store.metadata
                    if m.get("source") == src and m.get("kind") == "caption")
        n_sec = sum(1 for m in store.metadata
                    if m.get("source") == src and m.get("kind") == "section")
        console.print(
            f"    • {src}  "
            f"[dim]({n_cap} captions, {n_sec} sections)[/]"
        )


# ── Command: clear ─────────────────────────────────────────────────────────────

def cmd_clear(_args) -> None:
    if VECTOR_STORE_PATH.exists():
        confirm = input("Delete the entire knowledge store? [y/N] ").strip().lower()
        if confirm == "y":
            VECTOR_STORE_PATH.unlink()
            console.print("[green]✓ Knowledge store cleared.[/]")
        else:
            console.print("[dim]Cancelled.[/]")
    else:
        console.print("[yellow]No knowledge store found.[/]")


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="ieee-gen",
        description="IEEE Report Generator + Caption Generator (fully local, no API).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # index
    p = sub.add_parser("index", help="Index a previous-year report (captions + sections)")
    p.add_argument("--report", required=True, metavar="FILE",
                   help="Path to .pdf or .docx previous-year report")

    # caption (single image)
    p = sub.add_parser("caption", help="Generate 3 IEEE captions for one image")
    p.add_argument("--image", required=True, metavar="FILE")
    p.add_argument("--text",  required=True, metavar="TEXT",
                   help="Your description of the image")

    # caption-batch (folder)
    p = sub.add_parser("caption-batch", help="Generate captions for all images in a folder")
    p.add_argument("--folder", required=True, metavar="DIR")
    p.add_argument("--text",   default="",   metavar="TEXT",
                   help="Shared description for all images (optional)")

    # report (generate full DOCX)
    p = sub.add_parser("report", help="Generate a full event report DOCX")
    p.add_argument("--event",           required=True, metavar="NAME",
                   help="Event name (used as report title)")
    p.add_argument("--model",           default="", metavar="MODEL",
                   help="Ollama model to use (default: llama3.1:8b from config)")
    p.add_argument("--intro",           default="", metavar="TEXT",
                   help="Introduction - purpose and context of the event")
    p.add_argument("--speaker",         default="", metavar="TEXT",
                   help="About the Speaker - name, designation, background (optional)")
    p.add_argument("--about",           default="", metavar="TEXT",
                   help="About the Event - date, time, venue, number of participants")
    p.add_argument("--description",     default="", metavar="TEXT",
                   help="Description - chronological flow of what happened")
    p.add_argument("--outcomes",        default="", metavar="TEXT",
                   help="Results and outcomes (optional)")
    p.add_argument("--conclusion",      default="", metavar="TEXT",
                   help="Conclusion - closing remarks and impact")
    p.add_argument("--sdg",             default="", metavar="TEXT",
                   help="SDG Impact bullets (optional)")
    p.add_argument("--goals",           default="", metavar="TEXT",
                   help="IEEE Goals and Vision Achieved bullets (optional)")
    p.add_argument("--acknowledgement", default="", metavar="TEXT",
                   help="Acknowledgement - faculty, sponsors, organisers")

    # status
    sub.add_parser("status", help="Show knowledge store contents")

    # clear
    sub.add_parser("clear",  help="Wipe the knowledge store")

    args = parser.parse_args()
    {
        "index":         cmd_index,
        "caption":       cmd_caption,
        "caption-batch": cmd_caption_batch,
        "report":        cmd_report,
        "status":        cmd_status,
        "clear":         cmd_clear,
    }[args.command](args)


if __name__ == "__main__":
    main()