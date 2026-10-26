// ZTL Engineer — the page. No framework: one session, polled while a run is in progress.
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
let PRESETS = [], S = null, polling = null, VIEW = null;   // VIEW: an earlier run being looked at, or null
const KEY = "ztl-engineer.session";

async function api(path, body) {
  const r = await fetch(path, body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const d = await r.json();
  if (!r.ok) throw new Error(d.error || r.statusText);
  return d;
}

function showHint(p) {
  $("hint").innerHTML = `<div class="icon">${p.icon}</div>
    <dl><dt>Tell the AI</dt><dd>${esc(p.say)}</dd><dt>Give it</dt><dd>${esc(p.give)}</dd></dl>
    <div class="example"><b>Example</b><br>${esc(p.example)}<br><button class="ghost small" id="useEx">Use this example${p.demo ? " (with demo file" + (p.demo.length > 1 ? "s" : "") + ")" : ""}</button></div>`;
  $("useEx").onclick = async () => {
    $("text").value = p.example;
    // the example's own demo files (a nameplate, a netlist + BOM, a deck) go into the session with it
    for (const name of p.demo || []) {
      if (S.files.some((f) => f.name === name)) continue;
      const blob = await (await fetch(`/demo/${name}`)).blob();
      const b64 = await new Promise((res) => { const r = new FileReader(); r.onload = () => res(r.result.split(",")[1]); r.readAsDataURL(blob); });
      await api(`/api/session/${S.id}/file`, { name, mime: blob.type, b64 });
    }
    S = await api(`/api/session/${S.id}`); render(S);
    $("text").focus();
  };
}

async function init() {
  PRESETS = await api("/api/presets");
  $("preset").innerHTML = PRESETS.map((p) => `<option value="${p.id}">${p.icon}  ${esc(p.title)}</option>`).join("");
  $("preset").value = "pump";                // the default task (curator): the pump, first among the examples
  $("preset").onchange = () => showHint(PRESETS.find((p) => p.id === $("preset").value));
  // the session survives going to Help and back, and a server restart: its id is kept in this browser
  let sid = null;
  try { sid = localStorage.getItem(KEY); } catch (e) {}
  if (sid) { try { S = await api(`/api/session/${sid}`); } catch (e) { S = null; } }
  if (!S) await newSession();
  $("preset").value = S.preset;
  showHint(PRESETS.find((p) => p.id === S.preset) || PRESETS[0]);
  render(S);
  if (!["idle", "done", "error"].includes(S.job.phase)) poll();
  refreshSpend();
}
async function newSession() {
  S = await api("/api/session", { preset: $("preset").value || PRESETS[0].id });
  try { localStorage.setItem(KEY, S.id); } catch (e) {}
  VIEW = null;
}
$("newSession").onclick = async () => { await newSession(); render(S); };

async function refreshSpend() {
  try { const s = await api("/api/spend"); $("spend").textContent = `API $${s.usd.toFixed(2)} / $${s.cap.toFixed(0)}`; } catch (e) {}
}

// ---------- files
const chat = document.querySelector(".chat");
$("attach").onclick = () => $("picker").click();
$("picker").onchange = (e) => { upload([...e.target.files]); e.target.value = ""; };
chat.ondragover = (e) => { e.preventDefault(); chat.classList.add("over"); };
chat.ondragleave = (e) => { if (!chat.contains(e.relatedTarget)) chat.classList.remove("over"); };
chat.ondrop = (e) => { e.preventDefault(); chat.classList.remove("over"); upload([...e.dataTransfer.files]); };

async function upload(files) {
  for (const f of files) {
    const b64 = await new Promise((res) => { const r = new FileReader(); r.onload = () => res(r.result.split(",")[1]); r.readAsDataURL(f); });
    await api(`/api/session/${S.id}/file`, { name: f.name, mime: f.type, b64 });
  }
  S = await api(`/api/session/${S.id}`);
  render(S);
}

// ---------- chat
$("send").onclick = send;
$("text").onkeydown = (e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) send(); };
async function send() {
  const text = $("text").value.trim();
  if (!text) return;
  $("text").value = "";
  try {
    S = await api(`/api/session/${S.id}/message`, { text, preset: $("preset").value });
    render(S); poll();
  } catch (e) { alert(e.message); }
}

