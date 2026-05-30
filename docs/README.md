# Engineering Report

The ThutoTrack engineering report lives in [`report.tex`](report.tex).

## Compile to PDF

You need a TeX distribution installed (TeX Live, MiKTeX, or MacTeX). On Windows the easiest is [MiKTeX](https://miktex.org/download).

### Option 1 — `latexmk` (recommended)

```bash
cd docs
latexmk -pdf report.tex
```

`latexmk` runs `pdflatex` the right number of times for the TOC, cross-references, and the TikZ diagram to settle.

### Option 2 — plain `pdflatex`

```bash
cd docs
pdflatex report.tex
pdflatex report.tex   # second pass for TOC / references
```

### Option 3 — Overleaf (no local install)

1. Create a new project at https://overleaf.com
2. Upload `report.tex`
3. Set the main document to `report.tex`
4. Click **Recompile**

## What's covered

- Title page, abstract, table of contents
- Introduction (background + motivation)
- Problem statement
- Aim and objectives
- Literature review
- Methodology (development approach + technology stack + architecture)
- System design (roles, data model, modules)
- Implementation (per-portal feature description + code listing)
- Testing strategy + coverage table + CI
- Results, limitations, future work
- Conclusion
- References
- Appendices (repository layout, sample test output, glossary)

## Filling in the blanks

Open `report.tex` and replace these placeholders before submitting:

- `[Department Name]` — your department on the title page
- `[Institution Name]` — your university/college on the title page
- `[Supervisor Name]` — your project supervisor on the title page

Search for `[` in the document — those are the only manual edits needed.
