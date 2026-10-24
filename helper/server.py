import importlib, io, json, os, platform, re, shutil, subprocess, sys, tarfile, threading, time, urllib.request, uuid, zipfile
from importlib import metadata
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# Titles can contain any language; never crash on a console that can't print them
for _st in (sys.stdout, sys.stderr):
    try:
        _st.reconfigure(errors="replace")
    except Exception:
        pass


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


HERE = Path(__file__).parent.resolve()
BIN = HERE / "bin"
OUT = Path.home() / "Downloads" / "YouTube Downloads"
PORT = 9477

SYSTEM = platform.system()            # Windows / Linux / Darwin
IS_WIN = SYSTEM == "Windows"
EXE = ".exe" if IS_WIN else ""
ARM = platform.machine().lower() in ("aarch64", "arm64")

FF_BASE = "https://github.com/yt-dlp/FFmpeg-Builds/releases/latest/download/"
DENO_BASE = "https://github.com/denoland/deno/releases/latest/download/"
if IS_WIN:
    FFMPEG_URL = FF_BASE + "ffmpeg-master-latest-win64-gpl.zip"
    DENO_URL = DENO_BASE + "deno-x86_64-pc-windows-msvc.zip"
elif SYSTEM == "Linux":
    FFMPEG_URL = FF_BASE + ("ffmpeg-master-latest-linuxarm64-gpl.tar.xz" if ARM else "ffmpeg-master-latest-linux64-gpl.tar.xz")
    DENO_URL = DENO_BASE + ("deno-aarch64-unknown-linux-gnu.zip" if ARM else "deno-x86_64-unknown-linux-gnu.zip")
else:  # macOS: install ffmpeg with `brew install ffmpeg`
    FFMPEG_URL = None
    DENO_URL = DENO_BASE + ("deno-aarch64-apple-darwin.zip" if ARM else "deno-x86_64-apple-darwin.zip")

BIN.mkdir(exist_ok=True)
OUT.mkdir(parents=True, exist_ok=True)
os.environ["PATH"] = str(BIN) + os.pathsep + os.environ["PATH"]
ready = threading.Event()
jobs = {}


def fetch_archive(url, wanted):
    """Download a .zip or .tar.xz and extract only the wanted file names into BIN."""
    log(f"Downloading {url.rsplit('/', 1)[-1]} ...")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    data = urllib.request.urlopen(req).read()
    if url.endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            for name in z.namelist():
                base = name.rsplit("/", 1)[-1]
                if base in wanted:
                    (BIN / base).write_bytes(z.read(name))
    else:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:xz") as t:
            for m in t.getmembers():
                base = m.name.rsplit("/", 1)[-1]
                if m.isfile() and base in wanted:
                    (BIN / base).write_bytes(t.extractfile(m).read())
    for w in wanted:
        f = BIN / w
        if f.exists():
            f.chmod(0o755)


def have(tool):
    return (BIN / (tool + EXE)).exists() or shutil.which(tool)


def setup_tools():
    # Fallback: start.bat / start.sh normally set these up already
    try:
        if not (have("ffmpeg") and have("ffprobe")):
            if FFMPEG_URL:
                fetch_archive(FFMPEG_URL, {"ffmpeg" + EXE, "ffprobe" + EXE})
            else:
                log("ffmpeg not found. Install it with: brew install ffmpeg")
        if not have("deno"):
            fetch_archive(DENO_URL, {"deno" + EXE})
        log("Tools ready.")
    except Exception as e:
        log(f"Tool setup failed: {e}")
    ready.set()


def write_cookie_file(path, cookies):
    lines = ["# Netscape HTTP Cookie File"]
    for c in cookies:
        d = c["domain"]
        lines.append("\t".join([
            d, "TRUE" if d.startswith(".") else "FALSE", c["path"],
            "TRUE" if c["secure"] else "FALSE", str(int(c["expires"])),
            c["name"], c["value"],
        ]))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# kind -> (short text for the button, longer explanation for the tooltip / helper window)
