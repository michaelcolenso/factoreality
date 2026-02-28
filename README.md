# factoreality

A fully autonomous agentic pipeline that turns a product spec into a finished,
downloadable digital knowledge product — with zero human intervention between
kickoff and delivery.

Write the spec. Hit run. Come back to a finished product.

---

## What it produces

Any packaged digital knowledge product: ebooks, template packs, mini-courses,
worksheet bundles, checklist systems, swipe file collections, resource guides,
or data-driven reports.

## How it works

A sequential 6-stage pipeline coordinated by an orchestrator agent, with a
dedicated QA Reviewer agent that replaces the human at every milestone gate.

```
Spec → Plan → Research → Outline → Draft → Editorial → Format → Package
             Gate 0    Gate 1    Gate 2   Gate 3      Gate 4    Gate 5   Gate 6
```

Every gate scores the stage output on a structured rubric (0.0–1.0). Scores
below the threshold trigger targeted REVISE feedback (up to N retries). After
max retries, the pipeline halts cleanly with a diagnostic — never ships a
product that failed its gates.

## Quick start

### 1. Install

```bash
pip install -r requirements.txt
```

Requires Python 3.11+ and an `ANTHROPIC_API_KEY` environment variable.

Pandoc + XeLaTeX are optional but enable PDF export (Stage 5).

### 2. Create your spec

```bash
cp templates/spec_template.md spec.md
# Edit spec.md — be obsessively specific. This is the only input you provide.
```

The spec is the entire quality ceiling of the pipeline. A precise spec produces
a precise product. A vague spec produces a vague product.

### 3. Run

```bash
python orchestrator.py .
```

Or from a different directory:

```bash
python orchestrator.py /path/to/project
```

Options:
- `--dry-run` — validate spec and plan without making LLM calls
- `--resume`  — continue from the last completed stage after a halt



### Local fallback mode (no API key)

If `ANTHROPIC_API_KEY` is not set, the pipeline now uses a deterministic local LLM fallback so you can run end-to-end for testing and demos without external API calls.

You can force this mode explicitly:

```bash
CONTENT_FACTORY_LOCAL_LLM=1 python orchestrator.py .
```

### 4. Collect output

When complete, check `output/` for deliverables and `status.md` for the
full audit log of every gate, score, decision, and retry.

---

## Project structure

```
factoreality/
├── orchestrator.py          # Entry point — runs the full pipeline
├── spec.md                  # Your product brief (you write this once)
├── implement.md             # Operating rules for all agents (read-only)
├── plan.md                  # Auto-generated pipeline plan (Gate 0)
├── status.md                # Running audit log
│
├── agents/
│   ├── base.py              # Shared LLM call + file helpers
│   ├── planner.py           # Gate 0: generates plan.md
│   ├── research.py          # Stage 1: research brief
│   ├── outline.py           # Stage 2: locked outline
│   ├── content.py           # Stage 3: full draft
│   ├── editorial.py         # Stage 4: grammar, facts, readability
│   ├── formatter.py         # Stage 5: layout + export
│   ├── assembler.py         # Stage 6: package + manifest
│   └── qa_reviewer.py       # QA gate reviewer (separate agent, all gates)
│
├── gates/
│   ├── rubrics.py           # Per-gate scoring rubrics
│   └── gate.py              # Automated verification checks
│
├── utils/
│   ├── file_io.py           # status.md writer + file helpers
│   ├── spec_parser.py       # Parses spec.md into structured dict
│   ├── placeholder_scan.py  # Detects placeholder text in drafts
│   ├── link_checker.py      # Validates URLs return HTTP 200
│   └── readability.py       # Flesch-Kincaid grade level scorer
│
├── templates/
│   ├── spec_template.md     # Blank spec to fill in
│   └── product_profiles.json # Quality settings per product type
│
├── research/                # Stage 1 output
├── outline/                 # Stage 2 output
├── draft/                   # Stage 3 + 4 output
├── editorial/               # Editorial notes
├── qa-reviews/              # One review file per gate (audit trail)
├── assets/                  # Images, templates, brand assets
└── output/                  # Final deliverables + README + ZIP
```

---

## Quality gates

| Gate | Stage | Key checks |
|------|-------|------------|
| 0 | Plan | Covers all spec deliverables, word counts sum correctly |
| 1 | Research | ≥10 sources, competitive matrix, sourced pain points |
| 2 | Outline | Section count in range, word allocations sum to spec |
| 3 | Draft | No placeholders, word count on target, all sections present |
| 4 | Editorial | No grammar errors, readability on target, facts verified |
| 5 | Formatting | Files parse without errors, TOC matches headings |
| 6 | Assembly | Every spec deliverable exists, all files open, manifest accurate |

Default quality threshold: **0.80** (configurable per run in spec.md).

Gate 6 is PASS/FAIL only — no REVISE at the final gate.

---

## Supported product types

| Type | Default threshold |
|------|------------------|
| ebook | 0.85 |
| template-pack | 0.80 |
| worksheet-bundle | 0.80 |
| mini-course | 0.85 |
| resource-guide | 0.80 |
| report | 0.90 |

---

## Cost model (February 2026)

Rough estimates per run for a 15,000-word ebook:

| Component | Approx. cost |
|-----------|-------------|
| Research | $3–8 |
| Outline | $1–2 |
| Content generation | $5–15 |
| Editorial QA | $3–8 |
| Formatting | $2–5 |
| QA Reviewer (6 gates) | $5–12 |
| Retries (avg 2/run) | $2–5 |
| **Total** | **~$22–55** |
| Human time | $0 |

---

## Design

See the full architecture document: [The Content Factory v0.2](https://github.com/michaelcolenso/factoreality)

Key design decisions:

- **Separate QA Reviewer agent** — distinct model call, distinct prompt, fresh
  context at every gate. Self-review doesn't work; a separate reviewer catches
  errors the writer normalizes.
- **Durable file stack** — all state lives in files (spec, plan, implement,
  status), not in context windows. Any agent can resume from any point.
- **Decision locking** — the outline is frozen after Gate 2. No structural
  drift in downstream stages.
- **Stop-and-fix rule** — failures are repaired before proceeding. Errors never
  accumulate across milestones.
- **Cascading failure prevention** — permanent stage failure halts the pipeline
  cleanly. No partial products ship.
