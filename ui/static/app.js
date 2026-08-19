/* factoreality control room — vanilla JS, no build step. */

const $ = (sel) => document.querySelector(sel);
const el = (tag, className, text) => {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
};

const app = {
  state: null,
  cursor: 0,
  logLines: [],
  openStages: new Set(["plan"]),
  selectedFile: null,
  specOnDisk: "",
  pollTimer: null,
};

/* ── API ───────────────────────────────────────────────────────── */

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.error || `${response.status} ${response.statusText}`);
  return body;
}

function toast(message, kind = "") {
  const node = $("#toast");
  node.textContent = message;
  node.className = `toast ${kind}`;
  node.hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => { node.hidden = true; }, 4000);
}

/* ── Polling ───────────────────────────────────────────────────── */

async function refresh() {
  try {
    const [state, log] = await Promise.all([
      api("/api/state"),
      api(`/api/log?since=${app.cursor}`),
    ]);
    app.state = state;
    if (log.lines.length) {
      app.logLines.push(...log.lines);
      app.cursor = log.cursor;
      renderConsole();
    } else if (log.cursor < app.cursor) {
      // Buffer was cleared (new run or reset) — resync from the start.
      app.cursor = 0;
      app.logLines = [];
      renderConsole();
    }
    render();
  } catch (error) {
    setPill("offline", "server unreachable");
  } finally {
    schedule();
  }
}

function schedule() {
  clearTimeout(app.pollTimer);
  const active = app.state?.run?.active;
  app.pollTimer = setTimeout(refresh, active ? 500 : 2500);
}

/* ── Header ────────────────────────────────────────────────────── */

function setPill(status, meta) {
  const pill = $("#pipeline-pill");
  pill.dataset.status = status;
  pill.textContent = status;
  $("#run-meta").textContent = meta || "";
}

function renderHeader() {
  const { pipeline, run, project_dir } = app.state;
  $("#project-path").textContent = project_dir;

  const status = run.active ? "running" : pipeline.status || "idle";
  const bits = [];
  if (run.mode) bits.push(run.mode);
  if (run.active) bits.push(`pid ${run.pid}`);
  else if (run.finished_at) bits.push(`exit ${run.exit_code} · ${run.finished_at}`);
  else if (pipeline.finished_at) bits.push(pipeline.finished_at);
  setPill(status, bits.join("  ·  "));

  $("#btn-run").disabled = run.active;
  $("#btn-stop").disabled = !run.active;
  $("#btn-reset").disabled = run.active;
  $("#btn-brief-run").disabled = run.active;
}

/* ── Pipeline view ─────────────────────────────────────────────── */

function render() {
  renderHeader();
  renderTrack();
  renderStages();
  renderHalt();
  renderSpecSummary();
  renderTree();
}

