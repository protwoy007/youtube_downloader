# YT Local Downloader

A browser extension for **Brave, Chrome and Edge** that adds a **Download** button next to the Subscribe button on YouTube. Click it, pick a quality (or MP3 audio), and the file is saved to your computer. If the helper isn't running, the button starts it for you.

Under the hood, the extension talks to a small helper program on your own PC (`127.0.0.1`), which uses [yt-dlp](https://github.com/yt-dlp/yt-dlp) and [ffmpeg](https://ffmpeg.org/). Nothing goes through a third-party server.

> **Platform:** Windows 10/11 (the helper is a `.bat` + Python).
> **Browsers:** Brave, Chrome, Edge (any Chromium browser with Manifest V3).

## Features

- Download button next to Subscribe on every video page (light and dark theme)
- Video: **1080p, 720p, 480p, 360p, Best available** (saved as MP4)
- Audio: **MP3 128 kbps**
- Live progress on the button (`Downloading 42%`, `Processing…`, `✓ Saved`)
- **Click the button and the helper starts automatically** if it is not running (via a `ytdl://` link)
- `start.bat` checks every requirement and only installs what is missing
- Files saved to `Downloads\YouTube Downloads`

## How it works

```
YouTube page ──click──> Extension ──> Helper (127.0.0.1:9477) ──> yt-dlp + ffmpeg ──> Downloads folder
                            └── helper offline? opens ytdl://start ──> runs helper\start.bat
```

1. A content script injects the button and quality menu.
2. The extension's background worker sends your choice, plus your YouTube login cookies, to the local helper. The cookies stop YouTube from blocking downloads as "bot" traffic.
3. The helper runs yt-dlp, merges video and audio with ffmpeg (or converts to MP3), and reports progress back.

## Requirements

- Windows 10 or 11
- Internet connection
- About **500 MB** free disk space for the helper tools
- Python 3.9+ (installed automatically with `winget` if missing)
- You should be **logged into YouTube** in the browser you use

## Installation

### Step 1: Get the project

```
git clone https://github.com/<your-username>/<your-repo>.git
```

Or click **Code → Download ZIP** and extract it. You get two folders: `extension/` and `helper/`.

### Step 2: Run the helper once (first-time setup)

Double-click **`helper\start.bat`**. It runs six checks and skips any that are already satisfied:

| # | Check | If missing | Approx. time on first run* |
|---|-------|-----------|----------------------------|
| 1 | **Python** | Installed with `winget`; then close the window and run `start.bat` again | 2–5 min (skipped if installed) |
| 2 | **Virtual environment** (`helper\.venv`) | Created | under 30 sec |
| 3 | **yt-dlp** | Installed with `pip` | 30 sec – 2 min |
| 4 | **ffmpeg + ffprobe** | Downloaded to `helper\bin` (~150 MB) | 1–5 min, depends on internet speed |
| 5 | **deno** (JS runtime yt-dlp needs for YouTube) | Downloaded to `helper\bin` (~40 MB) | under 1 min |
| 6 | **`ytdl://` link** | Registered for your Windows user (no admin needed) | instant |

\* Rough estimates; internet speed matters most.

**Total first-time setup: roughly 5–10 minutes** (3–8 minutes if Python is already installed). Later runs take a few seconds. When it finishes you will see:

```
Starting helper. Keep this window open.
Helper running on 127.0.0.1:9477. Saving to C:\Users\<you>\Downloads\YouTube Downloads
```

Keep that window open while downloading.

> If `winget` isn't available, install Python from [python.org](https://www.python.org/downloads/) and tick **"Add python.exe to PATH"**.
> Step 6 re-registers the link every run. If you move the project folder, just run `start.bat` once from the new location.

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

### Step 4: Use it

1. Open a YouTube video while logged in.
2. Click **⬇ Download** next to Subscribe.
3. **If the helper isn't running**, the browser asks to open an external app. Click **Open** (tick "Always allow" to skip the prompt next time). A helper window opens, and the button says "Starting helper…" until it is ready.
4. Choose **1080p / 720p / 480p / 360p / Best available**, or **MP3 128 kbps**.
5. Wait for **✓ Saved**. Find the file in `Downloads\YouTube Downloads`.

The very first launch from the button also does the full setup from Step 2 if you skipped it, so it can take the 5–10 minutes above. The button keeps waiting for up to 15 minutes.

## Updating yt-dlp

YouTube changes often. If downloads start failing, run from a Command Prompt in the project folder:

```
helper\start.bat update
```

## Troubleshooting

| Problem | Fix |
|---------|-----|
| **"Helper not ready"** | The helper didn't start. Run `helper\start.bat` yourself and read the error. |
| Browser doesn't ask to open an app | Run `helper\start.bat` once manually (it registers the `ytdl://` link), then try again. |
| **429 Too Many Requests** or **"Sign in to confirm you're not a bot"** | Log into YouTube in the same browser, reload the extension and the page. If it persists, your IP is temporarily limited: wait 10–30 minutes. |
| Button does not appear | Refresh the page and make sure the extension is enabled. YouTube may have changed its layout; the selector in `extension/content.js` (`ytd-watch-metadata #owner`) may need updating. |
| **"Failed"** | Run `start.bat update`, then check the helper window and the browser console (F12, filter `[ytdl]`). |
| ffmpeg or deno download failed | Check your internet, delete partial files in `helper\bin`, run `start.bat` again. |
| Port 9477 already in use | Another copy of the helper is running; close it. |

## Security and privacy

- The helper listens only on `127.0.0.1`, never on the network.
- It accepts requests only from browser extensions, so websites can't trigger downloads.
- It only accepts `https://www.youtube.com/watch?v=...` links.
- Your YouTube cookies go from the browser to the local helper only. They are written to a temporary file for the duration of one download and deleted afterwards. They are never stored in the project, and `.gitignore` excludes cookie files.
- Using your logged-in cookies for automated downloads carries some risk of YouTube flagging the account. Consider a secondary account.

## Project structure

```
extension/
  manifest.json    Manifest V3, permissions
  content.js       Button, menu, helper auto-start, progress
  content.css      Styling (light and dark)
  background.js    Talks to the helper, attaches YouTube cookies
helper/
  start.bat        Checks requirements, installs what's missing, registers ytdl://, starts the helper
  server.py        Local server wrapping yt-dlp and ffmpeg
```

## Disclaimer

For **personal use** only. Downloading videos may violate YouTube's Terms of Service; only download content you own or have permission to download. You are responsible for how you use this tool. Not affiliated with YouTube or Google. Browser stores won't accept it, so it is installed as an unpacked extension.

## Credits

[yt-dlp](https://github.com/yt-dlp/yt-dlp) · [FFmpeg](https://ffmpeg.org/) (builds from [yt-dlp/FFmpeg-Builds](https://github.com/yt-dlp/FFmpeg-Builds)) · [Deno](https://deno.com/)

## License

Add your preferred license here (for example MIT).
