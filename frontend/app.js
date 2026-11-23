// Notes → proposal, shown as a pipeline:
// 1 input → 2 Claude extraction → 3 follow-up questions → 4 fields after rules
// → 5 AI-drafted text → 6 object for window.loadProposal() in the proposal tool.

const state = { schema: null, notes: "", fields: null, flags: [], questionsDone: false };
const $ = (id) => document.getElementById(id);
const show = (id, on = true) => ($(id).hidden = !on);

async function api(path, body) {
  const opts = body === undefined ? {} : {
    method: "POST",
    headers: body instanceof FormData ? {} : { "Content-Type": "application/json" },
    body: body instanceof FormData ? body : JSON.stringify(body),
  };
  const res = await fetch(path, opts);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `Request failed (${res.status})`);
  return data;
}

// Run an async step with a "Working…" label and a disabled button; show errors inline.
async function step(btnId, workingId, fn) {
  $(btnId).disabled = true; show(workingId);
  try { return await fn(); }
  catch (e) { alert(e.message); throw e; }
  finally { $(btnId).disabled = false; show(workingId, false); }
}

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

// ── Start-up ──────────────────────────────────────────────────────────────
async function init() {
  state.schema = await api("/api/schema");
  const h = await api("/api/health");
  $("status").innerHTML =
    `<span class="${h.claude ? "ok" : "off"}">Claude: ${h.claude ? esc(h.model) : "no API key"}</span>` +
    `<span class="${h.whisper ? "ok" : "off"}">Voice: ${h.whisper ? "Whisper (local)" : "not installed"}</span>`;
  for (const s of await api("/api/samples")) {
    const o = new Option(s.name, s.id);
    o.dataset.text = s.text;
    $("sampleSelect").add(o);
  }
}

// ── 1. Input ──────────────────────────────────────────────────────────────
$("sampleSelect").addEventListener("change", (e) => {
  const t = e.target.selectedOptions[0]?.dataset.text;
  if (t) { $("notes").value = t; show("transcriptNote", false); }
});

async function transcribe(blob, filename) {
  const fd = new FormData();
  fd.append("file", blob, filename);
  const { text } = await step("extractBtn", "inputWorking", () => api("/api/transcribe", fd));
  $("notes").value = text;
  show("transcriptNote");
}

$("audioFile").addEventListener("change", async () => {
  const file = $("audioFile").files[0];
  if (file) await transcribe(file, file.name);
  $("audioFile").value = "";
});

// Record straight from the microphone (browser MediaRecorder; Chrome gives webm, Safari mp4).
let recorder = null, recTimer = null;
$("recordBtn").addEventListener("click", async () => {
  if (recorder) { recorder.stop(); return; }
  let stream;
  try { stream = await navigator.mediaDevices.getUserMedia({ audio: true }); }
  catch (e) { return alert("Microphone access was blocked. Allow it in the browser's site settings."); }
  const type = ["audio/webm", "audio/mp4"].find((t) => MediaRecorder.isTypeSupported(t)) || "";
  const chunks = [];
  recorder = new MediaRecorder(stream, type ? { mimeType: type } : {});
  recorder.ondataavailable = (e) => e.data.size && chunks.push(e.data);
  recorder.onstop = async () => {
    clearInterval(recTimer);
    stream.getTracks().forEach((t) => t.stop());
    $("recordBtn").classList.remove("on");
    $("recordBtn").textContent = "● Record voice note";
    const mime = recorder.mimeType || type || "audio/webm";
    recorder = null;
    const blob = new Blob(chunks, { type: mime });
    if (blob.size) await transcribe(blob, mime.includes("mp4") ? "recording.m4a" : "recording.webm");
  };
  recorder.start();
  const started = Date.now();
  $("recordBtn").classList.add("on");
  const tick = () => {
    const s = Math.floor((Date.now() - started) / 1000);
    $("recordBtn").textContent = `■ Stop (${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")})`;
  };
  tick();
  recTimer = setInterval(tick, 500);
});