MESSAGES = {
    "rate": ("429: wait 30-60 min", "YouTube is rate-limiting this IP (HTTP 429). Stop retrying, wait 30-60 minutes, then try once."),
    "bot": ("Bot check: reload YouTube", "YouTube asked to confirm you are not a bot. Log in, reload the YouTube tab and the extension, then try once."),
    "reload": ("Cookies expired: reload page", "YouTube rejected the login cookies. Reload the YouTube page and try again."),
    "private": ("Private video", "This video is private. Log in with an account that can watch it, then reload the YouTube tab."),
    "members": ("Members-only video", "This video is for channel members only."),
    "age": ("Age-restricted: log in", "This video is age-restricted. Log in to YouTube in this browser and reload the tab."),
    "region": ("Blocked in your country", "YouTube says this video is not available in your country."),
    "unavailable": ("Video unavailable", "This video is unavailable (removed, deleted or blocked)."),
    "live": ("Live stream: not supported", "Live streams and upcoming premieres can't be downloaded until they finish."),
    "network": ("No internet connection", "Could not reach YouTube. Check your internet connection."),
    "ffmpeg": ("ffmpeg missing", "ffmpeg/ffprobe not found. Delete helper/bin and run start.bat (or start.sh) again."),
    "format": ("Quality not available", "The requested quality is not available for this video. Try another quality."),
    "low": ("Only low quality offered", "YouTube only offered low quality for this video right now."),
    "other": ("Failed - see helper window", "Download failed for an unknown reason. See the helper window."),
}

# (substrings are lower-case; first matching rule wins, so order matters)
RULES = [
    ("rate", ("429", "too many requests")),
    ("bot", ("not a bot",)),
    ("reload", ("needs to be reloaded",)),
    ("private", ("private video",)),
    ("members", ("members-only", "members only", "join this channel")),
    ("age", ("confirm your age", "age-restricted", "age restricted")),
    ("region", ("in your country", "geo restrict", "geo-restrict")),
    ("live", ("live event", "is live", "premieres in", "this live")),
    ("format", ("requested format is not available",)),
    ("unavailable", ("video unavailable", "not available", "has been removed", "been terminated")),
    ("network", ("getaddrinfo", "name resolution", "network is unreachable", "unable to connect",
                 "timed out", "connection reset", "no route to host", "failed to resolve",
                 "name or service not known")),
    ("ffmpeg", ("ffmpeg", "ffprobe")),
]
ALWAYS_FATAL = {"rate", "network", "ffmpeg", "live"}          # trying another client won't help
NEEDS_LOGIN = {"private", "members", "age", "region", "unavailable"}  # fatal only if cookies were already used
UPDATABLE = {"other", "format"}                               # often fixed by a newer yt-dlp


def classify(err):
    t = str(err).lower()
    for kind, needles in RULES:
        if any(n in t for n in needles):
            return kind
    return "other"


def short_err(e):
    s = re.sub(r"^ERROR:\s*(\[[^\]]+\]\s*)?([\w-]{11}:\s*)?", "", str(e).strip())
    return s.replace("\n", " ")[:160]


class _Quiet:
    """Silence yt-dlp's own output; the helper prints its own short status lines."""
    def debug(self, m): pass
    def info(self, m): pass
    def warning(self, m): pass
    def error(self, m): pass


_update_lock = threading.Lock()
_last_update = 0.0


