# Products

Finished, shipped deliverables produced **with** the factoreality framework.

Unlike `output/` (the pipeline's ephemeral, git-ignored working directory), this
directory holds curated, version-controlled products ready to use or distribute.

## Contents

### `medical-bill-negotiation-kit/`
**The Medical Bill Negotiation & Dispute Kit** — a complete, ready-to-use
consumer self-advocacy system that helps U.S. patients audit, dispute, negotiate,
and reduce medical bills, access charity care, appeal insurance denials, and
defend their credit against medical collections.

- 7-module core guide (~9,100 words) + "Know Your Battlefield," costly-mistakes,
  special-situations, worked examples, FAQ, and glossary
- 9 templates/scripts (request letters, call scripts, appeal letters, settlement
  framework, validation/dispute letters, checklists)
- 2 bonus deep dives (insurance-appeal, collection-defense)
- Package README + `manifest.json` + downloadable `.zip`

Start with `medical-bill-negotiation-kit/README.md`.

> **How this was made:** the framework's bundled `utils/agentic_harness.py` is a
> deterministic *stub* — it emits placeholder prose and a QA reviewer hard-coded
> to `PASS`. Running `orchestrator.py` unmodified produces a product that passes
> every gate but contains no real value. This kit was produced by having a real
> intelligent agent act as the harness the pipeline was designed to plug into,
> following the same spec → plan → research → outline → draft → edit → format →
> package workflow the framework defines — but with genuine, useful content.

> **Disclaimer:** The kit is an educational self-advocacy resource — not legal,
> medical, tax, or financial advice, and no outcome is guaranteed. See the
> disclaimers within each file.