function poll() {
  clearInterval(polling);
  polling = setInterval(async () => {
    S = await api(`/api/session/${S.id}`);
    render(S);
    if (["done", "error", "idle"].includes(S.job.phase)) { clearInterval(polling); VIEW = null; render(S); refreshSpend(); }
  }, 700);
}

// ---------- render
const PHASE = { starting: "Starting…", reading: "Muse Spark is reading", proving: "ZTL stand is proving",
  repairing: "Muse Spark is repairing the brick", done: "Done", error: "Stopped", idle: "" };

function render(s0) {
  let s = s0;
  // files
  // files waiting to be sent sit above the input; sent files live in their message, with a download link
  $("files").innerHTML = s.files.filter((f) => f.msg === null || f.msg === undefined).map((f) =>
    `<li title="${(f.size / 1024).toFixed(0)} KB"><span class="kind">${f.kind}</span>${esc(f.name)}
     <button class="x" data-unattach="${esc(f.name)}" title="Remove">×</button></li>`).join("");
  document.querySelectorAll("[data-unattach]").forEach((b) => b.onclick = async () => {
    S = await api(`/api/session/${S.id}/file_remove`, { name: b.dataset.unattach }); render(S); });
  // chat
  $("empty").hidden = s.history.length > 0;
  const fileLink = (n) => `<a class="att" href="/api/session/${s.id}/file/${encodeURIComponent(n)}" download>📎 ${esc(n)}</a>`;
  const msgs = s.history.map((m) => `<div class="msg ${m.role}"><span class="who">${m.role === "user" ? "You" : "Muse Spark"}</span>${esc(m.text)}${
    m.files && m.files.length ? `<div class="atts">${m.files.map(fileLink).join("")}</div>` : ""}</div>`).join("");
  $("msgs").innerHTML = msgs;
  $("msgs").scrollTop = $("msgs").scrollHeight;
  // progress
  const j = s.job, running = !["idle", "done", "error"].includes(j.phase);
  $("progress").hidden = j.phase === "idle";
  $("send").disabled = running;
  $("phase").textContent = PHASE[j.phase] || j.phase;
  const bar = $("bar");
  if (j.phase === "proving" && j.total) {
    bar.classList.remove("indet"); bar.firstElementChild.style.width = `${Math.min(100, j.percent || 0)}%`;
    $("pcount").textContent = `${j.tried} of ${j.total} designs · ${j.elapsed}s`;
  } else if (running) {
    bar.classList.add("indet"); $("pcount").textContent = `${j.elapsed || 0}s`;
  } else {
    bar.classList.remove("indet"); bar.firstElementChild.style.width = j.phase === "done" ? "100%" : "0%";
    $("pcount").textContent = j.elapsed ? `${j.elapsed}s` : "";
  }
  $("log").innerHTML = (j.log || []).map((l) => `<li>${esc(l.msg)}</li>`).join("") + (j.error ? `<li style="color:var(--refuted)">${esc(j.error)}</li>` : "");
  // runs
  $("runsCard").hidden = !(s.runs && s.runs.length);
  $("runs").innerHTML = (s.runs || []).slice().reverse().map((x) => `<li class="${VIEW && VIEW.n === x.n ? "on" : ""}" data-run="${x.n}">
      <span class="rn">#${x.n}</span><span class="rq">${esc(x.question || "")}</span>
      <span class="rs ${chipClass(x.verdict || "")}">${esc(x.verdict || "")}</span><span class="rt">${esc(x.at)}</span></li>`).join("");
  document.querySelectorAll("[data-run]").forEach((li) => li.onclick = () => openRun(+li.dataset.run));
  const latest = s.runs && s.runs.length ? s.runs[s.runs.length - 1].n : null;
  const old = VIEW && VIEW.n !== latest;
  $("viewing").hidden = !old;
  if (old) $("viewing").innerHTML = `Viewing run #${VIEW.n} from ${esc(VIEW.at)} · <a href="#" id="backNow">back to the latest</a>`;
  if (old) $("backNow").onclick = (e) => { e.preventDefault(); VIEW = null; render(S); };
  if (old) s = Object.assign({}, s, { warranty: VIEW.warranty, result: VIEW.result || {}, values: VIEW.values || [],
                                      brick: VIEW.brick, question: VIEW.question, job: { phase: "done", log: [] } });
  // verdict
  const w = s.warranty, r = s.result || {};
  const shownRun = old ? VIEW.n : (s.runs && s.runs.length && !running && s.result && Object.keys(s.result).length ? s.runs[s.runs.length - 1].n : null);
  if (w) {
    // the stand's verdict is the answer; where its data came from is a note under it, not a second verdict
    const v = r.verdict || w.status;
    const HEAD = { EARNED: "Proved: the design holds for every value the tolerances allow.",
                   REFUTED: "Refuted: the design fails at a concrete point — see Details.",
                   OPEN: "Undecided: the stand could not prove it either way, and does not guess." };
    const ai = (s.values || []).filter((x) => x.from !== "file" && x.from !== "you").length;
    $("verdict").className = `verdict ${chipClass(v)}`;
    $("verdict").innerHTML = `<span class="chip">${esc(v)}</span><span class="head">${esc(HEAD[v] || w.headline)}</span>
      ${s.question ? `<span class="why">Question: ${esc(s.question)}</span>` : ""}
      ${ai ? `<span class="note">${ai} of the values come from Muse Spark's reading of your words or files — check them
        in the table; change any and press Recalculate.</span>` : (s.values && s.values.length ? `<span class="note">Every value is yours.</span>` : "")}
      ${shownRun ? `<span class="downloads">Download: <a href="/api/session/${s.id}/run/${shownRun}/report.html" download>Report (HTML)</a>
        <a href="/api/session/${s.id}/run/${shownRun}/results.json" download>Results (JSON)</a>
        <a href="/api/session/${s.id}/run/${shownRun}/brick.json" download title="Re-run it on ztl-stand alone: python3 -m ustand.stand brick.json">Brick (JSON)</a></span>` : ""}`;
  } else if (running) {
    $("verdict").className = "verdict IDLE"; $("verdict").innerHTML = `<span class="chip">WORKING</span><span class="head">${PHASE[j.phase] || ""}…</span>`;
  } else if (j.phase === "error") {
    $("verdict").className = "verdict REFUTED"; $("verdict").innerHTML = `<span class="chip">STOPPED</span><span class="head">${esc(j.error || "")}</span>`;
  } else {
    $("verdict").className = "verdict IDLE";
    $("verdict").innerHTML = `<span class="chip">WAITING</span><span class="head">${s.history.length ? "Muse Spark needs more from you — see the conversation." : "No question yet."}</span>`;
  }
  // values
  $("valuesCard").hidden = !s.values.length;
  $("recalc").hidden = !!old;
  const Q = (s.brick && s.brick.quantities) || {};
  const tolOf = (q) => {          // what is confirmed is the whole specification: the value AND its tolerance
    const b = Q[q] || {};
    if (b.tolerance !== undefined) {
      const t = Number(b.tolerance);
      return isNaN(t) ? `± ${b.tolerance}` : `± ${+(t * 100).toPrecision(4)}%`;
    }
    return "";
  };
  $("vals").innerHTML = s.values.map((v) => {
    const clean = v.confirmed || v.from === "file";
    const yours = v.from === "file" || v.from === "you";
    return `<tr><td class="q">${esc(v.quantity)}</td>
      <td><input type="text" data-q="${esc(v.quantity)}" data-orig="${esc(v.value)}" value="${esc(v.value)}" ${old ? "disabled" : ""}> <span class="muted">${esc(v.unit || "")}</span>${tolOf(v.quantity) ? ` <span class="tol">${esc(tolOf(v.quantity))}</span>` : ""}
        ${v.read_as ? `<div class="where">AI read ${esc(v.read_as)}</div>` : ""}</td>
      <td><span class="src ${yours ? "you" : "ai"}">${yours ? "yours" : "AI read"}</span>
        <div class="where">${v.where && v.where.toLowerCase().startsWith(String(v.from).toLowerCase()) ? esc(v.where) : esc(v.from) + (v.where ? ": " + esc(v.where) : "")}</div></td><td></td></tr>`;
  }).join("");
  const markChanged = () => {
    let any = false;
    document.querySelectorAll("#vals input").forEach((inp) => { const c = inp.value.trim() !== inp.dataset.orig; inp.classList.toggle("changed", c); any = any || c; });
    $("recalc").disabled = !any || running;
  };
  document.querySelectorAll("#vals input").forEach((inp) => { inp.oninput = markChanged;
    inp.onkeydown = (e) => { if (e.key === "Enter" && !$("recalc").disabled) recalc(); }; });
  markChanged();
  // details
  $("detailsCard").hidden = !s.result || !Object.keys(r).length;
  $("details").innerHTML = details(r, s.brick);
  $("brick").textContent = s.brick ? JSON.stringify(s.brick, null, 2) : "";
  $("raw").textContent = Object.keys(r).length ? JSON.stringify(r, null, 2) : "";
}

