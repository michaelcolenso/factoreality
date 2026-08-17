# factoreality

A harness-native agentic pipeline that turns a product spec into a finished,
downloadable digital knowledge product — with zero human intervention between
kickoff and delivery and no outside LLM API dependency.

Write the spec. Hit run. Come back to a finished product.

---

## What it produces

Any packaged digital knowledge product: ebooks, template packs, mini-courses,
worksheet bundles, checklist systems, swipe file collections, resource guides,
or data-driven reports.

## How it works

A sequential 6-stage pipeline coordinated by an orchestrator agent, with a
dedicated QA Reviewer agent that replaces the human at every milestone gate.
All planning, drafting, reviewing, and packaging tasks are executed by the local
agentic harness rather than delegated to a hosted model API.

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

Requires Python 3.11+. No `ANTHROPIC_API_KEY`, hosted model provider, or network
access is required for the core pipeline.

Pandoc + XeLaTeX are optional system tools that enable PDF export (Stage 5).

### 2. Provide input (choose one path)

**Path A — Manual spec (most control)**

```bash
cp templates/spec_template.md spec.md
# Edit spec.md — be obsessively specific.
```

**Path B — Brief-driven bootstrap (fastest start)**

```bash
cp templates/brief_template.md product-brief.md
# Edit product-brief.md
python orchestrator.py . --brief-file product-brief.md
```

The pipeline still runs against `spec.md` as its source of truth. In Path B,
`spec.md` is generated for you before Gate 0.

### 3. Run

```bash
python orchestrator.py .
```

Or from a different directory:

```bash
python orchestrator.py /path/to/project
```

Options:
- `--dry-run` — validate spec and plan without making external LLM API calls
- `--resume`  — continue from the last completed stage after a halt
- `--brief "..."` — generate `spec.md` from a short product brief, then run
- `--brief-file path/to/brief.md` — same as `--brief`, reading from a file
- `--regenerate-spec` — force re-generation of `spec.md` from the brief (requires brief input)

Notes:
- Existing `spec.md` is reused by default.
- Use `--regenerate-spec` with `--brief` or `--brief-file` to overwrite `spec.md`.
- `--resume` continues from `status.md` and does not require regenerating `spec.md`.

Or drive the whole thing from a browser:

```bash
python ui/server.py          # http://127.0.0.1:8420
```

The control room runs the same pipeline, streams the console live, shows every
gate score against its threshold, lets you edit `spec.md` with live parse
validation, and previews or downloads any artifact a run produced. Stdlib only —
nothing to install. See [ui/README.md](ui/README.md).

Or run it with no machine of your own, from a phone: the **Run pipeline**
workflow takes a brief, executes the pipeline on a GitHub Actions runner, and
reports every gate score in the run summary. See
[running it remotely](ui/README.md#running-it-remotely).

### 4. Collect output

When complete, check `output/` for deliverables and `status.md` for the
full audit log of every gate, score, decision, and retry.

Stage 6 now also emits monetization artifacts by default:
- `channel-publish-manifest.json` (storefront-ready metadata + pricing anchors)
- `offer-stack.md` (tripwire/core/upsell packaging)
- `conversion-feedback-loop.md` (weekly optimization workflow)
- `growth-engine.md` (autonomous experiment plan)
- `metrics-template.csv` (analytics schema for regeneration loops)

---

## Project structure

```
factoreality/
├── orchestrator.py          # Entry point — runs the full pipeline
├── spec.md                  # Pipeline source of truth (manual or auto-generated)
├── implement.md             # Operating rules for all agents (read-only)
├── plan.md                  # Auto-generated pipeline plan (Gate 0)
├── status.md                # Running audit log
│
├── agents/
│   ├── base.py              # Shared harness task + file helpers
│   ├── planner.py           # Gate 0: generates plan.md
│   ├── specification.py     # Pre-stage: generates spec.md from a brief
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
│   ├── agentic_harness.py   # Local task executor; no outside LLM API
│   ├── fake_llm.py          # Backward-compatible alias to agentic_harness.py
│   ├── link_checker.py      # Validates URLs return HTTP 200
│   └── readability.py       # Flesch-Kincaid grade level scorer
│
├── templates/
│   ├── spec_template.md      # Blank spec to fill in manually
│   ├── brief_template.md     # Optional brief for auto-generated specs
│   └── product_profiles.json # Quality settings per product type
│
├── ui/                      # Web control room (stdlib only)
│   ├── server.py            # HTTP server: static assets + JSON API
│   ├── state.py             # Projects the file stack into dashboard state
│   ├── backends/            # Store / Runner protocols + local implementations
│   └── static/              # index.html + app.js + styles.css
│
├── .github/workflows/
│   ├── run-pipeline.yml     # Remote execution plane (workflow_dispatch)
│   └── tests.yml            # Test suite + end-to-end pipeline smoke test
│
├── .harness/                # Local agentic task ledger
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

## Harness-native execution model

The pipeline is designed to run inside an agentic harness, not by proxying work
to a hosted LLM API. Each stage still receives explicit role instructions, input
context, acceptance criteria, and retry feedback, but `BaseAgent.call_agent()`
records the task in `.harness/tasks.md` and resolves it through the local
`AgenticHarness`. The historical `call_llm()` method remains only as a backward-
compatible alias and does not make network calls.

| Component | Outside API cost | Execution path |
|-----------|------------------|----------------|
| Research | $0 | Local harness synthesis + deterministic gate checks |
| Outline | $0 | Local harness synthesis + deterministic gate checks |
| Content generation | $0 | Section-by-section local harness tasks |
| Editorial QA | $0 | Local harness editorial pass |
| Formatting | $0 | Local Markdown formatting; optional local Pandoc PDF export |
| QA Reviewer gates | $0 | Separate local reviewer task + deterministic checks |
| Retries | $0 | Harness reruns targeted local revision tasks |

---


## Revenue acceleration features (high impact)

1. **Built-in channel publishing + storefront sync**
   - One-click export + publish to Gumroad, Lemon Squeezy, Shopify Digital Downloads, and Notion marketplaces.
   - Add per-channel metadata templates (title, subtitle, thumbnail prompts, SEO description, pricing anchor copy).
   - Why this lifts revenue: distribution friction is usually the bottleneck; shipping directly to where buyers already are increases conversion velocity.

2. **Automated offer stack generator (tripwire → core → upsell)**
   - Generate not just one product, but a monetization ladder: lead magnet, low-ticket offer, core product, and optional order bump.
   - Auto-create matching checkout copy, email sequence drafts, and post-purchase upsell pages.
   - Why this lifts revenue: average order value (AOV) rises when each run outputs a complete funnel rather than a single SKU.

3. **Conversion feedback loop with performance-aware regeneration**
   - Ingest sales + funnel analytics (CTR, CVR, refund rate, EPC) from Stripe/Gumroad/email tools.
   - Feed winning hooks/headlines/modules back into future specs and revise weak assets automatically.
   - Why this lifts revenue: the system compounds winners over time, turning the pipeline into a learning engine rather than one-off content generation.

## Design

See the full architecture document: [The Content Factory v0.2](https://github.com/michaelcolenso/factoreality)

Key design decisions:

- **Separate QA Reviewer agent** — distinct harness task, distinct prompt, fresh
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
