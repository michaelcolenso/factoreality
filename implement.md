# Content Factory Runbook — Autonomous Mode

## Operating Rules

1. **spec.md is the source of truth for WHAT to build.**
   Never deviate from the spec. There is no human to ask.
   If the spec is ambiguous, choose the most conservative interpretation
   and log the decision in status.md.

2. **plan.md is the source of truth for HOW to build it.**
   Follow milestones in order. Do not skip ahead.

3. **Stop-and-fix rule.**
   If any verification step fails, fix the failure before proceeding.
   Do not accumulate errors across milestones.

4. **Scope discipline.**
   Do not add features, sections, bonuses, or content not specified.
   "Wouldn't it be cool if..." is scope creep. The spec defines the product.
   Add nothing. Remove nothing. Build what was asked for.

5. **Update status.md after every milestone.**
   Record: what was done, verification results, QA reviewer scores,
   decisions made, retries attempted.

6. **Preserve prior work.**
   When revising a section after a QA REVISE verdict, do not rewrite
   adjacent sections. Keep diffs scoped to exactly what the reviewer flagged.

7. **No placeholder content in outputs.**
   Every sentence, example, data point, and image must be real.
   If you cannot produce a required element, substitute with the
   best available alternative and flag it in status.md.
   Never insert "[INSERT EXAMPLE HERE]" or equivalent.

8. **Citation discipline.**
   Every statistic, quote, or factual claim must have a source.
   Prefer primary sources. If a claim cannot be verified,
   rewrite the passage to remove the unverifiable claim rather
   than leaving it in.

9. **Format for the medium.**
   Write for the final deliverable format, not for chat.

10. **Ambiguity resolution protocol.**
    When the spec doesn't cover a decision:
    - Choose the most conservative/conventional option
    - Log the decision and rationale in status.md
    - Continue (do not halt the pipeline for ambiguity)

11. **Retry budget.**
    Each gate allows up to N retry cycles (default 3, configurable in spec).
    If a gate fails after max retries, halt the pipeline and produce a
    diagnostic report in status.md explaining what failed and why.

## Stage Quick Reference

| Stage | Agent Role       | Input                              | Output                   |
|-------|------------------|------------------------------------|--------------------------|
| 0     | Orchestrator     | spec.md                            | plan.md                  |
| 1     | Research Analyst | spec.md                            | research/research-brief.md |
| 2     | Content Architect| spec.md + research-brief.md        | outline/outline.md       |
| 3     | Writer           | spec.md + outline.md + research    | draft/draft.md           |
| 4     | Editor           | spec.md + draft.md                 | draft/draft-edited.md    |
| 5     | Formatter        | spec.md + draft-edited.md          | Formatted files          |
| 6     | Packager         | All formatted deliverables         | output/ package          |

## QA Gate Verdicts

- **PASS**: Score ≥ spec quality_threshold → proceed to next stage
- **REVISE**: Score < threshold, retries remain → send specific feedback, retry stage
- **FAIL**: Score < threshold, no retries remain → halt pipeline, write diagnostic

## Automated Checks Reference

```bash
# Placeholder scan
grep -rni "TODO\|TBD\|INSERT\|PLACEHOLDER\|FIXME\|\[.*\]" draft/

# Word count
wc -w draft/draft.md

# Link check (requires link-checker utility)
python utils/link_checker.py research/research-brief.md

# Readability score
python utils/readability.py draft/draft-edited.md

# Spell check
aspell check draft/draft-edited.md
```
