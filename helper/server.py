import io, json, os, platform, shutil, tarfile, threading, time, urllib.request, uuid, zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

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
    print(f"Downloading {url} ...")
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
                print("ffmpeg not found. Install it with: brew install ffmpeg")
        if not have("deno"):
            fetch_archive(DENO_URL, {"deno" + EXE})
        print("Tools ready.")
    except Exception as e:
        print("Tool setup failed:", e)
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


def run_job(jid, url, mode, height, cookies=None):
    import yt_dlp
    job = jobs[jid]
    ready.wait()
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
        "quiet": True,
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
    # Browser-like TLS fingerprint (needs curl_cffi, installed by start.bat)
    try:
        import curl_cffi  # noqa: F401
        from yt_dlp.networking.impersonate import ImpersonateTarget
        opts["impersonate"] = ImpersonateTarget("chrome")
    except Exception:
        pass

    # JS runtime for YouTube's challenge solving. Without it only a 360p format
    # is exposed. Point yt-dlp straight at the bundled deno.
    deno = shutil.which("deno")
    if deno:
        opts["js_runtimes"] = {"deno": {"path": deno}}
    opts["remote_components"] = ["ejs:github"]

    def classify(err):
        t = str(err)
        if "429" in t or "Too Many Requests" in t:
            return "rate"
        if "not a bot" in t:
            return "bot"
        if "needs to be reloaded" in t:
            return "reload"
        return "other"

    # Your account is in YouTube's SABR-only experiment: the default (web) clients
    # then expose only 360p. So we try clients that do NOT use SABR first, and we
    # check the real quality BEFORE downloading, moving on if it is too low.
    #  1) android_vr, no cookies (no SABR, no PO token, up to 4K)
    #  2) tv client with your cookies
    #  3) tv_simply/web_safari with your cookies
    #  4) default clients with your cookies (last resort, accepts any quality)
    plans = [(False, ["android_vr"])]
    if cookies:
        plans += [(True, ["tv"]), (True, ["tv_simply", "web_safari"]), (True, None)]
    else:
        plans += [(False, None)]
    want = min(height, 720) if height else 720
    errors = []

    for i, (use_cookies, clients) in enumerate(plans):
        last_plan = i == len(plans) - 1
        if i:
            job.update(state="preparing", percent=0)
            time.sleep(3)
        o = dict(opts)
        if clients:
            o["extractor_args"] = {"youtube": {"player_client": clients}}
        cfile = None
        if use_cookies:
            cfile = HERE / f"cookies_{jid}.txt"
            write_cookie_file(cfile, cookies)
            o["cookiefile"] = str(cfile)
        label = ("cookies" if use_cookies else "no cookies") + " / " + (",".join(clients) if clients else "default clients")
        print(f"Attempt {i + 1}/{len(plans)}: {label}")
        try:
            with yt_dlp.YoutubeDL(o) as ydl:
                info = ydl.extract_info(url, download=False)
                best = max((f.get("height") or 0 for f in info.get("formats", [])
                            if f.get("vcodec") not in (None, "none")), default=0)
                print(f"  best video quality offered: {best}p")
                if mode == "video" and best < want and not last_plan:
                    errors.append("low")
                    continue
                ydl.process_video_result(info, download=True)
            job.update(state="done", percent=100)
            return
        except Exception as e:
            kind = classify(e)
            errors.append(kind)
            print(f"Attempt failed ({kind}):", e)
        finally:
            if cfile:
                cfile.unlink(missing_ok=True)

    if "rate" in errors or "bot" in errors:
        msg = ("YouTube is blocking this IP/session (429 / bot check). Stop retrying, "
               "wait 30-60 minutes, reload the YouTube tab (logged in), reload the extension, then try once.")
    elif "reload" in errors:
        msg = "YouTube rejected the login cookies. Reload the YouTube page, then try again."
    else:
        msg = "Download failed. Run start.bat (Windows) or start.sh (Linux) to update yt-dlp, then try again."
    print("FAILED:", msg)
    job.update(state="error", error=msg)


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
    print(f"Helper running on 127.0.0.1:{PORT}. Saving to {OUT}")
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