// the stand writes exact fractions with an approximation: "324139…/144115… (~2.24917)" — people read the ≈ value
function pretty(v) {
  if (Array.isArray(v)) return v.map(pretty).join(" … ");
  if (v && typeof v === "object") return JSON.stringify(v);
  const s = String(v ?? "");
  const m = s.match(/\(~([^)\s]+)\)/) || s.match(/^~(\S+)/);
  return m ? "≈ " + m[1] : s;
}
const fmt = (x) => (typeof x === "number" ? (Math.abs(x) >= 1000 || Math.abs(x) < 0.01 ? x.toPrecision(5) : x.toFixed(4).replace(/0+$/, "").replace(/\.$/, "")) : String(x ?? "—"));
const pts = (at) => at ? Object.entries(at).map(([k, v]) => `${k}=${pretty(v)}`).join(", ") : "—";
// a design choice as people read it: {"catalog":"res_1pct","R":{"nominal":"1000","tolerance":"1/100"}} -> "R 1000 ±1% (res_1pct)"
function choice(d) {
  if (d === null || typeof d !== "object") return pretty(d);
  const parts = [];
  let cat = "", item = "";
  for (const [k, v] of Object.entries(d)) {
    if (k === "catalog") { cat = String(v); continue; }
    if (["item", "name", "part", "id"].includes(k)) { item = String(v); continue; }
    if (v && typeof v === "object" && "nominal" in v) {
      const t = v.tolerance !== undefined ? Number(String(v.tolerance).split(" ")[0].split("/").reduce((a, b) => a / b)) : null;
      parts.push(`${k} ${pretty(v.nominal)}${t ? ` ±${+(t * 100).toPrecision(3)}%` : ""}`);
    } else if (v && typeof v === "object" && ("min" in v || "max" in v)) {
      parts.push(`${k} ${pretty(v.min)} … ${pretty(v.max)}`);
    } else parts.push(`${k} ${pretty(v)}`);
  }
  return [item, parts.join(", "), cat ? `(${cat})` : ""].filter(Boolean).join(" ");
}
function chipClass(st) {
  return st === "EARNED" ? "EARNED" : st === "REFUTED" ? "REFUTED" : String(st).includes("CREDIT") ? "CREDIT" : "OPEN";
}
async function openRun(n) {
  const latest = S.runs[S.runs.length - 1].n;
  VIEW = n === latest ? null : await api(`/api/session/${S.id}/run/${n}`);
  render(S);
}
function kv(obj) {
  if (!obj || typeof obj !== "object") return esc(obj);
  return `<div class="kv">${Object.entries(obj).map(([k, v]) => `<b>${esc(k)}</b><span>${esc(pretty(v))}</span>`).join("")}</div>`;
}
function details(r, brick) {
  let h = "";
  if (r.find && r.proved) h += `<div class="limit"><span class="muted">${r.find === "largest" ? "Largest" : "Smallest"} ${esc(r.quantity)} that works</span>
      <b>${esc(pretty(r.proved))} ${esc(r.unit || "")}</b><span class="muted">${esc(r.proved_means || "")}</span>
      ${r.beyond_is ? `<span class="muted">Just past it: ${esc(r.beyond_is)}</span>` : ""}</div>`;
  const noChoice = !brick || !brick.slots || !Object.keys(brick.slots).length;
  const why = noChoice && /^every design in the catalog violates/.test(r.why || "") ? "This design fails at a concrete point." : r.why;
  if (why) h += `<p class="muted" style="font-size:13px">${esc(why)}</p>`;
  if (r.design && Object.keys(r.design).length) h += `<h3 style="margin-top:10px">Chosen design</h3>` +
      `<div class="kv">${Object.entries(r.design).map(([slot, d]) => `<b>${esc(slot)}</b><span>${esc(choice(d))}</span>`).join("")}</div>`;
  if (r.exact_range) h += `<h3 style="margin-top:10px">Exact worst case</h3>` + Object.entries(r.exact_range).map(([t, e]) =>
      e.error ? `<p class="muted">${esc(t)}: ${esc(e.error)}</p>` :
      `<div class="limit"><span class="muted">${esc(t)} over every tolerance</span><b>${esc(fmt(e.min && e.min.approx))} … ${esc(fmt(e.max && e.max.approx))}</b>
        <span class="muted">min at ${esc(pts(e.min && e.min.at))}</span><span class="muted">max at ${esc(pts(e.max && e.max.at))}</span></div>`).join("");
  // what was checked: the requirements as the stand got them — the person sees how the model read the question
  const reqs = (brick && brick.requirements) || [];
  const Qs = (brick && brick.quantities) || {};
  if (reqs.length) h = `<h3>What was checked</h3>` + reqs.map((q) => {
    const unit = (Qs[q.quantity] && Qs[q.quantity].unit) || "";
    const val = Array.isArray(q.value) ? `${q.value[0]} … ${q.value[1]}` : q.value;
    return `<div class="req"><b>${esc(q.quantity)}</b> ${esc(q.op)} ${esc(val)} ${esc(unit)}${q.why ? `<span class="muted"> — ${esc(q.why)}</span>` : ""}</div>`;
  }).join("") + h;
  const gu = r.guaranteed_unit || {};
  const withUnit = (o) => Object.fromEntries(Object.entries(o).map(([k, v]) => [k + (gu[k] || (Qs[k] && Qs[k].unit) ? ` (${gu[k] || Qs[k].unit})` : ""), v]));
  if (r.guaranteed) h += `<h3 style="margin-top:10px">Proved to stay within</h3>${kv(withUnit(r.guaranteed))}` +
      (r.how ? `<p class="muted" style="font-size:12px">${Object.entries(r.how).map(([k, v]) => `${esc(k)}: ${esc(v)}`).join("<br>")}</p>` : "");
  if (r.limit) h += `<h3 style="margin-top:10px">Limit</h3>${kv(r.limit)}`;
  if (r.closest_design && Object.keys(r.closest_design).length) h += `<h3 style="margin-top:10px">Closest design</h3>` +
      `<div class="kv">${Object.entries(r.closest_design).map(([k, d]) => `<b>${esc(k)}</b><span>${esc(choice(d))}</span>`).join("")}</div>`;
  if (r.its_violating_point && Object.keys(r.its_violating_point).length) h += `<h3 style="margin-top:10px">Where it fails</h3>${kv(r.its_violating_point)}`;
  if (r.value_there) h += `<h3 style="margin-top:10px">Value there</h3>${kv(r.value_there)}`;
  if (r.overshoot) h += `<p class="muted" style="font-size:13px">Misses the requirement by ${esc(pretty(r.overshoot))}</p>`;
  if (r.minimal_conflicts && r.minimal_conflicts.sets) {
    // each set is a minimal conflict: a single requirement fails ON ITS OWN; a group fails only TOGETHER
    const one = r.minimal_conflicts.sets.filter((x) => x.length === 1), many = r.minimal_conflicts.sets.filter((x) => x.length > 1);
    if (one.length) h += `<h3 style="margin-top:10px">Fails on its own</h3>` + one.map((x) => `<div class="conflict">${esc(x[0])}</div>`).join("");
    if (many.length) h += `<h3 style="margin-top:10px">Cannot hold together — relax one of each group</h3>` +
      many.map((x) => `<div class="conflict">${x.map(esc).join(" <b>+</b> ")}</div>`).join("");
  }
  return h;
}

async function recalc() {
  const changes = {};
  document.querySelectorAll("#vals input").forEach((inp) => { if (inp.value.trim() !== inp.dataset.orig) changes[inp.dataset.q] = inp.value.trim(); });
  try { S = await api(`/api/session/${S.id}/recalc`, { changes }); render(S); poll(); }
  catch (e) { alert(e.message); }
}
$("recalc").onclick = recalc;

init();