$("extractBtn").addEventListener("click", async () => {
  state.notes = $("notes").value.trim();
  if (!state.notes) return alert("Add some notes first.");
  const data = await step("extractBtn", "inputWorking", () => api("/api/extract", { notes: state.notes }));
  state.fields = data.fields;
  state.flags = data.flags || [];
  state.questionsDone = false;

  $("rawJson").textContent = JSON.stringify(data.raw, null, 2);
  show("flags", state.flags.length > 0);
  $("flags").innerHTML = `<b>Flags for the PM</b><ul>${state.flags.map((f) => `<li>${esc(f)}</li>`).join("")}</ul>`;
  $("answered").innerHTML = "";
  ["stage-raw", "stage-questions", "stage-fields"].forEach((id) => show(id));
  ["stage-text", "stage-output"].forEach((id) => show(id, false));
  $("needsText").value = ""; $("riskText").value = "";

  renderChecks(data.checks);
  renderFields();
  onQuestion(data);
});

// ── 3. One question at a time ─────────────────────────────────────────────
let currentQ = null;

function onQuestion(data) {
  state.fields = data.fields;
  renderChecks(data.checks);
  currentQ = data.question;
  show("qcard", !!currentQ);
  show("qDone", !currentQ);
  $("qCount").textContent = currentQ ? `(${data.remaining} left)` : "";
  if (!currentQ) return finishQuestions();

  $("qText").textContent = currentQ.text;
  show("qError", false);
  $("qOptions").innerHTML = currentQ.options
    .map((o) => `<button class="btn" data-v="${esc(o.value)}" title="${esc(o.hint || "")}">${esc(o.label)}</button>`).join("");
  $("qOptions").querySelectorAll("button").forEach((b) =>
    b.addEventListener("click", () => answer(b.dataset.v, b.textContent)));
  show("qForm", currentQ.options.length === 0);
  $("qInput").value = "";
  $("qInput").placeholder = currentQ.placeholder || "Type the answer";
}

async function answer(value, label, skip = false) {
  const data = await api("/api/answer", { fields: state.fields, key: currentQ.key, answer: value, skip });
  if (data.error) { $("qError").textContent = data.error; show("qError"); return; }
  const li = document.createElement("li");
  li.innerHTML = `${esc(currentQ.label)}: <b>${skip ? "TO CONFIRM" : esc(label)}</b>`;
  $("answered").appendChild(li);
  state.fields = data.fields;
  renderChecks(data.checks);
  renderFields();
  onQuestion(data);
}

$("qForm").addEventListener("submit", (e) => {
  e.preventDefault();
  const v = $("qInput").value.trim();
  if (v) answer(v, v);
});
$("qSkip").addEventListener("click", () => answer(null, null, true));

async function finishQuestions() {
  if (state.questionsDone) return;
  state.questionsDone = true;
  show("stage-text"); show("stage-output");
  await writeText();
}

// ── Consistency checks (rule-based, from the backend) ─────────────────────
function renderChecks(checks) {
  state.checks = checks || [];
  const html = state.checks.map((c) =>
    `<div class="check ${c.level}"><b>${c.level === "warning" ? "Check:" : "Note:"}</b>${esc(c.message)}</div>`).join("");
  ["checks", "checksOut"].forEach((id) => { $(id).innerHTML = html; show(id, state.checks.length > 0); });
}

// ── 4. Fields table ───────────────────────────────────────────────────────
function shownValue(spec, v) {
  if (v === null || v === undefined) return "";
  if (spec.kind === "bool") return v ? "true" : "false";
  return String(v);
}

function control(spec, entry) {
  const v = shownValue(spec, entry.value);
  if (spec.kind === "enum" || spec.kind === "bool") {
    const opts = spec.kind === "bool" ? ["true", "false"] : spec.options;
    return `<select data-key="${spec.key}"><option value="">(to confirm)</option>${opts
      .map((o) => `<option ${o === v ? "selected" : ""}>${esc(o)}</option>`).join("")}</select>`;
  }
  return `<input data-key="${spec.key}" value="${esc(v)}" placeholder="(to confirm)">`;
}

