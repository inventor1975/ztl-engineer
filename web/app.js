// Zero-Trust Engineer — the page. No framework: one session, polled while a run is in progress.
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
let PRESETS = [], S = null, polling = null;

async function api(path, body) {
  const r = await fetch(path, body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const d = await r.json();
  if (!r.ok) throw new Error(d.error || r.statusText);
  return d;
}

function showHint(p) {
  $("hint").innerHTML = `<div class="icon">${p.icon}</div>
    <dl><dt>Tell the AI</dt><dd>${esc(p.say)}</dd><dt>Give it</dt><dd>${esc(p.give)}</dd></dl>
    <div class="example"><b>Example</b><br>${esc(p.example)}<br><button class="ghost small" id="useEx">Use this example</button></div>`;
  $("useEx").onclick = () => { $("text").value = p.example; $("text").focus(); };
}

async function init() {
  PRESETS = await api("/api/presets");
  $("preset").innerHTML = PRESETS.map((p) => `<option value="${p.id}">${p.icon}  ${esc(p.title)}</option>`).join("");
  $("preset").onchange = () => showHint(PRESETS.find((p) => p.id === $("preset").value));
  showHint(PRESETS[0]);
  S = await api("/api/session", { preset: PRESETS[0].id });
  render(S);
  refreshSpend();
}

async function refreshSpend() {
  try { const s = await api("/api/spend"); $("spend").textContent = `API $${s.usd.toFixed(2)} / $${s.cap.toFixed(0)}`; } catch (e) {}
}

// ---------- files
const drop = $("drop");
drop.onclick = () => $("picker").click();
$("picker").onchange = (e) => upload([...e.target.files]);
drop.ondragover = (e) => { e.preventDefault(); drop.classList.add("over"); };
drop.ondragleave = () => drop.classList.remove("over");
drop.ondrop = (e) => { e.preventDefault(); drop.classList.remove("over"); upload([...e.dataTransfer.files]); };

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
    if (["done", "error", "idle"].includes(S.job.phase)) { clearInterval(polling); refreshSpend(); }
  }, 700);
}

// ---------- render
const PHASE = { starting: "Starting…", reading: "Muse Spark is reading", proving: "ZTL stand is proving",
  repairing: "Muse Spark is repairing the brick", done: "Done", error: "Stopped", idle: "" };

function render(s) {
  // files
  $("files").innerHTML = s.files.map((f) => `<li><span class="kind">${f.kind}</span>${esc(f.name)} <span class="muted">${(f.size / 1024).toFixed(0)} KB</span></li>`).join("");
  // chat
  $("empty").hidden = s.history.length > 0;
  const msgs = s.history.map((m) => `<div class="msg ${m.role}"><span class="who">${m.role === "user" ? "You" : "Muse Spark"}</span>${esc(m.text)}</div>`).join("");
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
  // verdict
  const w = s.warranty, r = s.result || {};
  if (w) {
    const cls = w.status === "EARNED" ? "EARNED" : w.status === "REFUTED" ? "REFUTED" : w.status.includes("CREDIT") ? "CREDIT" : "OPEN";
    $("verdict").className = `verdict ${cls}`;
    $("verdict").innerHTML = `<span class="chip">${esc(w.status)}</span><span class="head">${esc(w.headline)}</span>
      ${s.question ? `<span class="why">Question: ${esc(s.question)}</span>` : ""}
      ${w.dirty && w.dirty.length ? `<span class="why">Rests on dirty values: <b>${w.dirty.map(esc).join(", ")}</b></span>` : ""}
      ${w.formula ? `<span class="why">ZTL: ${esc(w.formula)} = ${esc(w.ztl_value)}</span>` : ""}`;
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
  $("vals").innerHTML = s.values.map((v) => {
    const clean = v.confirmed || v.from === "file";
    return `<tr><td class="q">${esc(v.quantity)}</td>
      <td><input type="text" data-q="${esc(v.quantity)}" value="${esc(v.value)}"> <span class="muted">${esc(v.unit || "")}</span>
        ${v.read_as ? `<div class="where">read as ${esc(v.read_as)}</div>` : ""}</td>
      <td><span class="src ${clean ? "clean" : "dirty"}">${clean ? "confirmed" : "dirty"}</span>
        <div class="where">${esc(v.from)}${v.where ? ": " + esc(v.where) : ""}</div></td>
      <td class="row-actions">${clean ? "" : `<button class="small" data-confirm="${esc(v.quantity)}">Confirm</button>`}</td></tr>`;
  }).join("");
  document.querySelectorAll("[data-confirm]").forEach((b) => b.onclick = () => confirmValue(b.dataset.confirm));
  document.querySelectorAll("#vals input").forEach((inp) => inp.onkeydown = (e) => { if (e.key === "Enter") confirmValue(inp.dataset.q); });
  // details
  $("detailsCard").hidden = !s.result || !Object.keys(r).length;
  $("details").innerHTML = details(r);
  $("brick").textContent = s.brick ? JSON.stringify(s.brick, null, 2) : "";
  $("raw").textContent = Object.keys(r).length ? JSON.stringify(r, null, 2) : "";
}

function kv(obj) {
  if (!obj || typeof obj !== "object") return esc(obj);
  return `<div class="kv">${Object.entries(obj).map(([k, v]) => `<b>${esc(k)}</b><span>${esc(Array.isArray(v) ? v.join(" … ") : typeof v === "object" ? JSON.stringify(v) : v)}</span>`).join("")}</div>`;
}
function details(r) {
  let h = "";
  if (r.find && r.proved) h += `<div class="limit"><span class="muted">${r.find === "largest" ? "Largest" : "Smallest"} ${esc(r.quantity)} that works</span>
      <b>${esc(r.proved)} ${esc(r.unit || "")}</b><span class="muted">${esc(r.proved_means || "")}</span>
      ${r.beyond_is ? `<span class="muted">Just past it: ${esc(r.beyond_is)}</span>` : ""}</div>`;
  if (r.why) h += `<p class="muted" style="font-size:13px">${esc(r.why)}</p>`;
  if (r.design) h += `<h3 style="margin-top:10px">Design</h3>${kv(r.design)}`;
  if (r.guaranteed) h += `<h3 style="margin-top:10px">Guaranteed ranges</h3>${kv(r.guaranteed)}`;
  if (r.limit) h += `<h3 style="margin-top:10px">Limit</h3>${kv(r.limit)}`;
  if (r.closest_design) h += `<h3 style="margin-top:10px">Closest design</h3>${kv(r.closest_design)}`;
  if (r.its_violating_point) h += `<h3 style="margin-top:10px">Where it fails</h3>${kv(r.its_violating_point)}`;
  if (r.minimal_conflicts && r.minimal_conflicts.sets) h += `<h3 style="margin-top:10px">Requirements that cannot hold together</h3>` +
    r.minimal_conflicts.sets.map((s) => `<div class="conflict">${s.map(esc).join(" + ")}</div>`).join("");
  return h;
}

async function confirmValue(q) {
  const inp = document.querySelector(`#vals input[data-q="${CSS.escape(q)}"]`);
  try { S = await api(`/api/session/${S.id}/confirm`, { quantity: q, value: inp ? inp.value : null }); render(S); poll(); }
  catch (e) { alert(e.message); }
}
$("confirmAll").onclick = async () => { S = await api(`/api/session/${S.id}/confirm_all`, {}); render(S); };

init();