def update_ytdlp():
    """Upgrade yt-dlp with pip and reload it. True only if a newer version was installed."""
    global _last_update
    with _update_lock:
        if time.time() - _last_update < 3600:
            log("yt-dlp was already checked in the last hour, not updating again.")
            return False
        _last_update = time.time()
        try:
            before = metadata.version("yt-dlp")
            log(f"Updating yt-dlp (current {before}) ...")
            r = subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-U", "yt-dlp[default]"],
                               capture_output=True, text=True, timeout=240)
            if r.returncode != 0:
                log("Update failed: " + (r.stderr.strip().splitlines() or ["pip error"])[-1][:160])
                return False
            importlib.invalidate_caches()
            for m in [m for m in sys.modules if m == "yt_dlp" or m.startswith(("yt_dlp.", "yt_dlp_ejs"))]:
                del sys.modules[m]
            after = metadata.version("yt-dlp")
            if after == before:
                log(f"yt-dlp is already the latest version ({after}).")
                return False
            log(f"yt-dlp updated {before} -> {after}.")
            return True
        except Exception as e:
            log(f"Update failed: {e}")
            return False


def try_download(jid, url, mode, height, cookies):
    """One full pass over all methods. Returns (True, None) or (False, error_kind)."""
    import yt_dlp
    job = jobs[jid]
    seen = []
    expected = 2 if mode == "video" else 1

    def hook(d):
        if d["status"] == "downloading":
            fn = d.get("filename")
            if fn not in seen:
                seen.append(fn)
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            frac = d["downloaded_bytes"] / total if total else 0
            overall = (min(len(seen) - 1, expected - 1) + frac) / expected
            job.update(state="downloading", percent=int(overall * 100))
        elif d["status"] == "finished":
            job["state"] = "processing"

    opts = {
        "outtmpl": str(OUT / "%(title)s.%(ext)s"),
        "noplaylist": True,
        "logger": _Quiet(),
        "no_warnings": True,
        "progress_hooks": [hook],
    }
    if (BIN / ("ffmpeg" + EXE)).exists():
        opts["ffmpeg_location"] = str(BIN)
    if IS_WIN:
        opts["windowsfilenames"] = True
    if mode == "audio":
        opts.update(
            format="bestaudio/best",
            postprocessors=[{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "128"}],
        )
    else:
        h = f"[height<={height}]" if height else ""
        opts.update(
            format=f"bv*{h}+ba/b{h}",
            format_sort=["res", "vcodec:h264", "acodec:aac"],
            merge_output_format="mp4",
            outtmpl=str(OUT / "%(title)s [%(height)sp].%(ext)s"),
        )

    # Fewer / slower requests + automatic retries help against HTTP 429
    opts.update(
        retries=10,
        extractor_retries=5,
        fragment_retries=10,
        file_access_retries=5,
        socket_timeout=30,
        sleep_interval_requests=1,
        concurrent_fragment_downloads=1,
    )
    # Browser-like TLS fingerprint (needs curl_cffi)
    try:
        import curl_cffi  # noqa: F401
        from yt_dlp.networking.impersonate import ImpersonateTarget
        opts["impersonate"] = ImpersonateTarget("chrome")
    except Exception:
        pass

    # JS runtime for YouTube's challenge solving. Without it only a 360p format is exposed.
    deno = shutil.which("deno")
    if deno:
        opts["js_runtimes"] = {"deno": {"path": deno}}
    opts["remote_components"] = ["ejs:github"]

    # Accounts in YouTube's SABR-only experiment get only 360p from the default clients,
    # so we try other clients first and check the real quality BEFORE downloading.
    #  1) android_vr, no cookies   2) tv + cookies   3) tv_simply/web_safari + cookies
    #  4) default clients + cookies (last resort, accepts any quality)
    plans = [(False, ["android_vr"])]
    if cookies:
        plans += [(True, ["tv"]), (True, ["tv_simply", "web_safari"]), (True, None)]
    else:
        plans += [(False, None)]
    want = min(height, 720) if height else 720
    kinds = []

    for i, (use_cookies, clients) in enumerate(plans):
        last_plan = i == len(plans) - 1
        if i:
            job.update(state="preparing", percent=0, note=f"Trying method {i + 1}/{len(plans)}…")
            time.sleep(3)
        o = dict(opts)
        if clients:
            o["extractor_args"] = {"youtube": {"player_client": clients}}
        cfile = None
        if use_cookies:
            cfile = HERE / f"cookies_{jid}.txt"
            write_cookie_file(cfile, cookies)
            o["cookiefile"] = str(cfile)
        label = ",".join(clients) if clients else "default clients"
        label += " (cookies)" if use_cookies else " (no cookies)"
        log(f"Method {i + 1}/{len(plans)}: {label}")
        try:
            with yt_dlp.YoutubeDL(o) as ydl:
                info = ydl.extract_info(url, download=False)
                best = max((f.get("height") or 0 for f in info.get("formats", [])
                            if f.get("vcodec") not in (None, "none")), default=0)
                if mode == "video" and best < want and not last_plan:
                    log(f"  only {best}p offered, trying next method")
                    kinds.append("low")
                    continue
                log(f"  {best}p offered, downloading")
                ydl.process_video_result(info, download=True)
            log(f"Saved: {info.get('title', url)}")
            return True, None
        except Exception as e:
            kind = classify(e)
            kinds.append(kind)
            log(f"  failed ({kind}): {short_err(e)}")
            if kind in ALWAYS_FATAL or (kind in NEEDS_LOGIN and (use_cookies or not cookies)):
                break
        finally:
            if cfile:
                cfile.unlink(missing_ok=True)

    real = [k for k in kinds if k != "low"]
    return False, (real[-1] if real else "low")


