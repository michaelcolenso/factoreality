# Control room

A local web UI for the Content Factory pipeline. Stdlib only — no framework, no
build step, no packages to install, matching the pipeline's own zero-dependency
constraint.

```bash
python ui/server.py            # http://127.0.0.1:8420
```

| Flag | Effect |
|------|--------|
| `--port N` | Serve on a different port (default 8420) |
| `--host ADDR` | Bind address (default `127.0.0.1`) |
| `--project DIR` | Point at a project directory that holds `spec.md` (default: the repo root) |
| `--no-browser` | Do not open a browser on start |

## What the tabs do

**Pipeline** — the seven gates as a live track, each with its score against the
spec's threshold, attempt count, QA feedback, and the scoring rubric the gate
was judged on. `Run pipeline` shells out to `orchestrator.py` exactly as the CLI
does and streams its stdout into the console panel; `dry run` and `resume` map
to the matching CLI flags. On a halt, the reason from `status.md` is surfaced
under the console.

**Spec** — edit `spec.md` in place. Every keystroke is re-parsed through
`SpecParser` against a temp copy, so you see whether the pipeline can read your
spec before you save it. Saving an unparseable spec requires confirming. The
right pane shows exactly what the pipeline extracts: product type, constraints,
deliverables, and the done-when checklist.

**Brief** — write a `product-brief.md` and run brief-driven bootstrap
(`--brief-file`, plus `--regenerate-spec` when you tick the overwrite box).

**Artifacts** — everything the run produced: `output/`, `draft/`, `outline/`,
`research/`, `qa-reviews/`, `.harness/`, plus the root project files. Markdown
renders, other text previews raw, and anything binary (zips, PDFs) downloads.

`Reset` deletes the generated artifacts — `research/ outline/ draft/ editorial/
qa-reviews/ output/ .harness/ plan.md status.json` — and nothing else. It is
refused while a run is active.

## Layout

```
ui/
├── server.py        # stdlib HTTP server: static assets + JSON API
├── runner.py        # RunManager — owns the orchestrator subprocess, tails its output
├── state.py         # reads the project file stack into the dashboard payload
└── static/
    ├── index.html
    ├── app.js       # vanilla JS: polling, rendering, mini markdown renderer
    └── styles.css   # dark-first, light via prefers-color-scheme
```

The UI holds no state of its own. Everything it shows comes from the same files
the pipeline already writes (`status.json`, `status.md`, `qa-reviews/`, the
stage output directories), so the dashboard and the CLI can never disagree.

## API

| Method | Route | Purpose |
|--------|-------|---------|
| GET | `/api/state` | Stages, gate scores, spec summary, artifact listing, run snapshot |
| GET | `/api/log?since=N` | Incremental console tail |
| GET | `/api/spec` · `/api/brief` | Current file contents |
| GET | `/api/file?path=` | Text preview (sandboxed, 400 KB cap) |
| GET | `/api/download?path=` | File download (sandboxed) |
| POST | `/api/run` | `{dry_run, resume, brief, regenerate_spec}` |
| POST | `/api/stop` · `/api/reset` | Terminate a run · clear generated artifacts |
| POST | `/api/spec` · `/api/spec/validate` | Save (with `force` to override a parse failure) · check without saving |

File routes resolve inside the project directory only — `..` traversal,
absolute paths, symlink escapes, and `.git` are rejected.

## Security

The server binds to loopback and has no authentication, because it exposes
process execution and file writes. If you bind it elsewhere with `--host`, put
it behind a trusted network or an SSH tunnel — anyone who can reach the port can
start runs and rewrite `spec.md`.

## Tests

```bash
python -m unittest tests.test_ui
```

Covers the state projection, path sandboxing, subprocess lifecycle (including
concurrent-run rejection and reset scoping), and the HTTP API driven over a real
loopback socket through a full pipeline run.
