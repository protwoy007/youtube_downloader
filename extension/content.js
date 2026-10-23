const ID = "ytdl-wrap";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// Safe wrapper: returns {invalid:true} if the extension was reloaded and this page is stale
async function send(msg) {
  try {
    if (!chrome.runtime?.id) return { ok: false, invalid: true };
    return (await chrome.runtime.sendMessage(msg)) || { ok: false };
  } catch (e) {
    return { ok: false, invalid: true };
  }
}

function videoUrl() {
  const v = new URL(location.href).searchParams.get("v");
  return v ? `https://www.youtube.com/watch?v=${v}` : null;
}

// Runs start.bat through the ytdl:// link (registered by start.bat)
function launchHelper() {
  const a = document.createElement("a");
  a.href = "ytdl://start";
  a.style.display = "none";
  document.body.appendChild(a);
  a.click();
  a.remove();
}

function build() {
  const wrap = document.createElement("div");
  wrap.id = ID;
  wrap.innerHTML = `
    <button id="ytdl-btn">⬇ Download</button>
    <div id="ytdl-menu">
      <div class="h">VIDEO</div>
      <div class="i" data-m="video" data-h="1080">1080p</div>
      <div class="i" data-m="video" data-h="720">720p</div>
      <div class="i" data-m="video" data-h="480">480p</div>
      <div class="i" data-m="video" data-h="360">360p</div>
      <div class="i" data-m="video" data-h="0">Best available</div>
      <div class="h">AUDIO</div>
      <div class="i" data-m="audio" data-h="0">MP3 128 kbps</div>
    </div>`;
  const btn = wrap.querySelector("#ytdl-btn");
  const menu = wrap.querySelector("#ytdl-menu");
  let busy = false;
  let waiting = false;

  const IDLE = "⬇ Download";
  function reset(ms) {
    setTimeout(() => { busy = false; btn.textContent = IDLE; }, ms);
  }

  // returns "ok" | "invalid" | "timeout" | "cancel"
  async function ensureHelper() {
    let r = await send({ type: "ping" });
    if (r.invalid) return "invalid";
    if (r.ok) return "ok";
    btn.textContent = "Starting helper… (click to cancel)";
    launchHelper();
    waiting = true;
    for (let i = 0; i < 120; i++) { // wait up to 2 min
      await sleep(1000);
      if (!waiting) return "cancel";
      r = await send({ type: "ping" });
      if (r.ok) { waiting = false; return "ok"; }
      if (i === 10) btn.textContent = "Waiting for helper window… (click to cancel)";
    }
    waiting = false;
    return "timeout";
  }

  btn.onclick = async (e) => {
    e.stopPropagation();
    if (waiting) { // cancel waiting
      waiting = false; busy = false; btn.textContent = IDLE; return;
    }
    if (busy) return;
    if (menu.classList.contains("open")) return menu.classList.remove("open");
    busy = true;
    const res = await ensureHelper();
    if (res === "cancel") return;
    if (res === "invalid") { btn.textContent = "Refresh the page (Ctrl+F5)"; return reset(5000); }
    if (res === "timeout") { btn.textContent = "Helper not ready – click to retry"; return reset(4000); }
    busy = false;
    btn.textContent = IDLE;
    menu.classList.add("open");
  };

  menu.querySelectorAll(".i").forEach((el) => {
    el.onclick = async () => {
      menu.classList.remove("open");
      const url = videoUrl();
      if (!url) return;
      busy = true;
      btn.textContent = "Starting…";
      const r = await send({ type: "start", url, mode: el.dataset.m, height: +el.dataset.h });
      if (r.invalid) { btn.textContent = "Refresh the page (Ctrl+F5)"; return reset(5000); }
      if (!r.ok) { btn.textContent = "Helper offline"; return reset(4000); }
      poll(r.id);
    };
  });

  async function poll(id) {
    const r = await send({ type: "status", id });
    if (!r.ok) { btn.textContent = "Helper offline"; return reset(3000); }
    if (r.state === "preparing") btn.textContent = "Setting up (first time)…";
    else if (r.state === "downloading") btn.textContent = `Downloading ${r.percent}%`;
    else if (r.state === "processing") btn.textContent = "Processing…";
    else if (r.state === "done") { btn.textContent = "✓ Saved"; return reset(3000); }
    else if (r.state === "error") { btn.textContent = "Failed"; console.error("[ytdl]", r.error); return reset(4000); }
    setTimeout(() => poll(id), 700);
  }
  return wrap;
}

function inject() {
  if (!videoUrl() || document.getElementById(ID)) return;
  const owner = document.querySelector("ytd-watch-metadata #owner");
  if (owner) owner.appendChild(build());
}

document.addEventListener("click", () => {
  document.getElementById("ytdl-menu")?.classList.remove("open");
});
new MutationObserver(inject).observe(document.body, { childList: true, subtree: true });
document.addEventListener("yt-navigate-finish", () => {
  document.getElementById(ID)?.remove();
  inject();
});
inject();
