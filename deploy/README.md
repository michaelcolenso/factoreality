# Deploy

Everything needed to run the pipeline somewhere other than your own machine.

## Install the workflows (one command)

The two files in `workflows/` are ready to use but are **not active** — they
live here rather than in `.github/workflows/` because the credentials that
authored them could not write to that path. Move them into place and they take
effect on the next push:

```bash
mkdir -p .github/workflows
git mv deploy/workflows/*.yml .github/workflows/
git commit -m "Enable CI and the pipeline run workflow"
git push
```

(Pushing files under `.github/workflows/` requires a token with the `workflow`
scope. A normal `git push` from your own machine has it; some CI tokens and
OAuth apps do not.)

| Workflow | Trigger | What it does |
|---|---|---|
| `tests.yml` | every PR and push to `main` | Runs the test suite, then runs the pipeline end to end and asserts `output/manifest.json` exists |
| `run-pipeline.yml` | manual (`workflow_dispatch`) | Runs the pipeline from a brief, on a runner, with no machine of your own |

## Running the pipeline from a phone

Once `run-pipeline.yml` is installed, open the repo in the GitHub mobile app →
**Actions** → **Run pipeline** → **Run workflow**. You get four inputs:

- **brief** — a paragraph or two. Leave empty to run against the committed `spec.md`.
- **regenerate_spec** — overwrite `spec.md` from that brief.
- **dry_run** — validate the spec and plan without writing output.
- **open_pr** — commit the generated product as a pull request.

The run summary shows every gate with its score and attempt count, and the halt
reason if it stopped. Deliverables attach to the run as artifacts.

What to expect: a run that takes 0.2s locally takes ~30 seconds there, almost
all of it runner start-up. There is no live console — Actions exposes job logs
through the API once the job finishes.

## Serving the control room remotely

The dashboard itself needs a machine, because it starts processes and writes
files. See [running it remotely](../ui/README.md#running-it-remotely) for the
three options and their trade-offs. In short:

- **Cloudflare Tunnel + Access** — no code changes, works today, only while your
  machine is awake. **The Access policy is the only authentication** the control
  room has; never publish it on a hostname without one.
- **A small always-on box** (Fly.io with a volume, or a VPS) — the Python runs
  unchanged because the disk persists.
- **Cloudflare Workers** — cannot host this: no subprocesses, no filesystem.
  Containers give you a process but ephemeral disk, so every run's output
  disappears when the instance sleeps.
