const API = "";
let token = localStorage.getItem("token");
let resumes = [];
let current = null;
let lastPdf = null;
let mode = "doc"; // "doc" | "form" | "raw"

async function api(path, opts = {}) {
  opts.headers = opts.headers || {};
  if (token) opts.headers["Authorization"] = "Bearer " + token;
  if (opts.body && typeof opts.body !== "string") {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(opts.body);
  }
  const res = await fetch(API + path, opts);
  if (res.status === 401 && path !== "/api/login") {
    localStorage.clear();
    location.reload();
    throw new Error("Session expired, please log in again");
  }
  const ct = res.headers.get("content-type") || "";
  if (ct.includes("application/pdf")) return res.blob();
  const data = ct.includes("json") ? await res.json() : await res.text();
  if (!res.ok) throw new Error(data.detail || res.statusText);
  return data;
}

const $ = (s) => document.querySelector(s);

// ---------- auth ----------
async function doAuth(kind) {
  $("#auth-error").textContent = "";
  try {
    const data = await api(kind === "login" ? "/api/login" : "/api/register", {
      method: "POST",
      body: { email: $("#auth-email").value.trim(), password: $("#auth-password").value },
    });
    token = data.token;
    localStorage.setItem("token", token);
    localStorage.setItem("email", data.email);
    enterApp();
  } catch (e) {
    $("#auth-error").textContent = typeof e.message === "string" ? e.message : "Error";
  }
}
$("#login-btn").onclick = () => doAuth("login");
$("#register-btn").onclick = () => doAuth("register");
$("#logout-btn").onclick = () => { token = null; localStorage.clear(); location.reload(); };

// ---------- app ----------
async function enterApp() {
  $("#auth-screen").classList.add("hidden");
  $("#app").classList.remove("hidden");
  $("#user-email").textContent = localStorage.getItem("email") || "";
  await loadResumes();
  if (resumes.length === 0) newResume(); else openResume(resumes[0].id);
}

async function loadResumes() {
  try { resumes = await api("/api/resumes"); } catch { resumes = []; }
  renderList();
}

function renderList() {
  const ul = $("#resume-list");
  ul.innerHTML = "";
  for (const r of resumes) {
    const li = document.createElement("li");
    if (current && r.id === current.id) li.className = "active";
    const span = document.createElement("span");
    span.textContent = r.title || "Untitled";
    span.onclick = () => openResume(r.id);
    const del = document.createElement("button");
    del.className = "del"; del.textContent = "×"; del.title = "Delete";
    del.onclick = async (e) => {
      e.stopPropagation();
      if (confirm("Delete this resume?")) {
        await api(`/api/resumes/${r.id}`, { method: "DELETE" });
        if (current && current.id === r.id) current = null;
        await loadResumes();
        if (!current && resumes.length) openResume(resumes[0].id);
        else if (!current) newResume();
      }
    };
    li.appendChild(span); li.appendChild(del);
    ul.appendChild(li);
  }
}

const esc = (s) => (s || "").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const EMPTY_CONTENT = () => ({ name: "", phone: "", email: "", linkedin: "", github: "", website: "", summary: "", education: [], experience: [], projects: [], skills: [], doc_html: "" });

function newResume() {
  current = { id: null, title: "Untitled Resume", template: "jakes", content: EMPTY_CONTENT(), raw_latex: null };
  $("#title").value = current.title;
  fillForm();
  $("#doc-editor").innerHTML = structureToHtml(current.content);
  $("#raw-editor").value = "";
  setMode("doc");
  renderList();
}

async function openResume(id) {
  current = await api(`/api/resumes/${id}`);
  $("#title").value = current.title;
  fillForm();
  $("#doc-editor").innerHTML = current.content.doc_html || structureToHtml(current.content);
  $("#raw-editor").value = current.raw_latex || "";
  setMode(current.raw_latex ? "raw" : "doc");
  renderList();
}

// ---------- structure <-> document HTML ----------
function structureToHtml(d) {
  const lines = [];
  lines.push(`<h1>${esc(d.name || "Your Name")}</h1>`);
  const contact = [d.phone, d.email, d.linkedin, d.github, d.website].filter(Boolean).map(esc).join(" &nbsp;|&nbsp; ");
  lines.push(`<p class="contact">${contact || "phone | email | linkedin | github"}</p>`);
  if (d.summary) lines.push(`<h2>Summary</h2><p>${esc(d.summary)}</p>`);
  if (d.education && d.education.length) {
    lines.push(`<h2>Education</h2>`);
    for (const e of d.education) {
      lines.push(`<div class="entry"><p class="er"><strong>${esc(e.school)}</strong><span class="r">${esc(e.location)}</span></p><p class="er sub"><em>${esc(e.degree)}</em><span class="r">${esc(e.dates)}</span></p></div>`);
    }
  }
  const addEntries = (arr, left, right, sub, dates) => {
    for (const e of arr) {
      lines.push(`<div class="entry"><p class="er"><strong>${esc(e[left])}</strong><span class="r">${esc(e[right])}</span></p><p class="er sub"><em>${esc(e[sub])}</em><span class="r">${esc(e[dates])}</span></p>`);
      const bs = (e.bullets || []).filter(b => b.trim());
      if (bs.length) lines.push(`<ul>${bs.map(b => `<li>${esc(b)}</li>`).join("")}</ul>`);
      lines.push(`</div>`);
    }
  };
  if (d.experience && d.experience.length) { lines.push(`<h2>Experience</h2>`); addEntries(d.experience, "company", "location", "title", "dates"); }
  if (d.projects && d.projects.length) { lines.push(`<h2>Projects</h2>`); addEntries(d.projects, "name", "tech", "dates", ""); }
  if (d.skills && d.skills.length) {
    lines.push(`<h2>Technical Skills</h2>`);
    for (const s of d.skills) lines.push(`<p class="skill"><strong>${esc(s.category)}</strong>: ${esc(s.items)}</p>`);
  }
  return lines.join("\n");
}

