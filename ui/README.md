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
├── state.py         # projects a Store into the dashboard payload
├── backends/
│   ├── base.py      # the Store / Runner protocols — the control/execution seam
│   └── local.py     # LocalStore (a directory) + LocalRunner (a subprocess)
└── static/
    ├── index.html
    ├── app.js       # vanilla JS: polling, rendering, mini markdown renderer
    └── styles.css   # dark-first, light via prefers-color-scheme, phone layout
```

The UI holds no state of its own. Everything it shows comes from the same files
the pipeline already writes (`status.json`, `status.md`, `qa-reviews/`, the
stage output directories), so the dashboard and the CLI can never disagree.

## Architecture: two planes, one seam

The control room does two jobs with very different requirements:

- **Control plane** — render gate scores, edit the spec, browse artifacts.
  Needs *data*.
- **Execution plane** — run `orchestrator.py`, write files. Needs a *POSIX box*.

Fusing them is what would pin the UI to one machine, so they are split behind
two protocols in `backends/base.py`:

| | `Store` | `Runner` |
|---|---|---|
| **Local** (today) | project directory | `subprocess` |
| **Repo-backed** | the git repo via the GitHub API | Actions `workflow_dispatch` |
| **Always-on box** | mounted volume | `subprocess` |

`ProjectState` never touches a filesystem — it reads through a `Store`. The
front end never learns which backend is in play, because the JSON API is shaped
like *pipeline state*, not like a filesystem. `build_server()` takes optional
`store=` / `runner=` arguments; pass them and the same dashboard serves a
project it has no local copy of. `StoreSeamTests` in `tests/test_ui.py` proves
this by rendering the whole dashboard from an in-memory dict.

The repo-backed row works because of a decision that predates the UI: the
pipeline keeps all state in files, and those files live in git. A repository is
a filesystem you can reach from a phone.

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

## Running it remotely

The dashboard is built for phones as well as desktops — full-width controls,
44px touch targets, a swipeable gate track. Three ways to actually reach it:

**1. Cloudflare Tunnel + Access — no code changes.** `cloudflared` makes an
outbound-only connection from your machine and publishes it on a hostname; an
Access policy restricted to your email is then the entire auth layer, which the
server itself does not provide. Do not publish it without one.

```bash
python ui/server.py --no-browser &
cloudflared tunnel --url http://127.0.0.1:8420
```

Caveat: it only serves while your machine is awake.

**2. GitHub Actions — the execution plane without a machine.** The
`Run pipeline` workflow (`.github/workflows/run-pipeline.yml`) takes a brief and
the same `--dry-run` / `--regenerate-spec` flags, and can be dispatched from the
GitHub mobile app. Gate scores land in the run summary as a table you can read
on a phone; deliverables upload as run artifacts, and `open_pr` commits the
product as a pull request. No servers, and the repo is the audit trail.

Costs to know: a run that takes 0.2s locally takes ~30s there (runner start-up
dominates), and the live console becomes "queued → running → logs," because
Actions exposes job logs through the API after the job finishes.

**3. An always-on box.** Fly.io with a volume, or any small VPS, running the
Python unchanged behind a tunnel. The file-stack model survives intact because
the disk persists.

Cloudflare Workers cannot host this directly — no subprocesses, no filesystem.
Cloudflare Containers give you a process, but [container disk is
ephemeral](https://developers.cloudflare.com/containers/faq/): every run's
output disappears when the instance sleeps. Going that route means writing a
`Store` that persists into R2 or Durable Object storage — which the seam above
makes possible, but which buys nothing over option 3.

## Tests

```bash
python -m unittest tests.test_ui
```

Covers the state projection, path sandboxing, subprocess lifecycle (including
concurrent-run rejection and reset scoping), and the HTTP API driven over a real
loopback socket through a full pipeline run.
