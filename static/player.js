// Player page: load VTT, render list, sync highlight, jump-to-time on click.
(async function () {
  const media = document.getElementById("media");
  const live = document.getElementById("cc-live");
  const rows = document.getElementById("caption-rows");
  const cfg = window.__CC;

  if (cfg.startAt && media) {
    media.addEventListener("loadedmetadata", () => { media.currentTime = cfg.startAt; media.play().catch(() => {}); });
  }
  if (!cfg.vttUrl || !rows) return;

  function parseVtt(txt) {
    const lines = txt.replace(/\r/g, "").split("\n");
    const cues = [];
    let i = 0;
    if (lines[0].startsWith("WEBVTT")) i++;
    while (i < lines.length) {
      const line = lines[i].trim();
      if (line.includes("-->")) {
        const [s, e] = line.split("-->").map(x => x.trim());
        const text = [];
        i++;
        while (i < lines.length && lines[i].trim() !== "") { text.push(lines[i]); i++; }
        cues.push({ start: toSec(s), end: toSec(e), text: text.join(" ") });
      }
      i++;
    }
    return cues;
  }
  function toSec(t) {
    const [h, m, s] = t.split(":");
    if (s === undefined) return parseFloat(h) * 60 + parseFloat(m);
    return parseInt(h) * 3600 + parseInt(m) * 60 + parseFloat(s);
  }
  function fmt(sec) {
    const m = Math.floor(sec / 60), s = Math.floor(sec % 60);
    return String(m).padStart(2, "0") + ":" + String(s).padStart(2, "0");
  }

  const txt = await fetch(cfg.vttUrl).then(r => r.text());
  const cues = parseVtt(txt);

  rows.innerHTML = cues.map((c, i) => {
    const kind = c.text.trim().startsWith("[") ? "sound" : "speech";
    return `<div class="cap-row ${kind}" data-i="${i}" data-start="${c.start}">
      <span class="ts">${fmt(c.start)}</span>
      <span class="text">${c.text.replace(/</g, "&lt;")}</span>
    </div>`;
  }).join("");

  rows.addEventListener("click", (e) => {
    const r = e.target.closest(".cap-row");
    if (!r) return;
    media.currentTime = parseFloat(r.dataset.start);
    media.play().catch(() => {});
  });

  media.addEventListener("timeupdate", () => {
    const t = media.currentTime;
    let activeIdx = -1;
    for (let i = 0; i < cues.length; i++) {
      if (cues[i].start <= t && t <= cues[i].end + 0.2) { activeIdx = i; break; }
    }
    rows.querySelectorAll(".cap-row.active").forEach(el => el.classList.remove("active"));
    if (activeIdx >= 0) {
      const el = rows.querySelector(`.cap-row[data-i="${activeIdx}"]`);
      if (el) { el.classList.add("active"); el.scrollIntoView({ block: "nearest" }); }
      if (live) live.textContent = cues[activeIdx].text;
    } else if (live) {
      live.textContent = "";
    }
  });
})();