// ---------- doc editor ----------
function exec(cmd) { document.execCommand(cmd, false, null); $("#doc-editor").focus(); }

// ---------- form mode ----------
function fillForm() {
  document.querySelectorAll("[data-f]").forEach(el => { el.value = current.content[el.dataset.f] || ""; });
  renderEdu(); renderExp(); renderProj(); renderSkills();
}
function readForm() {
  document.querySelectorAll("[data-f]").forEach(el => { current.content[el.dataset.f] = el.value; });
}
function formToDoc() {
  readForm();
  current.content.doc_html = structureToHtml(current.content);
  $("#doc-editor").innerHTML = current.content.doc_html;
  setMode("doc");
}

const eduCard = (e, i) => `<div class="entry-card"><button class="remove" onclick="delEdu(${i})">×</button>
  <div class="grid2">
    <label>School<input value="${esc(e.school)}" oninput="cur_edu[${i}].school=this.value"></label>
    <label>Location<input value="${esc(e.location)}" oninput="cur_edu[${i}].location=this.value"></label>
    <label>Degree<input value="${esc(e.degree)}" oninput="cur_edu[${i}].degree=this.value"></label>
    <label>Dates<input value="${esc(e.dates)}" oninput="cur_edu[${i}].dates=this.value"></label>
  </div></div>`;
const expCard = (e, i) => `<div class="entry-card"><button class="remove" onclick="delExp(${i})">×</button>
  <div class="grid2">
    <label>Company<input value="${esc(e.company)}" oninput="cur_exp[${i}].company=this.value"></label>
    <label>Location<input value="${esc(e.location)}" oninput="cur_exp[${i}].location=this.value"></label>
    <label>Title<input value="${esc(e.title)}" oninput="cur_exp[${i}].title=this.value"></label>
    <label>Dates<input value="${esc(e.dates)}" oninput="cur_exp[${i}].dates=this.value"></label>
  </div>
  <label>Bullets (one per line)<textarea rows="3" oninput="cur_exp[${i}].bullets=this.value.split('\\n')">${esc((e.bullets||[]).join('\n'))}</textarea></label></div>`;
const projCard = (p, i) => `<div class="entry-card"><button class="remove" onclick="delProj(${i})">×</button>
  <div class="grid2">
    <label>Project name<input value="${esc(p.name)}" oninput="cur_proj[${i}].name=this.value"></label>
    <label>Tech<input value="${esc(p.tech)}" oninput="cur_proj[${i}].tech=this.value"></label>
    <label>Dates<input value="${esc(p.dates)}" oninput="cur_proj[${i}].dates=this.value"></label>
  </div>
  <label>Bullets (one per line)<textarea rows="3" oninput="cur_proj[${i}].bullets=this.value.split('\\n')">${esc((p.bullets||[]).join('\n'))}</textarea></label></div>`;
const skillCard = (s, i) => `<div class="entry-card"><button class="remove" onclick="delSkill(${i})">×</button>
  <div class="grid2">
    <label>Category<input value="${esc(s.category)}" oninput="cur_skills[${i}].category=this.value"></label>
    <label>Items<input value="${esc(s.items)}" oninput="cur_skills[${i}].items=this.value"></label>
  </div></div>`;

let cur_edu, cur_exp, cur_proj, cur_skills;
function syncCur() { cur_edu = current.content.education; cur_exp = current.content.experience; cur_proj = current.content.projects; cur_skills = current.content.skills; }
function renderEdu() { syncCur(); $("#edu-list").innerHTML = cur_edu.map(eduCard).join(""); }
function renderExp() { syncCur(); $("#exp-list").innerHTML = cur_exp.map(expCard).join(""); }
function renderProj() { syncCur(); $("#proj-list").innerHTML = cur_proj.map(projCard).join(""); }
function renderSkills() { syncCur(); $("#skills-list").innerHTML = cur_skills.map(skillCard).join(""); }
function addEdu() { current.content.education.push({}); renderEdu(); }
function addExp() { current.content.experience.push({ bullets: [] }); renderExp(); }
function addProj() { current.content.projects.push({ bullets: [] }); renderProj(); }
function addSkill() { current.content.skills.push({}); renderSkills(); }
function delEdu(i) { current.content.education.splice(i, 1); renderEdu(); }
function delExp(i) { current.content.experience.splice(i, 1); renderExp(); }
function delProj(i) { current.content.projects.splice(i, 1); renderProj(); }
function delSkill(i) { current.content.skills.splice(i, 1); renderSkills(); }

