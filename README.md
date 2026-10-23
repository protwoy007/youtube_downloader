# YT Local Downloader For LaL Vai

A browser extension for **Brave, Chrome and Edge** that adds a **Download** button next to the Subscribe button on YouTube. Click it, pick a quality (or MP3 audio), and the file is saved to your computer. If the helper isn't running, the button starts it for you.

Under the hood, the extension talks to a small helper program on your own PC (`127.0.0.1`), which uses [yt-dlp](https://github.com/yt-dlp/yt-dlp) and [ffmpeg](https://ffmpeg.org/). Nothing goes through a third-party server.

> **Platforms:** Windows 10/11 (`start.bat`) and Linux (`start.sh`). macOS may work with `start.sh`, with a few manual steps (see [Linux and macOS](#linux-and-macos)).
> **Browsers:** Brave, Chrome, Edge (any Chromium browser with Manifest V3).

## Features

- Download button next to Subscribe on every video page (light and dark theme)
- Video: **1080p, 720p, 480p, 360p, Best available** (saved as MP4)
- Audio: **MP3 128 kbps**
- Live progress on the button (`Downloading 42%`, `Processing…`, `✓ Saved`)
- **Click the button and the helper starts automatically** if it is not running (via a `ytdl://` link)
- **Smart retries:** if YouTube only offers low quality or blocks a request, the helper automatically tries other YouTube clients before giving up
- `start.bat` / `start.sh` check every requirement and only install what is missing
- Files saved to `Downloads/YouTube Downloads`

## How it works

```
YouTube page ──click──> Extension ──> Helper (127.0.0.1:9477) ──> yt-dlp + ffmpeg ──> Downloads folder
                            └── helper offline? opens ytdl://start ──> runs helper/start.bat (or start.sh)
```

1. A content script injects the button and quality menu.
2. The extension's background worker sends your choice, plus your YouTube login cookies, to the local helper.
3. The helper runs yt-dlp, merges video and audio with ffmpeg (or converts to MP3), and reports progress back.

### How the helper picks a YouTube client

YouTube limits which clients can get high quality, and some accounts only get 360p from the default clients. So for each download the helper checks the quality that is *actually offered* before downloading, and moves to the next attempt if it is too low:

1. `android_vr` client, **no cookies**
2. `tv` client, with your cookies
3. `tv_simply` / `web_safari` clients, with your cookies
4. Default clients, with your cookies (last resort, accepts any quality)

Without cookies, only attempt 1 and a default-client fallback are used. The helper window prints each attempt (`Attempt 1/4: …`). The yt-dlp **warnings** between attempts are normal: they only explain why an attempt was skipped. As long as a later attempt reports the quality you want, the download is fine.

## Requirements

- Windows 10/11 or Linux
- Internet connection
- About **500 MB** free disk space for the helper tools
- Python 3.9+ (installed automatically with `winget` on Windows if missing; on Linux install `python3`, `python3-venv`, `python3-pip`)
- You should be **logged into YouTube** in the browser you use

## Installation (Windows)

### Step 1: Get the project

```
git clone https://github.com/protwoy007/youtube_downloader.git
```

Or click **Code → Download ZIP** and extract it. You get two folders: `extension/` and `helper/`.

### Step 2: Run the helper once (first-time setup)

Double-click **`helper\start.bat`**. Every run first registers the `ytdl://` link for your Windows user (no admin needed), then runs five checks and skips any that are already satisfied:

| # | Check | If missing | Approx. time on first run* |
|---|-------|-----------|----------------------------|
| 1 | **Python** | Installed with `winget`; then close the window and run `start.bat` again | 2–5 min (skipped if installed) |
| 2 | **Virtual environment** (`helper\.venv`) | Created | under 30 sec |
| 3 | **yt-dlp** | Installed with `pip` | 30 sec – 2 min |
| 4 | **ffmpeg + ffprobe** | Downloaded to `helper\bin` (~150 MB) | 1–5 min, depends on internet speed |
| 5 | **deno** (JS runtime yt-dlp needs for YouTube) | Downloaded to `helper\bin` (~40 MB) | under 1 min |

\* Rough estimates; internet speed matters most.

**Total first-time setup: roughly 5–10 minutes** (3–8 minutes if Python is already installed). Later runs take a few seconds. When it finishes you will see:

```
Starting helper. Keep this window open.
Helper running on 127.0.0.1:9477. Saving to C:\Users\<you>\Downloads\YouTube Downloads
```

Keep that window open while downloading.

> If `winget` isn't available, install Python from [python.org](https://www.python.org/downloads/) and tick **"Add python.exe to PATH"**.
> The link is re-registered on every run. If you move the project folder, just run `start.bat` once from the new location.
> If the helper is already running, `start.bat` says so and exits.
> `start.bat` also writes a small log to `helper\start.log` (ignored by git), useful when something fails.

### Step 3: Load the extension (about 1 minute)

| Browser | Address |
|---------|---------|
| Brave | `brave://extensions` |
| Chrome | `chrome://extensions` |
| Edge | `edge://extensions` |

1. Turn on **Developer mode**.
2. Click **Load unpacked** and select the **`extension`** folder.
3. Accept the permission prompt (it reads YouTube cookies for the helper).
4. Keep the `extension` folder where it is; the browser loads it from there.
5. After reloading the extension later, also **refresh the YouTube tab** (Ctrl+F5), or the old button will stop working.

### Step 4: Use it

1. Open a YouTube video while logged in.
2. Click **⬇ Download** next to Subscribe.
3. **If the helper isn't running**, the browser asks to open an external app. Click **Open** (tick "Always allow" to skip the prompt next time). A helper window opens, and the button says "Starting helper…" until it is ready. Click the button again to cancel the wait.
4. Choose **1080p / 720p / 480p / 360p / Best available**, or **MP3 128 kbps**.
5. Wait for **✓ Saved**. Find the file in `Downloads\YouTube Downloads`.

The button waits up to 2 minutes for the helper. If you skipped Step 2, the very first launch also does the full setup, which can take longer than that: run `helper\start.bat` yourself first.

## Linux and macOS

```
bash helper/start.sh
```

`start.sh` does the same job as `start.bat` in five steps: checks `python3`, creates the virtual environment, **installs/updates yt-dlp on every run** (with browser impersonation support), reports whether ffmpeg and deno are on the system, and registers the `ytdl://` link through `xdg-mime`.

- **ffmpeg and deno** are not downloaded by `start.sh`. The helper downloads them into `helper/bin` on the **first download** if they are missing, so the first download shows "Setting up (first time)…" for a while.
- **macOS:** install ffmpeg yourself with `brew install ffmpeg`. `xdg-mime` doesn't exist on macOS, so the `ytdl://` link isn't registered and the button can't start the helper: run `bash helper/start.sh` manually before downloading.

## Updating yt-dlp

YouTube changes often. If downloads start failing, update yt-dlp.

- **Windows:** from a Command Prompt in the project folder:
  ```
  helper\start.bat update
  ```
- **Linux/macOS:** run `bash helper/start.sh` (it updates every time).

## Troubleshooting

| Problem | Fix |
|---------|-----|
| **"Helper not ready"** | The helper didn't start in 2 minutes. Run `helper\start.bat` yourself and read the error (or check `helper\start.log`). |
| Button says **"Refresh the page (Ctrl+F5)"** | The extension was reloaded. Refresh the YouTube tab. |
| Browser doesn't ask to open an app | Run `helper\start.bat` once manually (it registers the `ytdl://` link), then try again. |
| **429 Too Many Requests** or **"Sign in to confirm you're not a bot"** | YouTube is limiting your IP or session. Stop retrying, wait 30–60 minutes, reload the YouTube tab (logged in), reload the extension, then try once. |
| Only **360p** or **720p** is downloaded | Some accounts only get low quality from YouTube's default clients. The helper already tries other clients (see above). Run `start.bat update` and try again. |
| Button does not appear | Refresh the page and make sure the extension is enabled. YouTube may have changed its layout; the selector in `extension/content.js` (`ytd-watch-metadata #owner`) may need updating. |
| **"Failed"** | Read the message in the helper window, run `start.bat update`, and check the browser console (F12, filter `[ytdl]`). |
| ffmpeg or deno download failed | Check your internet, delete partial files in `helper\bin`, run `start.bat` again. |
| Port 9477 already in use | Another copy of the helper is running; close it. |

## Security and privacy

- The helper listens only on `127.0.0.1`, never on the network.
- It accepts requests only from browser extensions, so websites can't trigger downloads.
- It only accepts `https://www.youtube.com/watch?v=...` links.
- Your YouTube cookies go from the browser to the local helper only. They are written to a temporary file for the duration of one attempt and deleted afterwards. They are never stored in the project, and `.gitignore` excludes cookie files.
- The first download attempt runs **without** cookies. They are only used if that attempt fails or offers low quality.
- To solve YouTube's JavaScript challenges, yt-dlp fetches its solver components from GitHub at download time.
- Using your logged-in cookies for automated downloads carries some risk of YouTube flagging the account. Consider a secondary account.

## Project structure

```
extension/
  manifest.json    Manifest V3, permissions
  content.js       Button, menu, helper auto-start, progress
  content.css      Styling (light and dark)
  background.js    Talks to the helper, attaches YouTube cookies
helper/
  start.bat        Windows: checks requirements, installs what's missing, registers ytdl://, starts the helper
  start.sh         Linux/macOS: same job, installs/updates yt-dlp every run
  server.py        Local server wrapping yt-dlp and ffmpeg, with client retries
```

## Disclaimer

For **personal use** only. Downloading videos may violate YouTube's Terms of Service; only download content you own or have permission to download. You are responsible for how you use this tool. Not affiliated with YouTube or Google. Browser stores won't accept it, so it is installed as an unpacked extension.

## Credits

[yt-dlp](https://github.com/yt-dlp/yt-dlp) · [FFmpeg](https://ffmpeg.org/) (builds from [yt-dlp/FFmpeg-Builds](https://github.com/yt-dlp/FFmpeg-Builds)) · [Deno](https://deno.com/)

## License

Add your preferred license here (for example MIT).