function renderFields() {
  const f = state.fields;
  let html = "", group = "";
  for (const spec of state.schema.fields) {
    if (spec.key === "financialPlanner" && f.introGreetTo?.value !== "advisor") continue;
    if (spec.key === "replacementDetails" && f.isReplacement?.value !== true) continue;
    if (spec.group !== group) { group = spec.group; html += `<tr class="group"><td colspan="5">${esc(group)}</td></tr>`; }
    const e = f[spec.key] || { source: "missing" };
    const optional = e.source === "missing" && !spec.ask && spec.key !== "financialPlanner";
    const src = optional ? "optional" : e.source;
    const srcLabel = optional ? "Optional" : state.schema.sources[src] || src;
    const raw = e.raw === undefined || e.raw === null ? "—" : JSON.stringify(e.raw);
    let ev = e.evidence ? `“${esc(e.evidence)}”` : "";
    if (e.reason) ev += `${ev ? "<br>" : ""}${esc(e.reason)}`;
    if (e.pmWording) ev += `<br>PM wrote: “${esc(e.pmWording)}”`;
    const flagged = (state.checks || []).some((c) => c.level === "warning" && c.fields.includes(spec.key));
    html += `<tr class="${flagged ? "flagged" : ""}"><td>${esc(spec.label)}<br><code>${spec.key}</code></td><td class="raw">${esc(raw)}</td>
      <td>${control(spec, e)}</td><td><span class="tag ${src}">${esc(srcLabel)}</span></td><td class="ev">${ev}</td></tr>`;
  }
  $("fieldRows").innerHTML = html;
  $("fieldRows").querySelectorAll("[data-key]").forEach((el) =>
    el.addEventListener("change", () => editField(el.dataset.key, el.value)));
  if (state.questionsDone) refreshOutput();
}

async function editField(key, value) {
  const data = await api("/api/answer", { fields: state.fields, key, answer: value, skip: value.trim() === "" });
  if (data.error) alert(data.error);
  else { state.fields = data.fields; renderChecks(data.checks); }
  renderFields();
}

// ── 5. AI-drafted text ────────────────────────────────────────────────────
async function writeText() {
  const data = await step("textBtn", "textWorking",
    () => api("/api/narrative", { fields: state.fields, notes: state.notes }));
  $("needsText").value = data.narrative.needs || "";
  $("riskText").value = data.narrative.riskProfile || "";
  refreshOutput();
}
$("textBtn").addEventListener("click", writeText);
["needsText", "riskText"].forEach((id) => $(id).addEventListener("input", refreshOutput));

// ── 6. Output ─────────────────────────────────────────────────────────────
async function buildProposal() {
  const { proposal, checks } = await api("/api/proposal", {
    fields: state.fields,
    narrative: { needs: $("needsText").value, riskProfile: $("riskText").value },
  });
  renderChecks(checks);
  return proposal;
}

let refreshTimer;
function refreshOutput() {
  clearTimeout(refreshTimer);
  refreshTimer = setTimeout(async () => {
    $("proposalJson").textContent = JSON.stringify(await buildProposal(), null, 2);
  }, 250);
}

// Opens the unchanged tool in a new tab (same origin) and calls its loadProposal().
$("openToolBtn").addEventListener("click", async () => {
  const tab = window.open("/tool", "meridian-tool");   // open first so the popup isn't blocked
  const proposal = await buildProposal();
  let tries = 0;
  const timer = setInterval(() => {
    tries++;
    try {
      if (tab && typeof tab.loadProposal === "function" && tab.document.readyState === "complete") {
        clearInterval(timer);
        tab.loadProposal(proposal);
        tab.focus();
      }
    } catch (_) { /* tab still loading */ }
    if (tries > 60) { clearInterval(timer); alert("The proposal tool didn't load in time — try again."); }
  }, 250);
});

$("downloadBtn").addEventListener("click", async () => {
  const blob = new Blob([JSON.stringify(await buildProposal(), null, 2)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `${(state.fields.clientName?.value || "proposal").replace(/[^a-z0-9]+/gi, "-").toLowerCase()}-draft.json`;
  a.click();
});

$("restartBtn").addEventListener("click", () => {
  ["stage-raw", "stage-questions", "stage-fields", "stage-text", "stage-output"].forEach((id) => show(id, false));
  $("notes").value = ""; $("sampleSelect").value = ""; show("transcriptNote", false);
  window.scrollTo(0, 0);
});

init().catch((e) => alert(`Couldn't start: ${e.message}`));
