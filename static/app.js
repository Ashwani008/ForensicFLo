// Forensic Flo — sidebar keyword filters drive the List View.
const $ = (s) => document.querySelector(s);
const $$ = (s) => Array.from(document.querySelectorAll(s));
const status = $("#status");

const tags = [];
let lastMatches = {};   // media filename -> {matches, keywords}
let currentMatched = null; // Set of names from last keyword search, or null = no keyword filter

// ---------- Pagination ----------
const PAGE_SIZE = 10;
const scopePager = { page: 1 };
const libPager = { page: 1 };

function renderPagerControl(container, total, state, onChange) {
  if (!container) return;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  if (state.page > totalPages) state.page = totalPages;
  if (state.page < 1) state.page = 1;
  const start = total === 0 ? 0 : (state.page - 1) * PAGE_SIZE + 1;
  const end = Math.min(total, state.page * PAGE_SIZE);
  const maxBtns = 5;
  let first = Math.max(1, state.page - 2);
  let last = Math.min(totalPages, first + maxBtns - 1);
  first = Math.max(1, last - maxBtns + 1);
  const btns = [];
  btns.push(`<button data-page="prev" ${state.page<=1?'disabled':''}>&larr; Prev</button>`);
  for (let p = first; p <= last; p++) {
    btns.push(`<button data-page="${p}" class="${p===state.page?'active':''}">${p}</button>`);
  }
  btns.push(`<button data-page="next" ${state.page>=totalPages?'disabled':''}>Next &rarr;</button>`);
  container.innerHTML =
    `<span class="pg-info">${start}\u2013${end} of ${total}</span>` +
    `<span class="pg-btns">${btns.join("")}</span>`;
  container.querySelectorAll("button").forEach(b => {
    b.addEventListener("click", () => {
      const v = b.dataset.page;
      if (v === "prev") state.page = Math.max(1, state.page - 1);
      else if (v === "next") state.page = Math.min(totalPages, state.page + 1);
      else state.page = Number(v);
      onChange();
    });
  });
}

function renderScopePage() {
  const rows = $$(".scope-list .scope-row");
  const total = rows.length;
  const start = (scopePager.page - 1) * PAGE_SIZE;
  const end = start + PAGE_SIZE;
  rows.forEach((r, i) => {
    r.classList.toggle("page-hidden", !(i >= start && i < end));
  });
  renderPagerControl($("#scope-pager"), total, scopePager, renderScopePage);
}

function renderLibPage() {
  const all = $$("#lib-body tr").filter(tr => !tr.classList.contains("match-row"));
  const visible = all.filter(tr => !tr.classList.contains("hidden-row"));
  const total = visible.length;
  const start = (libPager.page - 1) * PAGE_SIZE;
  const end = start + PAGE_SIZE;
  all.forEach(tr => tr.classList.remove("page-hidden"));
  visible.forEach((tr, i) => {
    if (i < start || i >= end) {
      tr.classList.add("page-hidden");
      // Collapse any expanded match-row beneath a hidden row.
      const next = tr.nextElementSibling;
      if (next && next.classList.contains("match-row")) next.remove();
      tr.classList.remove("revealed");
    }
  });
  renderPagerControl($("#lib-pager"), total, libPager, renderLibPage);
}

function fmtTs(sec) {
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = Math.floor(sec % 60);
  return (h ? String(h).padStart(2, "0") + ":" : "") +
         String(m).padStart(2, "0") + ":" + String(s).padStart(2, "0");
}

function renderTags() {
  $("#tags").innerHTML = tags.map((t, i) =>
    `<span class="tag" data-i="${i}">${t}<button type="button" class="tag-x" data-i="${i}" aria-label="Remove">&times;</button></span>`
  ).join("");
  $("#tags").querySelectorAll(".tag-x").forEach(btn => {
    btn.addEventListener("click", () => {
      tags.splice(Number(btn.dataset.i), 1);
      renderTags();
      runSearch();
    });
  });
}

