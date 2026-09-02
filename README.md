# YouTube Niche Research Bot + Auto-Player

Two tools for your niche — built to be safe for your accounts:

| Tool | What it does | Needs |
|---|---|---|
| **`research_bot.py`** | Scans the top channels in your niche → their recent Shorts, fastest-growing videos, top comments, title/hook keywords. Saves an **Excel** file + a Markdown **digest**. | Nothing (falls back to scraping). Better with a free API key. |
| **`auto_player.py`** | Opens a real browser window, searches your niche, and watches videos/Shorts hands-free with human-like pacing. **One account, watch-only.** For every video it writes an **Excel engagement worksheet** (title, channel, URL, real view count, length, suggested action) with blank comment/liked columns for **you** to fill in. | First run: installs a browser (one-time). |

> ⚠️ **By design, this project does NOT do:** multi-account rotation, auto-likes,
> auto-comments, or posting. Those are exactly the actions YouTube's
> detection system flags ("inauthentic engagement"), and they get accounts
> and the whole device/IP terminated. The auto-player uses **one account**
> and only watches; the Excel worksheet tells you *where* your genuine
> engagement is worth it, and you do the actual like/comment yourself.

---

## 1. One-time setup

1. Install **Python 3.10 or newer** — https://python.org
   - On Windows, tick **“Add python.exe to PATH”** during install.
2. Put your niche in `config.json` (open it in Notepad / any text editor):
   ```json
   { "niche": "tech gadgets under $50", ... }
   ```
   (If you skip this, you can also pass `--niche "your niche"` on the command line.)

## 2. Run the Research Bot

**Windows:** double-click `run-research.bat`
**Mac/Linux:** `./run-research.sh`

First run creates a virtual environment and installs dependencies (~1 min).
Afterwards it runs the scan and writes two files into `output/`:

- `niche_research_<date>.xlsx` — sheets: **Summary, Channels, Videos, Trending (by views), Top Comments, Keywords & Hooks**
- `digest_<date>.md` — a readable summary: top channels, top 10 videos,
  what's working (median views, median length, most-used title words),
  sample hooks, top comments, and an “Ideas to test” checklist to fill in.

Re-run it daily (or whenever) — each run creates a fresh timestamped file,
so you can track what's changing over time.

### Optional (recommended): free API key

The bot works without a key (it scrapes via `yt-dlp`), but a free
**YouTube Data API v3** key makes it faster and more reliable:

1. Go to https://console.cloud.google.com → create a project (any name)
2. **APIs & Services → Library → search “YouTube Data API v3” → Enable**
3. **APIs & Services → Credentials → Create Credentials → API key**
4. Copy the key into `config.json` → `"api_key": "AIza..."`
5. (Optional, good practice) **Credentials → your key → Application
   restrictions → IP restrictions** — but only add it if you run the bot
   from one fixed IP.

## 3. Run the Auto-Player

**Windows:** double-click `run-player.bat`
**Mac/Linux:** `./run-player.sh`

First run downloads a browser (~150 MB, one time). Then a browser window opens:

- **Default mode (recommended):** it uses a *dedicated* profile folder
  (`browser_profile/`) — the first time, the terminal asks you to press
  **Enter** when you're ready; you may log into **one** of your accounts in
  that window first (optional). The login stays saved.
- **Your everyday Chrome profile instead:** close Chrome completely, then run
  `python auto_player.py --real-chrome` (Windows auto-detects the profile;
  on Mac/Linux pass `--profile-dir "/path/to/Chrome/User Data"`).

### What it does on each loop
1. Fresh search for your niche
2. Opens a video/Short, makes sure it's playing
3. Watches for **40 ± 12 seconds** (configurable)
4. Small random mouse drift / scroll while it plays
5. Reads the video's **real view count, channel, and length** off the page
6. Appends a row to **`output/engagement_<date>.xlsx`** and flags it
   (Trending / Growing / Small creator) so you know where a genuine
   comment + like is worth it
7. After **8 videos** → a 90–180 s “human break”, then repeats until you stop

**You do the engagement.** Open the flagged videos, write a real comment,
like the ones you genuinely enjoyed. That engagement is yours and it's real —
which is what YouTube rewards, and what keeps your account safe.

### How to stop it
- **Ctrl+C** in the terminal, **or**
- create any file named **`stop.txt`** in this folder (it stops within seconds;
  you don't have to be at the keyboard), **or**
- just close the browser window.

### Useful flags
```
python auto_player.py --niche "car detailing"     # override niche
python auto_player.py --real-chrome               # use your actual Chrome profile
python auto_player.py --headless                  # run without a visible window
```

### Tuning (all in `config.json`)
| Key | Default | Meaning |
|---|---|---|
| `play_seconds_per_video` | 40 | seconds watched per video |
| `play_jitter` | 12 | ± random variation (keeps it natural) |
| `break_every` | 8 | videos before a scheduled break |
| `break_seconds` | [90, 180] | break length range (seconds) |
| `max_videos` | 0 | stop after N videos (0 = run until you stop it) |

---

## How to actually use the research (where the real value is)

The digest is your content brief. Each run, look for:

1. **Hook patterns** — the “Sample hooks” section shows the first 8 words of
   winning titles. Notice what the niche's audience is being promised.
2. **Length sweet spot** — median duration of top videos. Match it.
3. **Keyword density** — which words keep appearing in top titles.
4. **Comment themes** — questions and complaints in top comments = your
   next 10 video ideas.
5. **Gaps** — ideas your top channels *haven't* covered yet.

Then make 3–5 Shorts a day from that list, and run the research bot again in
a week to see which of your ideas the data still supports.

## Files

```
config.json          <- your niche + settings
research_bot.py      <- research scanner (API + scrape fallback)
auto_player.py       <- hands-free niche player (single account, watch-only)
run-research.bat/.sh <- one-click launchers (Windows / Mac+Linux)
run-player.bat/.sh
output/              <- results land here (Excel, digest, watch log)
```