// ---------- modes ----------
function setMode(m) {
  mode = m;
  $("#tab-doc").classList.toggle("active", m === "doc");
  $("#tab-form").classList.toggle("active", m === "form");
  $("#tab-raw").classList.toggle("active", m === "raw");
  $("#doc-mode").classList.toggle("hidden", m !== "doc");
  $("#form-mode").classList.toggle("hidden", m !== "form");
  $("#raw-mode").classList.toggle("hidden", m !== "raw");
}
$("#tab-doc").onclick = () => setMode("doc");
$("#tab-form").onclick = () => setMode("form");
$("#tab-raw").onclick = () => setMode("raw");

// ---------- save / compile ----------
function currentPayload() {
  if (mode === "form") readForm();
  if (mode === "doc") current.content.doc_html = $("#doc-editor").innerHTML;
  return {
    title: $("#title").value || "Untitled Resume",
    template: "jakes",
    content: current.content,
    raw_latex: mode === "raw" ? $("#raw-editor").value : null,
  };
}

$("#save-btn").onclick = async () => {
  try {
    const payload = currentPayload();
    if (current.id) current = await api(`/api/resumes/${current.id}`, { method: "PUT", body: payload });
    else current = await api("/api/resumes", { method: "POST", body: payload });
    await loadResumes();
    flashStatus("Saved");
  } catch (e) { flashStatus(e.message, true); }
};

$("#compile-btn").onclick = async () => {
  const payload = currentPayload();
  flashStatus("Compiling…");
  try {
    const blob = await api("/api/compile", { method: "POST", body: payload });
    if (lastPdf) URL.revokeObjectURL(lastPdf);
    lastPdf = URL.createObjectURL(blob);
    $("#pdf-frame").src = lastPdf;
    $("#download-btn").disabled = false;
    flashStatus("Compiled");
  } catch (e) { flashStatus(e.message, true); }
};

$("#download-btn").onclick = () => {
  if (!lastPdf) return;
  const a = document.createElement("a");
  a.href = lastPdf;
  a.download = ($("#title").value || "resume") + ".pdf";
  a.click();
};

$("#new-btn").onclick = newResume;

$("#download-tex-btn").onclick = async () => {
  const payload = currentPayload();
  try {
    const res = await fetch("/api/tex", {
      method: "POST",
      headers: { "Authorization": "Bearer " + token, "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error("Failed to build .tex");
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = ($("#title").value || "resume") + ".tex"; a.click();
    URL.revokeObjectURL(url);
  } catch (e) { flashStatus(e.message, true); }
};

$("#import-latex-btn").onclick = async () => {
  const raw = $("#raw-editor").value;
  if (!raw.trim()) { flashStatus("Nothing to import", true); return; }
  try {
    const data = await api("/api/import-latex", { method: "POST", body: { raw_latex: raw } });
    applyImported(data);
    flashStatus(data.method === "parsed" ? "Imported (structured parse)" : "Imported (generic conversion)");
  } catch (e) { flashStatus(e.message, true); }
};

$("#import-latex-ai-btn").onclick = async () => {
  const raw = $("#raw-editor").value;
  if (!raw.trim()) { flashStatus("Nothing to import", true); return; }
  let key = localStorage.getItem("gemini_key") || "";
  if (!key) {
    key = prompt("Paste your Gemini API key (free at aistudio.google.com/apikey):");
    if (key) localStorage.setItem("gemini_key", key.trim());
    if (!key) return;
  }
  try {
    const data = await api("/api/import-latex-ai", { method: "POST", body: { raw_latex: raw, api_key: key.trim() } });
    applyImported(data);
    flashStatus("Imported (AI)");
  } catch (e) {
    if (/401|403|API key not valid/i.test(e.message)) localStorage.removeItem("gemini_key");
    flashStatus(e.message, true);
  }
};

function applyImported(data) {
  const s = data.content || {};
  const hasAny = s.name || (s.education||[]).length || (s.experience||[]).length || (s.projects||[]).length || (s.skills||[]).length;
  current.content = Object.assign(EMPTY_CONTENT(), s);
  if (data.doc_html) {
    current.content.doc_html = data.doc_html;
    $("#doc-editor").innerHTML = data.doc_html;
  } else {
    current.content.doc_html = "";
    $("#doc-editor").innerHTML = structureToHtml(current.content);
  }
  if (hasAny) fillForm();
  setMode("doc");
}

function flashStatus(msg, isErr = false) {
  const el = $("#compile-status");
  el.style.color = isErr ? "#dc2626" : "#16a34a";
  if (isErr) {
    el.textContent = "Error — click for details";
    el.onclick = () => alert(msg);
  } else {
    el.onclick = null;
    el.textContent = msg;
    setTimeout(() => { el.textContent = ""; }, 4000);
  }
}

if (token) enterApp().catch(() => localStorage.clear());