def run_job(jid, url, mode, height, cookies=None):
    job = jobs[jid]
    ready.wait()
    what = "MP3 128k" if mode == "audio" else (f"{height}p" if height else "best quality")
    log(f"Request: {what} ({url.rsplit('=', 1)[-1]})")
    ok, kind = try_download(jid, url, mode, height, cookies)
    if not ok and kind in UPDATABLE:
        job.update(state="preparing", percent=0, note="Updating yt-dlp…")
        if update_ytdlp():
            job.update(note="Retrying after update…")
            log("Retrying once with the updated yt-dlp ...")
            ok, kind = try_download(jid, url, mode, height, cookies)
    if ok:
        job.update(state="done", percent=100)
        return
    short, long = MESSAGES.get(kind, MESSAGES["other"])
    log(f"FAILED ({kind}): {long}")
    job.update(state="error", error=long, short=short)


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _allowed(self):
        return self.headers.get("Origin", "").startswith("chrome-extension://")

    def _send(self, code, obj=None):
        self.send_response(code)
        if self._allowed():
            self.send_header("Access-Control-Allow-Origin", self.headers.get("Origin"))
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        if obj is not None:
            self.wfile.write(json.dumps(obj).encode())

    def do_OPTIONS(self):
        self._send(204 if self._allowed() else 403)

    def do_POST(self):
        if not self._allowed():
            return self._send(403, {"error": "forbidden"})
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        if self.path == "/ping":
            return self._send(200, {"pong": True})
        if self.path == "/start":
            url = body.get("url", "")
            if not url.startswith("https://www.youtube.com/watch?v="):
                return self._send(400, {"error": "bad url"})
            jid = uuid.uuid4().hex
            jobs[jid] = {"state": "preparing" if not ready.is_set() else "downloading", "percent": 0}
            threading.Thread(
                target=run_job,
                args=(jid, url, body.get("mode"), int(body.get("height") or 0), body.get("cookies")),
                daemon=True,
            ).start()
            return self._send(200, {"id": jid})
        if self.path == "/status":
            job = jobs.get(body.get("id"))
            if job and job["state"] == "downloading" and not ready.is_set():
                job["state"] = "preparing"
            return self._send(200, job or {"state": "error", "error": "unknown job"})
        self._send(404, {"error": "not found"})


if __name__ == "__main__":
    threading.Thread(target=setup_tools, daemon=True).start()
    log(f"Helper running on 127.0.0.1:{PORT}. Saving to {OUT}")
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
