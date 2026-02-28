# Content Factory Plan — The IEP & 504 Parent Playbook

## Gate 0: Plan Validation
**Acceptance criteria:**
- [ ] Every deliverable in spec.md appears in this plan
- [ ] Word count allocations sum to 13,500 words (midpoint of 12,000–16,000 range)
- [ ] Section count is 9 (within 8–10 constraint)
- [ ] Every milestone has machine-verifiable acceptance criteria
- [ ] All six production stages are covered

**Deliverable map:**
| Spec Deliverable | Plan Coverage |
|------------------|---------------|
| Main ebook PDF (12,000–16,000 words) | Stages 1–5, all 9 chapters |
| Timeline cheat sheet PDF (1–2 pages) | Stage 5, supplementary output |
| Template pack, 5 email/meeting templates | Stage 5, supplementary output |

---

## Milestone 1: Research Complete (Stage 1)
**Output:** `research/research-brief.md`

**Acceptance criteria (machine-verifiable):**
- Source count ≥ 10 (grep `^\-.*\(http` | wc -l)
- Competitive analysis ≥ 3 entries (grep `^\|` in section 2 | wc -l ≥ 5)
- Pain points ≥ 5 with citations (grep `^>` in section 3 | wc -l ≥ 5)
- Key statistics ≥ 8 bullet points (count bullets in section 4)
- No placeholder URLs (grep `example\.com` returns 0)

**Content targets:**
- Federal law and regulatory sources (IDEA, Section 504, ADA)
- OSEP policy letters and Dear Colleague letters
- Wrightslaw, PACER, COPAA, NCLD as authoritative secondary sources
- Parent community language from Reddit r/specialed, IEP-focused Facebook groups
- Competitive pricing and format data for ≥ 3 comparable products

---

## Milestone 2: Outline Locked (Stage 2)
**Output:** `outline/outline.md`

**Acceptance criteria (machine-verifiable):**
- Section count = 9 (grep `^### ` | wc -l = 9)
- Word count allocations sum to 13,000–15,000 words (sum of allocation lines)
- Every section has Summary, Word Count Allocation, Key Points, Research Integration,
  Examples/Data fields
- No section title contains placeholder text

**Section structure (9 chapters):**
1. Introduction — Your Child Has Rights. Here's How to Use Them. (900 words)
2. IEP vs. 504: Which Plan Does Your Child Need? (1,200 words)
3. The Evaluation: How to Get Your Child Assessed (and What to Do If the School Says No) (1,500 words)
4. Reading the IEP: What Every Section Actually Means (1,800 words)
5. The IEP Meeting: How to Walk In Prepared and Walk Out With What You Need (2,000 words)
6. When the School Says No: How to Escalate Without Going to War (1,800 words)
7. 504 Plans: A Shorter Path to Classroom Accommodations (1,200 words)
8. Keeping Records, Writing Emails, and Creating a Paper Trail (1,100 words)
9. Next Steps and Resources: What to Do After You Finish This Book (1,000 words)
**Total: 12,500 words**

---

## Milestone 3: First Draft Complete (Stage 3)
**Output:** `draft/draft.md`

**Acceptance criteria (machine-verifiable):**
- Word count 12,000–16,000 (wc -w draft/draft.md)
- Placeholder scan = 0 hits (python utils/placeholder_scan.py draft/draft.md)
- Section count = 9 (grep `^## ` | wc -l = 9)
- Every section heading matches outline exactly

---

## Milestone 4: Editorial QA Complete (Stage 4)
**Output:** `draft/draft-edited.md`, `editorial/editorial-notes.md`

**Acceptance criteria (machine-verifiable):**
- Word count within ±5% of draft (wc -w comparison)
- Readability ≤ FK grade 9 (python utils/readability.py draft/draft-edited.md)
- Placeholder scan = 0 hits on edited draft
- No [VERIFY:] flags remaining unresolved in edited draft

---

## Milestone 5: Formatting Complete (Stage 5)
**Output:** `output/formatted.md`, `output/iep-timeline-cheatsheet.md`,
           `output/template-pack.md`

**Acceptance criteria (machine-verifiable):**
- YAML front matter parses without error (python -c "import yaml; yaml.safe_load(open('output/formatted.md').read().split('---')[1])")
- Table of contents entries match actual H2 headings (diff TOC vs grep `^## `)
- Supplementary files exist and have content (wc -w output/iep-timeline-cheatsheet.md ≥ 200)
- Template pack contains exactly 5 templates (grep `^## Template` | wc -l = 5)

---

## Milestone 6: Package Assembled (Stage 6)
**Output:** `output/README.md`, `output/manifest.json`

**Acceptance criteria (machine-verifiable):**
- output/README.md exists and lists all three deliverable types
- output/manifest.json is valid JSON (python -c "import json; json.load(open('output/manifest.json'))")
- All three spec deliverables present in output/ (ls output/ | grep -E 'formatted|cheatsheet|template')
- manifest.json file list matches files in output/

---

## Stage Summary

| Stage | Agent | Input | Output | Gate |
|-------|-------|-------|--------|------|
| 0 | Planner | spec.md | plan.md | validate plan covers spec |
| 1 | Research | spec.md | research/research-brief.md | ≥10 sources, ≥5 pain points |
| 2 | Outline | spec.md + research | outline/outline.md | 9 sections, word counts sum |
| 3 | Content | spec.md + outline + research | draft/draft.md | 12k–16k words, no placeholders |
| 4 | Editorial | spec.md + draft | draft-edited.md + notes | readability ≤ grade 9 |
| 5 | Formatter | spec.md + edited draft | output/formatted.md + supplements | YAML valid, TOC matches |
| 6 | Assembler | all output files | README.md + manifest.json | all deliverables present |