function addTagsFromInput(commit) {
  const raw = $("#q").value;
  const parts = raw.split(",").map(s => s.trim()).filter(Boolean);
  if (!parts.length) return false;
  if (!commit && !raw.includes(",")) return false;
  let added = false;
  parts.forEach(p => {
    if (!tags.includes(p)) { tags.push(p); added = true; }
  });
  $("#q").value = "";
  if (added) renderTags();
  return added;
}

function highlight(text, keywords) {
  if (!keywords || !keywords.length) return text;
  const re = new RegExp(
    "(" + keywords.map(k => k.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|") + ")",
    "ig"
  );
  return text.replace(re, "<mark>$1</mark>");
}

function clearExpandedRows() {
  $$(".match-row").forEach(r => r.remove());
  $$("#lib-body tr.revealed").forEach(r => r.classList.remove("revealed"));
}

function setRowVisible(tr, visible) {
  tr.classList.toggle("hidden-row", !visible);
}

function getDateRange() {
  const from = document.getElementById("date-from")?.value || "";
  const to   = document.getElementById("date-to")?.value   || "";
  return { from, to };
}

function rowPassesDate(tr, range) {
  if (!range.from && !range.to) return true;
  const d = tr.dataset.date || "";
  if (!d) return false;
  if (range.from && d < range.from) return false;
  if (range.to   && d > range.to)   return false;
  return true;
}

function applyFilters() {
  const range = getDateRange();
  let shown = 0;
  $$("#lib-body tr").forEach(tr => {
    if (tr.classList.contains("match-row")) return;
    const okName = !currentMatched || currentMatched.has(tr.dataset.name);
    const okDate = rowPassesDate(tr, range);
    const visible = okName && okDate;
    setRowVisible(tr, visible);
    if (visible) shown++;
  });
  const rc = document.getElementById("result-count");
  if (rc) rc.textContent = String(shown);
  libPager.page = 1;
  renderLibPage();
}

function showAllRows() {
  currentMatched = null;
  applyFilters();
}

async function runSearch() {
  addTagsFromInput(true);
  clearExpandedRows();
  lastMatches = {};
  if (!tags.length) {
    showAllRows();
    status.textContent = "";
    return;
  }
  const scope = $$(".scope-pick:checked").map(cb => cb.dataset.name);
  const kinds = $$(".kind-pick:checked").map(cb => cb.dataset.kind);
  const allKinds = $$(".kind-pick").length;
  status.textContent = scope.length
    ? `searching ${scope.length} file(s)…`
    : "searching whole library…";
  const params = new URLSearchParams({ q: tags.join(",") });
  if (scope.length) params.set("media", scope.join(","));
  if (kinds.length && kinds.length < allKinds) params.set("kinds", kinds.join(","));
  const r = await fetch("/api/search?" + params.toString());
  const data = await r.json();

  const matched = new Set((data.results || []).map(f => f.media));
  const kws = data.keywords || tags;
  (data.results || []).forEach(f => {
    lastMatches[f.media] = { matches: f.matches || [], keywords: kws };
  });
  currentMatched = matched;
  applyFilters();
  status.textContent = `${data.result_count} file(s) match`;
}

$("#go").addEventListener("click", runSearch);
$("#clear").addEventListener("click", () => {
  tags.length = 0;
  $("#q").value = "";
  renderTags();
  clearExpandedRows();
  lastMatches = {};
  const f = document.getElementById("date-from");
  const t = document.getElementById("date-to");
  if (f) f.value = "";
  if (t) t.value = "";
  showAllRows();
  status.textContent = "";
});
$("#q").addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    e.preventDefault();
    addTagsFromInput(true);
    runSearch();
  } else if (e.key === "Backspace" && !$("#q").value && tags.length) {
    tags.pop();
    renderTags();
    runSearch();
  }
});
$("#q").addEventListener("input", () => {
  if ($("#q").value.includes(",")) addTagsFromInput(false);
});
$("#tag-input").addEventListener("click", () => $("#q").focus());

