# YouTube Niche Research Bot + Multi-Account Auto-Player & UI

A modular automation and market intelligence suite for YouTube creators with full multi-account rotation, automated engagement (watching, liking, commenting, subscribing), and an interactive Web UI Control Panel.

| Tool | What it does | Launch |
|---|---|---|
| **`bot_UI.bat` / `bot_ui.py`** | **Interactive Web Dashboard & Control Panel** — Start/stop the bot, monitor live watch progress, configure rotation times (15–25 min), tweak like/comment/subscribe probabilities, and download Excel engagement reports. | Double-click `bot_UI.bat` (or `./bot_UI.sh`) |
| **`auto_player.py`** | **Automation Engine** — Discovers linked YouTube brand/channel accounts in your Chrome profile, rotates accounts one by one every 15–25 mins, watches trending & niche videos/Shorts with human simulation, automatically likes videos, posts comments, and subscribes to creators. | Double-click `run-player.bat` (or CLI) |
| **`research_bot.py`** | **Competitor Scanner** — Scans top channels in your niche → recent Shorts, fastest-growing videos, top comments, and hook keywords. Generates multi-sheet Excel reports and Markdown content brief digests. | Double-click `run-research.bat` (or CLI) |

---

## 1. Quick Start: Web UI Control Panel (Recommended)

1. **Windows:** Double-click **`bot_UI.bat`**  
   **Mac/Linux:** Run **`./bot_UI.sh`** (or `python bot_ui.py`)
2. The browser opens the interactive control panel at **`http://localhost:5000`**.
   > **If `bot_UI.bat` closes instantly:** run it from a terminal so you can read the error —
   > Win+R → `cmd` → `cd /d "<this folder>"` → `bot_UI.bat`. The window now pauses on any error instead of vanishing.
3. Configure your niche, choose content type (Shorts / Videos / Both), review your comment templates, and click **START BOT**.
4. The bot launches Chromium with your saved session, rotates across your accounts every 15–25 minutes, and streams real-time status and logs to the dashboard.

### Logging in / using your accounts
The bot opens a browser in one of two ways. Pick in the dashboard's **Browser Profile** section:

1. **OFF (default) — dedicated profile `browser_profile/`:** a fresh Chromium window opens. Sign into your Google/YouTube account **in that browser window** and the bot **automatically detects the login and continues** (no need to press Enter). You only log in once.

2. **ON — your real Chrome profile (recommended for existing accounts):** the bot opens the chosen Chrome profile (already signed in, with all your channel accounts). Set **"Chrome profile to use"** to the profile name (e.g. `Default`, `Profile 5`) and turn **ON** *"Use my real Chrome profile"*. The bot **auto-closes any running Chrome**, then launches that profile directly. Playwright uses a pipe (not the debug port), so it works even on Chrome 136+.

> **Which profile?** In `config.json`, `"chrome_profile_dir"` selects the profile inside your Chrome "User Data" folder (`Default`, `Profile 1`, `Profile 2`, …). The dashboard's *"Chrome profile to use"* field sets the same value. Use the one that holds your logged-in channel accounts.

> **Why not "Attach to running Chrome (CDP)"?** Chrome 136+ (and Edge/Chromium based on it) silently **ignores `--remote-debugging-port` when the profile is the default user data directory**. So attaching to your real-running Chrome no longer works. The reliable path is to let the bot launch your Chrome profile directly (option 2). The `launch-chrome-debug.bat`/`.sh` helpers are kept only for advanced manual use.

---

## 2. Multi-Account Capabilities

* **Single Profile Persistence:** Uses a dedicated profile (`./browser_profile/`) or your existing Chrome profile (`--real-chrome`). Log into your Google Account once — all your linked YouTube brand/channel accounts stay saved.
* **Automatic Discovery & Rotation:** Automatically scans all channels linked to your session and rotates through them one by one every **15 to 25 minutes** (randomized and configurable).
* **Automated Engagement Suite:**
  - **Auto-Like:** Automatically likes videos halfway through playback (with state detection to prevent unliking).
  - **Auto-Comment:** Scrolls to the comments section, types human-like comments with natural key delays from your customizable comment pool, and posts them.
  - **Auto-Subscribe:** Randomly subscribes to creators based on a configurable probability.
  - **Shorts & Videos:** Supports both YouTube Shorts and standard videos from global trending feeds and niche search.

---

## 3. Output Worksheets & Logs

Every run generates structured, timestamped reports in `output/`:
- **`output/engagement_<date>.xlsx`** — Complete Excel engagement worksheet containing:
  - `Account` (which YouTube account executed the action)
  - `Title`, `Channel`, `URL`, `Views`, `Length`, `Watched time`
  - `Suggested action` (Trending / Growing / Small creator)
  - `Comment Posted`
  - `Liked?` (`YES` / `NO`)
  - `Subscribed?` (`YES` / `NO`)
- **`output/watch_log.csv`** — Fast append-only history log.
- **`output/niche_research_<date>.xlsx`** & **`digest_<date>.md`** — Market intelligence reports from `research_bot.py`.

---

## 4. Configuration Reference (`config.json`)

```json
{
  "niche": "tech gadgets under $50",
  "api_key": "",
  "play_seconds_per_video": 40,
  "play_jitter": 12,
  "break_every": 8,
  "break_seconds": [90, 180],
  "account_rotation": {
    "enabled": true,
    "rotate_minutes": [15, 25],
    "accounts": []
  },
  "trending": {
    "enabled": true,
    "content_type": "both",
    "source": "trending_and_niche",
    "categories": ["trending", "gaming", "music"]
  },
  "engagement": {
    "auto_like": true,
    "like_probability": 0.8,
    "auto_comment": true,
    "comment_probability": 0.5,
    "auto_subscribe": true,
    "subscribe_probability": 0.25,
    "comment_pool": [
      "Great video, thanks for sharing!",
      "Really well explained, enjoyed this one 👍",
      "Super helpful content, keep it up!",
      "Loved the breakdown on this. Very insightful!",
      "Quality video right here 🔥",
      "This was really informative, thanks!",
      "Awesome presentation and pacing 👌",
      "Nice video! Learned something new today.",
      "Great editing and clear explanations!",
      "Solid content as always 👏",
      "Subscribed! Looking forward to more videos.",
      "The explanation at the beginning was super clear 🙌"
    ]
  }
}
```

---

## 5. CLI Options

```bash
# Launch Web UI
python bot_ui.py

# Launch CLI Auto-Player with real Chrome profile
python auto_player.py --real-chrome

# Custom rotation window (e.g. 20 to 30 mins)
python auto_player.py --rotate-min 20 --rotate-max 30

# Content type filter: Shorts only
python auto_player.py --shorts-only

# Stop anytime:
# Click "STOP BOT" in the UI, press Ctrl+C in terminal, or create a file named stop.txt
```
