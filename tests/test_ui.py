"""Tests for the control-room UI: state projection, sandboxing, and the API."""

import json
import shutil
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from ui.backends import FileMeta, LocalRunner, LocalStore, Runner, Store, StoreError
from ui.server import build_server
from ui.state import ProjectState

REPO_ROOT = Path(__file__).resolve().parent.parent


def make_project(tmp: str) -> Path:
    """A minimal project dir: real spec + the code the orchestrator imports."""
    project_dir = Path(tmp) / "project"
    project_dir.mkdir()
    for name in ("agents", "gates", "utils", "templates"):
        shutil.copytree(REPO_ROOT / name, project_dir / name)
    for name in ("orchestrator.py", "spec.md", "implement.md"):
        shutil.copy(REPO_ROOT / name, project_dir / name)
    return project_dir


class ProjectStateTests(unittest.TestCase):
    def test_stages_default_to_pending_without_a_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = ProjectState(LocalStore(make_project(tmp)))
            stages = state.stages()
            self.assertEqual(len(stages), 7)
            self.assertEqual([s["gate"] for s in stages], [0, 1, 2, 3, 4, 5, 6])
            self.assertTrue(all(s["status"] == "pending" for s in stages))
            self.assertTrue(all(s["rubric"] for s in stages))

    def test_stage_state_is_read_from_status_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = make_project(tmp)
            (project_dir / "status.json").write_text(
                json.dumps({
                    "pipeline_status": "halted",
                    "halt_reason": "gate-3 FAILED",
                    "stages": {
                        "plan": {"status": "passed", "score": 0.95, "attempt": 1},
                        "content": {"status": "failed", "score": 0.4, "feedback": "placeholders"},
                    },
                }),
                encoding="utf-8",
            )
            payload = ProjectState(LocalStore(project_dir)).payload()
            by_key = {stage["key"]: stage for stage in payload["stages"]}

            self.assertEqual(payload["pipeline"]["status"], "halted")
            self.assertEqual(payload["pipeline"]["halt_reason"], "gate-3 FAILED")
            self.assertEqual(by_key["plan"]["score"], 0.95)
            self.assertEqual(by_key["content"]["status"], "failed")
            self.assertEqual(by_key["content"]["feedback"], "placeholders")
            self.assertEqual(by_key["research"]["status"], "pending")

    def test_threshold_comes_from_the_spec(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = make_project(tmp)
            # The bundled spec.md pins 0.9.
            self.assertEqual(ProjectState(LocalStore(project_dir)).stages()[0]["threshold"], 0.9)

    def test_spec_summary_reports_parse_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = make_project(tmp)
            (project_dir / "spec.md").write_text("# Nothing useful\n", encoding="utf-8")
            summary = ProjectState(LocalStore(project_dir)).spec_summary()
            self.assertFalse(summary["valid"])
            self.assertIn("missing required fields", summary["error"])

    def test_validate_spec_text_does_not_touch_disk(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = make_project(tmp)
            original = (project_dir / "spec.md").read_text(encoding="utf-8")
            state = ProjectState(LocalStore(project_dir))

            self.assertFalse(state.validate_spec_text("## Nope\n")["valid"])
            good = state.validate_spec_text("## Product Type\nebook\n\n## Topic & Angle\nX\n")
            self.assertTrue(good["valid"])
            self.assertEqual(good["product_type"], "ebook")
            self.assertEqual((project_dir / "spec.md").read_text(encoding="utf-8"), original)

    def test_resolve_rejects_traversal_and_git(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = make_project(tmp)
            (project_dir / ".git").mkdir()
            (project_dir / ".git" / "config").write_text("secret", encoding="utf-8")
            store = LocalStore(project_dir)

            self.assertTrue(str(store.resolve("spec.md")).endswith("spec.md"))
            for bad in ("../../etc/passwd", "/etc/passwd", ".git/config", "", "missing.md"):
                with self.assertRaises(StoreError):
                    store.resolve(bad)

    def test_write_outside_the_project_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalStore(make_project(tmp))
            with self.assertRaises(StoreError):
                store.write_text("../escaped.md", "nope")
            self.assertFalse((Path(tmp) / "escaped.md").exists())


class StoreSeamTests(unittest.TestCase):
    """ProjectState must work against any Store — not just a directory.

    This is the contract that lets the control plane run somewhere other than
    the machine holding the files (e.g. reading a project out of a git repo).
    """

    def test_dashboard_renders_from_an_in_memory_store(self) -> None:
        state = ProjectState(MemoryStore({
            "spec.md": "## Product Type\nebook\n\n## Topic & Angle\nSourdough for beginners\n",
            "status.json": json.dumps({
                "pipeline_status": "running",
                "stages": {"plan": {"status": "passed", "score": 0.91, "attempt": 2}},
            }),
            "qa-reviews/gate-0-review.md": "# Gate 0\n**Verdict:** PASS\n",
            "qa-reviews/gate-0-review-attempt-1.md": "# Gate 0\n**Verdict:** REVISE\n",
            "output/manifest.json": "{}",
        }))

        payload = state.payload()
        by_key = {stage["key"]: stage for stage in payload["stages"]}

        self.assertEqual(payload["pipeline"]["status"], "running")
        self.assertEqual(payload["spec"]["product_type"], "ebook")
        self.assertEqual(by_key["plan"]["score"], 0.91)
        self.assertEqual(by_key["research"]["status"], "pending")

        # Reviews are discovered through the store's walk(), and ordered.
        self.assertEqual([r["attempt"] for r in by_key["plan"]["reviews"]], [0, 1])

        groups = {group["name"]: group for group in payload["artifacts"]}
        self.assertIn("output", groups)
        self.assertEqual(groups["output"]["files"][0]["name"], "manifest.json")
        self.assertTrue(groups["output"]["files"][0]["previewable"])

    def test_missing_spec_is_reported_not_raised(self) -> None:
        payload = ProjectState(MemoryStore({})).payload()
        self.assertFalse(payload["spec"]["valid"])
        self.assertEqual(payload["pipeline"]["status"], "idle")
        self.assertEqual(payload["artifacts"], [])

    def test_local_backend_satisfies_the_protocols(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = make_project(tmp)
            self.assertIsInstance(LocalStore(project_dir), Store)
            self.assertIsInstance(LocalRunner(project_dir, project_dir), Runner)
            self.assertIsInstance(MemoryStore({}), Store)

    def test_server_accepts_an_injected_backend(self) -> None:
        """build_server must not hard-code the local backend."""
        store = MemoryStore({"spec.md": "## Product Type\nebook\n\n## Topic & Angle\nX\n"})
        server = build_server("127.0.0.1", 0, Path("/nonexistent"), store=store)
        try:
            base = f"http://127.0.0.1:{server.server_address[1]}"
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            with urllib.request.urlopen(f"{base}/api/state", timeout=10) as response:
                payload = json.loads(response.read().decode("utf-8"))
            self.assertEqual(payload["project_dir"], "memory://test")
            self.assertEqual(payload["spec"]["product_type"], "ebook")
        finally:
            server.shutdown()
            server.server_close()


class MemoryStore:
    """A Store with no filesystem behind it, used to prove the seam holds."""

    def __init__(self, files: dict[str, str]) -> None:
        self.files = files

    @property
    def label(self) -> str:
        return "memory://test"

    def exists(self, path: str) -> bool:
        return path in self.files

    def read_text(self, path: str) -> str:
        if path not in self.files:
            raise StoreError(f"Not a file: {path}")
        return self.files[path]

    def read_bytes(self, path: str) -> bytes:
        return self.read_text(path).encode("utf-8")

    def write_text(self, path: str, content: str) -> None:
        self.files[path] = content

    def stat(self, path: str):
        if path not in self.files:
            return None
        return FileMeta(
            path=path,
            name=path.rsplit("/", 1)[-1],
            size=len(self.files[path].encode("utf-8")),
            modified="2026-01-01T00:00:00Z",
        )

    def walk(self, prefix: str):
        return [self.stat(path) for path in sorted(self.files) if path.startswith(f"{prefix}/")]


class LocalRunnerTests(unittest.TestCase):
    def test_full_run_completes_and_streams_log(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = make_project(tmp)
            runner = LocalRunner(project_dir, project_dir)
            runner.start()
            self._wait_for_exit(runner)

            snapshot = runner.snapshot()
            self.assertEqual(snapshot["exit_code"], 0)
            self.assertFalse(snapshot["active"])
            self.assertEqual(snapshot["mode"], "full run")

            log = runner.log_since(0)
            self.assertGreater(log["cursor"], 0)
            text = "\n".join(line["text"] for line in log["lines"])
            self.assertIn("pipeline complete", text)
            self.assertTrue((project_dir / "output" / "manifest.json").exists())

            # Incremental tailing returns only what is new.
            self.assertEqual(runner.log_since(log["cursor"])["lines"], [])

    def test_second_run_is_rejected_while_one_is_active(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = make_project(tmp)
            runner = LocalRunner(project_dir, project_dir)
            runner.start()
            try:
                runner.start()
            except Exception as exc:
                self.assertIn("already in progress", str(exc))
            self._wait_for_exit(runner)

    def test_regenerate_spec_without_a_brief_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = make_project(tmp)
            runner = LocalRunner(project_dir, project_dir)
            with self.assertRaises(ValueError):
                runner.start(regenerate_spec=True)
            self.assertFalse(runner.snapshot()["active"])

    def test_brief_is_written_and_passed_to_the_orchestrator(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = make_project(tmp)
            runner = LocalRunner(project_dir, project_dir)
            run = runner.start(brief="A guide to composting in small apartments.", dry_run=True)
            self._wait_for_exit(runner)

            brief_path = project_dir / "product-brief.md"
            self.assertTrue(brief_path.exists())
            self.assertIn("composting", brief_path.read_text(encoding="utf-8"))
            self.assertIn("--brief-file", run["argv"])
            self.assertEqual(run["mode"], "dry run + brief-driven")

    def test_reset_removes_only_generated_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = make_project(tmp)
            runner = LocalRunner(project_dir, project_dir)
            runner.start()
            self._wait_for_exit(runner)

            self.assertTrue((project_dir / "output").exists())
            removed = runner.reset()

            self.assertIn("output/", removed)
            self.assertIn("status.json", removed)
            for name in ("research", "outline", "draft", "qa-reviews", "output"):
                self.assertFalse((project_dir / name).exists(), name)
            self.assertTrue((project_dir / "spec.md").exists())
            self.assertTrue((project_dir / "orchestrator.py").exists())

    @staticmethod
    def _wait_for_exit(runner: LocalRunner, timeout: float = 60.0) -> None:
        import time

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if not runner.snapshot()["active"]:
                return
            time.sleep(0.05)
        raise AssertionError("Run did not finish within the timeout.")


class ApiTests(unittest.TestCase):
    """Drives the real HTTP server over a loopback socket."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.project_dir = make_project(self._tmp.name)
        self.server = build_server("127.0.0.1", 0, self.project_dir)
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self._tmp.cleanup()

    def get(self, path: str) -> dict:
        with urllib.request.urlopen(f"{self.base}{path}", timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))

    def post(self, path: str, body: dict) -> dict:
        request = urllib.request.Request(
            f"{self.base}{path}",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))

    def test_index_and_assets_are_served(self) -> None:
        for path, needle in (("/", b"factoreality"), ("/app.js", b"renderMarkdown"), ("/styles.css", b"--accent")):
            with urllib.request.urlopen(f"{self.base}{path}", timeout=10) as response:
                self.assertEqual(response.status, 200)
                self.assertIn(needle, response.read())

    def test_static_traversal_is_blocked(self) -> None:
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(f"{self.base}/../server.py", timeout=10)
        self.assertEqual(ctx.exception.code, 404)

    def test_state_endpoint_shape(self) -> None:
        payload = self.get("/api/state")
        self.assertEqual(len(payload["stages"]), 7)
        self.assertFalse(payload["run"]["active"])
        self.assertTrue(payload["spec"]["valid"])
        self.assertEqual(payload["spec"]["product_type"], "resource-guide")
        self.assertEqual(payload["project_dir"], str(self.project_dir))

    def test_spec_round_trip_rejects_unparseable_content(self) -> None:
        original = self.get("/api/spec")["content"]
        self.assertIn("## Product Type", original)

        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.post("/api/spec", {"content": "# broken\n"})
        self.assertEqual(ctx.exception.code, 422)
        self.assertEqual(self.get("/api/spec")["content"], original)

        edited = original.replace("resource-guide", "ebook", 1)
        self.assertTrue(self.post("/api/spec", {"content": edited})["saved"])
        self.assertEqual(self.get("/api/state")["spec"]["product_type"], "ebook")

    def test_force_saves_an_unparseable_spec(self) -> None:
        result = self.post("/api/spec", {"content": "# broken\n", "force": True})
        self.assertTrue(result["saved"])
        self.assertFalse(self.get("/api/state")["spec"]["valid"])

    def test_file_endpoint_is_sandboxed(self) -> None:
        self.assertIn("Content Factory Spec", self.get("/api/file?path=spec.md")["content"])
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.get("/api/file?path=../../etc/passwd")
        self.assertEqual(ctx.exception.code, 400)

    def test_run_then_inspect_artifacts_and_log(self) -> None:
        self.post("/api/run", {})
        LocalRunnerTests._wait_for_exit(self.server.RequestHandlerClass.runner)

        state = self.get("/api/state")
        self.assertEqual(state["pipeline"]["status"], "completed")
        self.assertTrue(all(stage["status"] == "passed" for stage in state["stages"]))
        self.assertTrue(all(stage["score"] for stage in state["stages"]))

        groups = {group["name"]: group for group in state["artifacts"]}
        self.assertIn("output", groups)
        self.assertIn("qa-reviews", groups)
        self.assertTrue(any(f["name"] == "manifest.json" for f in groups["output"]["files"]))

        log = self.get("/api/log?since=0")
        self.assertTrue(log["lines"])
        self.assertFalse(log["run"]["active"])

        review = self.get("/api/file?path=qa-reviews/gate-6-review.md")
        self.assertIn("Verdict", review["content"])

    def test_concurrent_run_returns_409(self) -> None:
        self.post("/api/run", {})
        try:
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                self.post("/api/run", {})
            self.assertEqual(ctx.exception.code, 409)
        finally:
            LocalRunnerTests._wait_for_exit(self.server.RequestHandlerClass.runner)

    def test_unknown_endpoint_is_404(self) -> None:
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.get("/api/nope")
        self.assertEqual(ctx.exception.code, 404)


if __name__ == "__main__":
    unittest.main()