// Scope (per-file) picker
const scopeAll = $("#scope-all");
const scopePicks = () => $$(".scope-pick:not(:disabled)");
if (scopeAll) {
  scopeAll.addEventListener("change", () => {
    scopePicks().forEach(cb => { cb.checked = scopeAll.checked; });
    if (tags.length) runSearch();
  });
}
$$(".scope-pick").forEach(cb => {
  cb.addEventListener("change", () => {
    const all = scopePicks();
    const checked = all.filter(c => c.checked);
    if (scopeAll) scopeAll.checked = all.length > 0 && checked.length === all.length;
    if (tags.length) runSearch();
  });
});
$$(".kind-pick").forEach(cb => {
  cb.addEventListener("change", () => { if (tags.length) runSearch(); });
});

// ---------- Hide/Show filters sidebar ----------
const toggleBtn = document.getElementById("toggle-filters");
if (toggleBtn) {
  toggleBtn.addEventListener("click", () => {
    const main = document.getElementById("ur-main");
    const hidden = main.classList.toggle("no-sidebar");
    toggleBtn.innerHTML = (hidden ? "&#8645; Show Filters" : "&#8645; Hide Filters");
  });
}

// ---------- View-mode toggle (visual state only) ----------
$$(".view-toggle .vt-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    $$(".view-toggle .vt-btn").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
  });
});

// ---------- Refresh ----------
const reindex = document.getElementById("reindex");
if (reindex) reindex.addEventListener("click", () => location.reload());

// ---------- Select-all in table ----------
const selAll = document.getElementById("sel-all");
if (selAll) {
  selAll.addEventListener("change", () => {
    $$("#lib-body .row-check").forEach(cb => {
      if (cb.closest("tr").classList.contains("hidden-row")) return;
      cb.checked = selAll.checked;
    });
  });
}

// ===== Floating Player =====
const fp = document.getElementById("float-player");
const fpBody = document.getElementById("fp-body");
const fpMedia = document.getElementById("fp-media");
const fpFilename = document.getElementById("fp-filename");
const fpDate = document.getElementById("fp-date");

function openFloatingPlayer(name, captureDate, startTime) {
  const ext = name.split(".").pop().toLowerCase();
  const isVideo = ["mp4", "mkv", "mov", "avi", "webm"].includes(ext);

  fpFilename.textContent = name;
  fpDate.textContent = captureDate || "—";

  fpMedia.innerHTML = "";
  const el = document.createElement(isVideo ? "video" : "audio");
  el.controls = true;
  el.preload = "metadata";
  el.src = "/media/" + encodeURIComponent(name);
  if (isVideo) {
    const track = document.createElement("track");
    track.kind = "captions";
    track.label = "Captions";
    track.srclang = "en";
    track.src = "/captions/" + name.replace(/\.[^.]+$/, ".vtt");
    track.default = true;
    el.appendChild(track);
  }
  if (startTime) {
    el.addEventListener("loadedmetadata", () => { el.currentTime = startTime; }, { once: true });
  }
  fpMedia.appendChild(el);

  fp.classList.remove("fp-minimized", "fp-maximized");
  fp.classList.add("fp-visible");
  fpBody.style.display = "";
  el.play().catch(() => {});
}

document.getElementById("fp-close").addEventListener("click", () => {
  fp.classList.remove("fp-visible", "fp-minimized", "fp-maximized");
  fpMedia.innerHTML = "";
});

document.getElementById("fp-min").addEventListener("click", () => {
  const minimized = fp.classList.toggle("fp-minimized");
  fp.classList.remove("fp-maximized");
  if (minimized) fp.style.transform = "";
});