function renderTrack() {
  const nodes = app.state.stages.map((stage) => {
    const node = el("div", "node");
    node.dataset.status = stage.status;
    node.append(
      el("div", "gate", `GATE ${stage.gate}`),
      el("div", "label", stage.label),
      el("div", "score", formatScore(stage)),
    );
    node.onclick = () => {
      app.openStages.add(stage.key);
      renderStages();
      $(`#stage-${stage.key}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
    };
    return node;
  });
  $("#track").replaceChildren(...nodes);
}

function formatScore(stage) {
  if (stage.score === null || stage.score === undefined) {
    return stage.status === "running" ? "scoring…" : "—";
  }
  const attempts = stage.attempt && stage.attempt > 1 ? ` ×${stage.attempt}` : "";
  return `${Number(stage.score).toFixed(2)}${attempts}`;
}

function renderStages() {
  const threshold = app.state.stages[0]?.threshold ?? 0.8;
  $("#threshold-hint").textContent = `pass ≥ ${threshold.toFixed(2)}`;

  const list = $("#stage-list");
  list.replaceChildren();
  for (const stage of app.state.stages) {
    list.appendChild(renderStage(stage, threshold));
  }
}

function renderStage(stage, threshold) {
  const wrap = el("div", "stage");
  wrap.id = `stage-${stage.key}`;
  wrap.dataset.status = stage.status;

  const open = app.openStages.has(stage.key);
  const head = el("button", "stage-head");
  head.append(
    el("span", "caret", open ? "▾" : "▸"),
    el("span", "name", `${stage.gate}. ${stage.label}`),
    el("span", "purpose", stage.purpose),
    el("span", "status", stage.status),
  );
  head.onclick = () => {
    app.openStages.has(stage.key) ? app.openStages.delete(stage.key) : app.openStages.add(stage.key);
    renderStages();
  };

  const body = el("div", "stage-body");
  body.hidden = !open;

  if (stage.score !== null && stage.score !== undefined) {
    const meter = el("div", "meter");
    const fill = el("i");
    fill.style.width = `${Math.min(1, Math.max(0, stage.score)) * 100}%`;
    const marker = el("b");
    marker.style.left = `${threshold * 100}%`;
    marker.title = `threshold ${threshold}`;
    meter.append(fill, marker);

    const caption = el("div", "meter-caption");
    caption.append(
      el("span", null, `score ${Number(stage.score).toFixed(2)}`),
      el("span", null, `threshold ${threshold.toFixed(2)}`),
    );
    body.append(meter, caption);
  }

  const facts = el("dl", "kv");
  const addFact = (key, value) => {
    if (!value) return;
    facts.append(el("dt", null, key), el("dd", null, value));
  };
  addFact("attempts", stage.attempt ? String(stage.attempt) : "");
  addFact("started", stage.started_at);
  addFact("completed", stage.completed_at);
  addFact("output", stage.output_path);
  if (facts.children.length) body.append(facts);

  if (stage.feedback || stage.error) {
    body.append(el("div", "feedback", stage.error || stage.feedback));
  }

  const links = el("div", "links");
  if (stage.output_path) links.append(fileChip(`open ${stage.output_path}`, stage.output_path));
  for (const review of stage.reviews) {
    links.append(fileChip(review.attempt ? `review · attempt ${review.attempt}` : "QA review", review.path));
  }
  if (links.children.length) body.append(links);

  if (stage.rubric.length) {
    const rubric = el("div", "rubric");
    rubric.append(el("h4", null, "Gate rubric"));
    for (const dim of stage.rubric) {
      const row = el("div", "dim-row");
      row.append(
        el("span", "w", dim.weight.toFixed(2)),
        el("span", null, dim.name),
        el("span", "m", dim.measures),
      );
      if (dim.critical) row.append(el("span", "crit", "CRITICAL"));
      rubric.append(row);
    }
    body.append(rubric);
  }

  wrap.append(head, body);
  return wrap;
}

function fileChip(label, path) {
  const chip = el("button", "chip", label);
  chip.onclick = () => openFile(path);
  return chip;
}

function renderConsole() {
  const box = $("#console");
  const atBottom = box.scrollHeight - box.scrollTop - box.clientHeight < 40;

  if (!app.logLines.length) {
    box.replaceChildren(el("span", "dim", "No run yet. Hit “Run pipeline”."));
    return;
  }

  box.replaceChildren(...app.logLines.map((line) => {
    let cls = "";
    if (line.stream === "system") cls = "sys";
    if (/PASSED|COMPLETE|✓/.test(line.text)) cls = "ok";
    if (/FAILED|HALTED|Error|✗|Traceback/.test(line.text)) cls = "bad";
    const row = el("div", cls);
    row.textContent = line.text || " ";
    return row;
  }));

  if ($("#opt-follow").checked && atBottom) box.scrollTop = box.scrollHeight;
}

function renderHalt() {
  const box = $("#halt-box");
  const reason = app.state.pipeline.halt_reason;
  const halted = app.state.pipeline.status === "halted" && reason && !app.state.run.active;
  box.hidden = !halted;
  if (halted) box.textContent = `PIPELINE HALTED\n\n${reason}`;
}

/* ── Spec view ─────────────────────────────────────────────────── */

async function loadSpec() {
  const { content } = await api("/api/spec");
  app.specOnDisk = content;
  $("#spec-editor").value = content;
  validateSpec();
}

let validateTimer;
function scheduleValidate() {
  clearTimeout(validateTimer);
  validateTimer = setTimeout(validateSpec, 400);
}

async function validateSpec() {
  const content = $("#spec-editor").value;
  const label = $("#spec-validity");
  if (!content.trim()) {
    label.className = "validity bad";
    label.textContent = "empty";
    return;
  }
  try {
    const result = await api("/api/spec/validate", {
      method: "POST",
      body: JSON.stringify({ content }),
    });
    const dirty = content !== app.specOnDisk ? " · unsaved" : "";
    label.className = `validity ${result.valid ? "ok" : "bad"}`;
    label.textContent = result.valid
      ? `parses · ${result.product_type} · ${result.deliverables} deliverables${dirty}`
      : `${result.error}${dirty}`;
  } catch (error) {
    label.className = "validity bad";
    label.textContent = error.message;
  }
}

async function saveSpec() {
  const content = $("#spec-editor").value;
  try {
    await api("/api/spec", { method: "POST", body: JSON.stringify({ content }) });
    app.specOnDisk = content;
    toast("spec.md saved", "ok");
    validateSpec();
    refresh();
  } catch (error) {
    if (confirm(`spec.md will not parse:\n\n${error.message}\n\nSave it anyway?`)) {
      await api("/api/spec", { method: "POST", body: JSON.stringify({ content, force: true }) });
      app.specOnDisk = content;
      toast("Saved with parse errors", "bad");
      validateSpec();
    }
  }
}

function renderSpecSummary() {
  const spec = app.state.spec;
  const box = $("#spec-summary");
  box.replaceChildren();

  if (!spec.valid) {
    box.append(el("p", "dim", spec.error || "spec.md does not parse yet."));
    return;
  }

  const block = (title, child) => {
    const section = el("div", "summary-block");
    section.append(el("h3", null, title), child);
    box.append(section);
  };

  block("Product type", el("p", null, spec.product_type || "—"));
  block("Topic & angle", el("p", null, spec.topic_angle || "—"));

  const badges = el("div", "badges");
  const push = (text) => text && badges.append(el("span", "badge", text));
  push(`gate ≥ ${spec.min_gate_confidence}`);
  push(`${spec.max_retry_cycles} retries`);
  if (spec.word_range) push(`${spec.word_range[0].toLocaleString()}–${spec.word_range[1].toLocaleString()} words`);
  if (spec.section_range) push(`${spec.section_range[0]}–${spec.section_range[1]} sections`);
  if (spec.readability_target) push(spec.readability_target);
  for (const format of spec.formats || []) push(format);
  block("Constraints", badges);

  if (spec.deliverables.length) {
    const list = el("ol");
    for (const item of spec.deliverables) list.append(el("li", null, item));
    block(`Deliverables (${spec.deliverables.length})`, list);
  }
  if (spec.done_when.length) {
    const list = el("ul");
    for (const item of spec.done_when) list.append(el("li", null, item));
    block("Done when", list);
  }
}

/* ── Artifacts view ────────────────────────────────────────────── */

function renderTree() {
  const filter = $("#artifact-filter").value.trim().toLowerCase();
  const tree = $("#file-tree");
  tree.replaceChildren();

  let shown = 0;
  for (const group of app.state.artifacts) {
    const files = group.files.filter((file) => !filter || file.path.toLowerCase().includes(filter));
    if (!files.length) continue;
    shown += files.length;

    const section = el("div", "tree-group");
    section.append(el("h3", null, `${group.name}/  (${files.length})`));
    for (const file of files) {
      const item = el("button", "tree-item");
      if (file.path === app.selectedFile) item.classList.add("selected");
      item.append(
        el("span", "fname", file.path.replace(`${group.name}/`, "")),
        el("span", "fsize", humanSize(file.size)),
      );
      item.onclick = () => openFile(file.path);
      section.append(item);
    }
    tree.append(section);
  }

  if (!shown) {
    tree.append(el("p", "dim", filter ? "No files match that filter." : "No artifacts yet — run the pipeline."));
  }
}

function humanSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

async function openFile(path) {
  showView("artifacts");
  app.selectedFile = path;
  renderTree();

  $("#preview-title").textContent = path;
  const download = $("#btn-download");
  download.href = `/api/download?path=${encodeURIComponent(path)}`;
  download.hidden = false;

  const preview = $("#preview");
  const previewable = /\.(md|txt|json|csv|ya?ml|py|html|css|js)$/i.test(path);
  if (!previewable) {
    preview.replaceChildren(el("p", "dim", "Binary file — use Download to open it."));
    return;
  }

  preview.replaceChildren(el("p", "dim", "Loading…"));
  try {
    const file = await api(`/api/file?path=${encodeURIComponent(path)}`);
    const raw = $("#opt-raw").checked || !path.toLowerCase().endsWith(".md");
    preview.classList.toggle("raw", raw);
    if (raw) {
      const pre = el("pre");
      pre.append(el("code", null, file.content));
      preview.replaceChildren(pre);
    } else {
      preview.innerHTML = renderMarkdown(file.content);
    }
    if (file.truncated) {
      preview.prepend(el("p", "dim", `Showing the first ${humanSize(file.content.length)} of ${humanSize(file.size)}.`));
    }
    preview.scrollTop = 0;
  } catch (error) {
    preview.replaceChildren(el("p", "dim", error.message));
  }
}

/* ── Minimal markdown renderer (escape first, then inline) ──────── */

function escapeHtml(text) {
  return text.replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[char]);
}

function inline(text) {
  return text
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/(^|[^*])\*([^*\n]+)\*/g, "$1<em>$2</em>")
    .replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
}

function renderMarkdown(source) {
  const lines = escapeHtml(source).split("\n");
  const out = [];
  let listType = null;
  let inCode = false;
  let inTable = false;
  let start = 0;

  // Pandoc-style YAML front matter — show it as metadata, not as a rule.
  if (lines[0] === "---") {
    const end = lines.indexOf("---", 1);
    if (end > 0) {
      out.push(`<pre class="frontmatter"><code>${lines.slice(1, end).join("\n")}</code></pre>`);
      start = end + 1;
    }
  }
  if (start) lines.splice(0, start);

  const closeList = () => { if (listType) { out.push(`</${listType}>`); listType = null; } };
  const closeTable = () => { if (inTable) { out.push("</tbody></table>"); inTable = false; } };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    if (/^\s*```/.test(line)) {
      closeList(); closeTable();
      out.push(inCode ? "</code></pre>" : "<pre><code>");
      inCode = !inCode;
      continue;
    }
    if (inCode) { out.push(line + "\n"); continue; }

    const heading = line.match(/^(#{1,6})\s+(.*)$/);
    if (heading) {
      closeList(); closeTable();
      const level = Math.min(heading[1].length, 4);
      out.push(`<h${level}>${inline(heading[2])}</h${level}>`);
      continue;
    }

    if (/^\s*(---|\*\*\*|___)\s*$/.test(line)) {
      closeList(); closeTable();
      out.push("<hr>");
      continue;
    }

    // Table: a header row followed by a separator row.
    if (/^\s*\|.*\|\s*$/.test(line) && /^\s*\|[\s:|-]+\|\s*$/.test(lines[i + 1] || "")) {
      closeList();
      const cells = splitRow(line).map((c) => `<th>${inline(c)}</th>`).join("");
      out.push(`<table><thead><tr>${cells}</tr></thead><tbody>`);
      inTable = true;
      i++;
      continue;
    }
    if (inTable) {
      if (/^\s*\|.*\|\s*$/.test(line)) {
        out.push(`<tr>${splitRow(line).map((c) => `<td>${inline(c)}</td>`).join("")}</tr>`);
        continue;
      }
      closeTable();
    }

    const bullet = line.match(/^\s*[-*+]\s+(.*)$/);
    const numbered = line.match(/^\s*\d+[.)]\s+(.*)$/);
    if (bullet || numbered) {
      const wanted = bullet ? "ul" : "ol";
      if (listType !== wanted) { closeList(); out.push(`<${wanted}>`); listType = wanted; }
      out.push(`<li>${inline((bullet || numbered)[1])}</li>`);
      continue;
    }
    closeList();

    const quote = line.match(/^\s*>\s?(.*)$/);
    if (quote) { out.push(`<blockquote>${inline(quote[1])}</blockquote>`); continue; }

    if (line.trim()) out.push(`<p>${inline(line)}</p>`);
  }

  closeList();
  closeTable();
  if (inCode) out.push("</code></pre>");
  return out.join("\n");
}

function splitRow(line) {
  return line.trim().replace(/^\||\|$/g, "").split("|").map((cell) => cell.trim());
}

/* ── Run controls ──────────────────────────────────────────────── */

async function startRun(extra = {}) {
  try {
    await api("/api/run", {
      method: "POST",
      body: JSON.stringify({
        dry_run: $("#opt-dry").checked,
        resume: $("#opt-resume").checked,
        ...extra,
      }),
    });
    app.cursor = 0;
    app.logLines = [];
    showView("pipeline");
    toast("Run started", "ok");
    refresh();
  } catch (error) {
    toast(error.message, "bad");
  }
}

async function stopRun() {
  try {
    await api("/api/stop", { method: "POST" });
    toast("Stopping run…");
    refresh();
  } catch (error) {
    toast(error.message, "bad");
  }
}

async function resetRun() {
  const confirmed = confirm(
    "Delete generated artifacts and start clean?\n\n" +
    "Removes: research/ outline/ draft/ editorial/ qa-reviews/ output/ .harness/ plan.md status.json\n" +
    "Keeps: spec.md, product-brief.md, and all source code."
  );
  if (!confirmed) return;
  try {
    const result = await api("/api/reset", { method: "POST" });
    app.cursor = 0;
    app.logLines = [];
    toast(result.removed.length ? `Removed ${result.removed.length} item(s)` : "Already clean", "ok");
    refresh();
  } catch (error) {
    toast(error.message, "bad");
  }
}

/* ── Views ─────────────────────────────────────────────────────── */

function showView(name) {
  for (const tab of document.querySelectorAll(".tab")) {
    tab.classList.toggle("active", tab.dataset.view === name);
  }
  for (const view of document.querySelectorAll(".view")) {
    view.classList.toggle("active", view.id === `view-${name}`);
  }
}

/* ── Wiring ────────────────────────────────────────────────────── */

function init() {
  $("#tabs").addEventListener("click", (event) => {
    if (event.target.matches(".tab")) showView(event.target.dataset.view);
  });

  $("#btn-run").onclick = () => startRun();
  $("#btn-stop").onclick = stopRun;
  $("#btn-reset").onclick = resetRun;

  $("#btn-spec-save").onclick = saveSpec;
  $("#btn-spec-revert").onclick = () => { $("#spec-editor").value = app.specOnDisk; validateSpec(); };
  $("#spec-editor").addEventListener("input", scheduleValidate);
  $("#spec-editor").addEventListener("keydown", (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key === "s") { event.preventDefault(); saveSpec(); }
  });

  $("#btn-brief-run").onclick = () => {
    const brief = $("#brief-editor").value.trim();
    if (!brief) { toast("Write a brief first.", "bad"); return; }
    startRun({ brief, regenerate_spec: $("#opt-regen").checked });
  };

  $("#artifact-filter").addEventListener("input", renderTree);
  $("#opt-raw").addEventListener("change", () => app.selectedFile && openFile(app.selectedFile));
  $("#opt-follow").addEventListener("change", renderConsole);

  loadSpec().catch(() => {});
  api("/api/brief").then(({ content }) => { $("#brief-editor").value = content; }).catch(() => {});
  refresh();
}

document.addEventListener("DOMContentLoaded", init);
