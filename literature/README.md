# Literature

This folder contains source materials (PDFs / HTML) and extracted raw text used to inform the project's methodology for measuring economic performance under Democratic vs. Republican presidents.

**Layout**
- `literature/<slug>/source.*`: Original downloaded artifact(s) (e.g. `source.pdf`, `source.html`).
- `literature/<slug>/source.txt`: Best-effort plain-text extraction from the original artifact.
- `literature/<slug>/notes.md`: Structured review notes (claims, methods, pitfalls, takeaways for our pipeline).
- `literature/manifest.json`: Machine-readable index of sources and local file paths.
- `literature/_scripts/`: Small utilities to (re)download sources and extract text.
- `literature/_templates/`: Templates used for notes.

**Conventions**
- Keep `source.txt` "raw-ish": enough cleaning to remove navigation / boilerplate, but don't paraphrase.
- Put *analysis* and *takeaways* in `notes.md` (not in the raw extracted text).