document.getElementById("fp-max").addEventListener("click", () => {
  const wasMax = fp.classList.contains("fp-maximized");
  fp.classList.remove("fp-minimized");
  if (wasMax) {
    fp.classList.remove("fp-maximized");
    fp.style.cssText = "";
  } else {
    fp.classList.add("fp-maximized");
    fp.style.cssText = "";
  }
});

(function () {
  const header = document.getElementById("fp-header");
  let dragging = false, ox = 0, oy = 0;
  header.addEventListener("mousedown", (e) => {
    if (fp.classList.contains("fp-maximized")) return;
    dragging = true;
    const rect = fp.getBoundingClientRect();
    ox = e.clientX - rect.left;
    oy = e.clientY - rect.top;
    fp.style.right = "auto"; fp.style.bottom = "auto";
    fp.style.left = rect.left + "px"; fp.style.top = rect.top + "px";
  });
  document.addEventListener("mousemove", (e) => {
    if (!dragging) return;
    fp.style.left = (e.clientX - ox) + "px";
    fp.style.top  = (e.clientY - oy) + "px";
  });
  document.addEventListener("mouseup", () => { dragging = false; });
})();

$$(".row-play").forEach(btn => {
  btn.addEventListener("click", () => {
    openFloatingPlayer(btn.dataset.name, btn.dataset.date || "");
  });
});

// ---------- Action button: toggle matches detail row ----------
function buildMatchHtml(name) {
  const info = lastMatches[name];
  if (!info || !info.matches.length) {
    return `<div class="no-matches">No matches \u2014 run a keyword search first.</div>`;
  }
  const kws = info.keywords;
  const seen = new Set();
  const unique = info.matches.filter(m => {
    const key = `${m.kind}|${m.start}|${(m.snippet || "").replace(/\.\s*Objects:.*$/i, "").trim()}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
  return unique.map(m => `
    <div class="match">
      <span class="kind ${m.kind}">${m.kind}</span>
      <a class="ts" href="#" data-name="${name}" data-start="${m.start}" data-date="">${fmtTs(m.start)}</a>
      <span class="snippet">${highlight((m.snippet || "").replace(/\.\s*Objects:.*$/i, ""), kws)}</span>
    </div>
  `).join("");
}

$$(".row-action").forEach(btn => {
  btn.addEventListener("click", (e) => {
    e.stopPropagation();
    const tr = btn.closest("tr");
    if (!tr) return;
    const name = btn.dataset.name;
    const next = tr.nextElementSibling;
    if (tr.classList.contains("revealed") && next && next.classList.contains("match-row")) {
      next.remove();
      tr.classList.remove("revealed");
      return;
    }
    const colCount = tr.children.length;
    const detail = document.createElement("tr");
    detail.className = "match-row";
    detail.innerHTML = `<td colspan="${colCount}">${buildMatchHtml(name)}</td>`;
    tr.after(detail);
    tr.classList.add("revealed");
  });
});

// ---------- Timestamp link -> floating player ----------
document.addEventListener("click", (e) => {
  const a = e.target.closest("a.ts");
  if (!a) return;
  e.preventDefault();
  const matchDiv = a.closest(".match");
  const matchRow = a.closest(".match-row");
  if (!matchRow) return;
  const tr = matchRow.previousElementSibling;
  const name = a.dataset.name;
  const start = parseFloat(a.dataset.start) || 0;
  const date = tr ? (tr.dataset.date || "") : "";
  openFloatingPlayer(name, date, start);
});

// ---------- Initial pagination ----------
renderScopePage();
renderLibPage();

// ---------- Date filter wiring ----------
["date-from", "date-to"].forEach(id => {
  const el = document.getElementById(id);
  if (el) el.addEventListener("change", applyFilters);
});
const dateClear = document.getElementById("date-clear");
if (dateClear) dateClear.addEventListener("click", () => {
  const f = document.getElementById("date-from");
  const t = document.getElementById("date-to");
  if (f) f.value = "";
  if (t) t.value = "";
  applyFilters();
});
