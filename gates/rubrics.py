"""
QA gate scoring rubrics.

Each rubric is a list of dimension dicts:
  name     — display name
  weight   — contribution to composite score (weights sum to 1.0 per rubric)
  measures — human-readable description of what is being evaluated
  critical — if True, a score < 0.5 on this dimension triggers REVISE regardless of composite
"""

RUBRICS: dict[str, list[dict]] = {

    # Gate 0 — Plan validation
    "plan": [
        {
            "name": "Spec coverage",
            "weight": 0.35,
            "measures": "Plan covers every deliverable and constraint in spec.md",
            "critical": True,
        },
        {
            "name": "Word count consistency",
            "weight": 0.25,
            "measures": "Section word count allocations sum to spec total (±10%)",
            "critical": True,
        },
        {
            "name": "Verifiability",
            "weight": 0.25,
            "measures": "Every milestone has machine-verifiable acceptance criteria (counts, scans, scores)",
            "critical": False,
        },
        {
            "name": "Structural soundness",
            "weight": 0.15,
            "measures": "No milestone depends on a later milestone; stages are in correct order",
            "critical": False,
        },
    ],

    # Gate 1 — Research
    "research": [
        {
            "name": "Source coverage",
            "weight": 0.25,
            "measures": "≥10 sources, diverse types (articles, data, community posts)",
            "critical": True,
        },
        {
            "name": "Source quality",
            "weight": 0.25,
            "measures": "Primary sources preferred, recent (≤18 months), authoritative",
            "critical": False,
        },
        {
            "name": "Competitive depth",
            "weight": 0.20,
            "measures": "≥3 products analyzed with structure, pricing, and identified gaps",
            "critical": False,
        },
        {
            "name": "Audience validation",
            "weight": 0.20,
            "measures": "Pain points traced to real community evidence with citations",
            "critical": False,
        },
        {
            "name": "Citation integrity",
            "weight": 0.10,
            "measures": "All claims sourced, all links present (format is correct even if not live-checked)",
            "critical": False,
        },
    ],

    # Gate 2 — Outline
    "outline": [
        {
            "name": "Spec alignment",
            "weight": 0.30,
            "measures": "Section count, word count, deliverables all match spec constraints",
            "critical": True,
        },
        {
            "name": "Logical flow",
            "weight": 0.25,
            "measures": "No gaps, no redundancy, clear progression from section to section",
            "critical": False,
        },
        {
            "name": "Content specificity",
            "weight": 0.25,
            "measures": "Section summaries are concrete and specific, not vague ('explains the 3-step X framework', not 'overview of X')",
            "critical": False,
        },
        {
            "name": "Completeness",
            "weight": 0.20,
            "measures": "Every spec deliverable and requirement has a home in the outline",
            "critical": True,
        },
    ],

    # Gate 3 — Draft (content generation)
    "content": [
        {
            "name": "Spec adherence",
            "weight": 0.20,
            "measures": "Content matches outline structure and spec requirements exactly",
            "critical": True,
        },
        {
            "name": "Completeness",
            "weight": 0.20,
            "measures": "No placeholder text, all sections present at target length (±10%)",
            "critical": True,
        },
        {
            "name": "Accuracy",
            "weight": 0.20,
            "measures": "Claims are sourced, examples are concrete, no fabricated data",
            "critical": True,
        },
        {
            "name": "Voice consistency",
            "weight": 0.15,
            "measures": "Tone matches spec throughout, no register shifts",
            "critical": False,
        },
        {
            "name": "Readability",
            "weight": 0.15,
            "measures": "Grade level within 1 of target (estimated from sentence length and vocabulary)",
            "critical": False,
        },
        {
            "name": "Cross-reference integrity",
            "weight": 0.10,
            "measures": "Internal references resolve, no contradictions between sections",
            "critical": False,
        },
    ],

    # Gate 4 — Editorial
    "editorial": [
        {
            "name": "Grammar and spelling",
            "weight": 0.25,
            "measures": "Zero errors after automated check; no awkward constructions",
            "critical": False,
        },
        {
            "name": "Terminology consistency",
            "weight": 0.20,
            "measures": "Same terms used for same concepts throughout the document",
            "critical": False,
        },
        {
            "name": "Fact verification",
            "weight": 0.25,
            "measures": "All statistics checked, unverifiable claims removed rather than left in",
            "critical": True,
        },
        {
            "name": "Readability compliance",
            "weight": 0.15,
            "measures": "Score within 1 grade level of spec target",
            "critical": False,
        },
        {
            "name": "Flow and transitions",
            "weight": 0.15,
            "measures": "Smooth section transitions, no abrupt shifts in tone or topic",
            "critical": False,
        },
    ],

    # Gate 5 — Formatting
    "formatting": [
        {
            "name": "File integrity",
            "weight": 0.30,
            "measures": "Files can be parsed/opened without errors; no broken syntax",
            "critical": True,
        },
        {
            "name": "TOC accuracy",
            "weight": 0.20,
            "measures": "Table of contents entries match actual content headings",
            "critical": True,
        },
        {
            "name": "Visual consistency",
            "weight": 0.20,
            "measures": "Fonts, heading levels, list styles, and spacing consistent throughout",
            "critical": False,
        },
        {
            "name": "Brand compliance",
            "weight": 0.15,
            "measures": "Matches spec brand guidelines (colors, fonts) if specified",
            "critical": False,
        },
        {
            "name": "Print/display readiness",
            "weight": 0.15,
            "measures": "No orphaned headings, truncated content, or broken image references",
            "critical": False,
        },
    ],

    # Gate 6 — Final package
    "assembly": [
        {
            "name": "Completeness",
            "weight": 0.40,
            "measures": "Every deliverable listed in spec exists as a file and opens correctly",
            "critical": True,
        },
        {
            "name": "File integrity",
            "weight": 0.30,
            "measures": "All files render correctly; file sizes are non-zero and within expected range",
            "critical": True,
        },
        {
            "name": "Manifest accuracy",
            "weight": 0.20,
            "measures": "README / manifest lists every file with accurate descriptions",
            "critical": False,
        },
        {
            "name": "Naming convention",
            "weight": 0.10,
            "measures": "Files follow a consistent, human-readable naming pattern",
            "critical": False,
        },
    ],
}
