#!/usr/bin/env python3
"""
Auto-Player  (single account, watch-only)
=========================================
Opens your real browser (Chrome via Playwright), searches your niche, and
watches videos/Shorts hands-free — ONE account, no rotation, no auto-likes,
no auto-comments. It READS each video's real stats off the page and writes
an Excel "engagement worksheet" so you can decide what to genuinely engage
with. You do the actual like/comment yourself (that's what keeps it real).

Stop it any time:
  - Ctrl+C in the terminal, OR
  - create a file named  stop.txt  in this folder, OR
  - close the browser window, OR
  - set "max_videos" in config.json (0 = unlimited)

First run:
  1) pip install -r requirements.txt
  2) python -m playwright install chromium     (one time)
  3) python auto_player.py
     A browser opens. Default: a DEDICATED profile (browser_profile/) —
     optionally log into ONE account once; it stays logged in.
     To use your everyday Chrome profile: close Chrome, then
       python auto_player.py --real-chrome
       (Mac/Linux: --profile-dir "/path/to/Chrome/User Data")

Output:
  output/engagement_<date>.xlsx   <- the Excel worksheet (one row per video)
  output/watch_log.csv            <- quick append-only log
"""
from __future__ import annotations

import json
import os
import random
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

HERE = Path(__file__).resolve().parent
CONFIG = HERE / "config.json"
STOP_FILE = HERE / "stop.txt"

DEFAULTS = {
    "niche": "",
    "output_dir": "output",
    "play_seconds_per_video": 40,
    "play_jitter": 12,
    "break_every": 8,
    "break_seconds": [90, 180],
    "max_videos": 0,
}


def load_cfg() -> dict:
    cfg = dict(DEFAULTS)
    try:
        cfg.update(json.loads(CONFIG.read_text(encoding="utf-8")))
    except FileNotFoundError:
        pass
    return cfg


def real_chrome_profile_dir():
    home = Path.home()
    candidates = [
        home / "AppData" / "Local" / "Google" / "Chrome" / "User Data",
        home / "Library" / "Application Support" / "Google" / "Chrome",
        home / ".config" / "google-chrome",
        home / ".config" / "chromium",
    ]
    for c in candidates:
        if c.is_dir():
            return str(c)
    return None


def stopped() -> bool:
    return STOP_FILE.exists()


def _chrome_exe():
    if sys.platform == "win32":
        cands = [
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Google/Chrome/Application/chrome.exe",
            Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Google/Chrome/Application/chrome.exe",
            Path.home() / "AppData/Local/Google/Chrome/Application/chrome.exe",
        ]
    else:
        cands = [Path("/usr/bin/google-chrome"), Path("/usr/bin/chromium-browser"),
                 Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")]
    for c in cands:
        if c.exists():
            return str(c)
    return "chrome"


def _scrape_meta(page) -> dict:
    """Best-effort: read view count, channel, and duration off the video page."""
    meta = {"views": "", "channel": "", "duration": ""}
    # view count (long video + shorts variants)
    for sel in ("ytd-video-view-count",
                "ytd-video-primary-info-renderer #view-count",
                "ytd-watch-metadata #count",
                "yt-content-view-engine-view-model #count"):
        try:
            el = page.query_selector(sel)
            if el:
                txt = (el.text_content() or "")
                m = re.search(r"([\d.,]+)", txt.replace("views", ""))
                if m:
                    num = m.group(1).replace(",", "").replace(".", "")
                    if num.isdigit():
                        meta["views"] = int(num)
                    break
        except Exception:
            continue
    # channel name
    for sel in ("ytd-channel-name a#channel-name", "ytd-channel-name #channel-name",
                "yt-formatted-string#channel-name"):
        try:
            el = page.query_selector(sel)
            if el and (el.text_content() or "").strip():
                meta["channel"] = el.text_content().strip()
                break
        except Exception:
            continue
    # duration from the <video> element
    try:
        el = page.query_selector("video")
        if el:
            d = el.get_attribute("duration")
            if d:
                meta["duration"] = int(float(d))
    except Exception:
        pass
    return meta


def fmt_len(s) -> str:
    try:
        s = int(s)
    except (TypeError, ValueError):
        return ""
    m, sec = divmod(s, 60)
    h, m = divmod(m, 60)
    return ("%d:%02d:%02d" % (h, m, sec)) if h else ("%d:%02d" % (m, sec))


def _flag(views) -> str:
    try:
        v = int(views)
    except (TypeError, ValueError):
        return ""
    if v >= 250000:
        return "Trending — a genuine comment + like here has the most reach"
    if v >= 25000:
        return "Growing — good candidate for a real comment"
    if v < 1000:
        return "Small creator — a sincere comment genuinely helps them"
    return ""


def write_xlsx(rows, path: Path, niche: str):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment

    wb = Workbook()
    ws = wb.active
    ws.title = "Engagement worksheet"
    ws.append(["Niche", niche, "", "", "", "", "Generated", datetime.now().strftime("%Y-%m-%d %H:%M")])
    ws.append([])
    headers = ["#", "Title", "Channel", "URL", "Views", "Length",
               "Watched (local)", "Suggested action", "Your comment (write a real one)",
               "Liked?", "Done?"]
    ws.append(headers)
    fill = PatternFill("solid", fgColor="1F4E78")
    for c in ws[ws.max_row]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = fill
        c.alignment = Alignment(vertical="center")
    for i, r in enumerate(rows, 1):
        ws.append([
            i, r.get("title", ""), r.get("channel", ""), r.get("url", ""),
            r.get("views", ""), fmt_len(r.get("duration")), r.get("watched_at", ""),
            r.get("flag", ""), "", "", "",
        ])
    widths = {"A": 5, "B": 55, "C": 28, "D": 46, "E": 12, "F": 8,
              "G": 20, "H": 40, "I": 44, "J": 9, "K": 8}
    for col, w in widths.items():
        ws.column_dimensions[col].width = w
    ws.freeze_panes = "A4"
    wb.save(path)


def _run_search_loop(page, cfg, niche, seen: set, counter: dict, rows: list,
                     xlsx_path: Path, csv_fh):
    q = quote(niche)
    page.goto("https://www.youtube.com/results?search_query=%s" % q, timeout=60000)
    page.wait_for_load_state("domcontentloaded")
    time.sleep(random.uniform(2, 4))
    _dismiss_banners(page)

    try:
        links = page.eval_on_selector_all(
            "a#video-title-link, a#video-title, a[href*='/shorts/']",
            """els => els.map(e => ({
                 href: e.href,
                 title: (e.getAttribute('title') || e.textContent || '').trim()
               })).filter(x => x.href)""")
    except Exception:
        links = []

    cands = []
    for l in links:
        href = l["href"].split("&")[0]
        if not href or href in seen:
            continue
        cands.append(l)
        seen.add(href)
    random.shuffle(cands)

    per = cfg["play_seconds_per_video"]
    jit = cfg["play_jitter"]
    for i, c in enumerate(cands, 1):
        if stopped():
            return
        if cfg["max_videos"] and counter["n"] >= cfg["max_videos"]:
            return
        dur = max(15, int(random.uniform(per - jit, per + jit)))
        print("[%d] %s  (~%ds)" % (i, (c["title"] or c["href"])[:60], dur))
        try:
            page.goto(c["href"], timeout=60000)
            page.wait_for_load_state("domcontentloaded")
            time.sleep(random.uniform(1.5, 3.5))
            _dismiss_banners(page)
            try:
                btn = page.query_selector("button.ytp-large-play-button")
                if btn and btn.is_visible():
                    btn.click()
            except Exception:
                pass
            # watch it, with light human-like activity
            t0 = time.time()
            while time.time() - t0 < dur and not stopped():
                time.sleep(3)
                try:
                    page.mouse.move(random.randint(200, 1100), random.randint(150, 700), steps=8)
                    if random.random() < 0.3:
                        page.mouse.wheel(0, random.randint(50, 180))
                except Exception:
                    break
            meta = _scrape_meta(page)
            row = {
                "title": (c["title"] or "")[:200],
                "url": c["href"],
                "channel": meta.get("channel", ""),
                "views": meta.get("views", ""),
                "duration": meta.get("duration", ""),
                "watched_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "flag": _flag(meta.get("views")),
            }
            rows.append(row)
            counter["n"] += 1
            try:
                write_xlsx(rows, xlsx_path, niche)
            except Exception as ex:
                print("   (xlsx write failed:", str(ex)[:60], ")")
            csv_fh.write('%s,%s,"%s"\n' % (
                row["watched_at"], c["href"].replace('"', "'"),
                (c["title"] or "")[:120].replace('"', "'"),
            ))
            csv_fh.flush()
            print("     views=%s  len=%s  flag=%s" % (
                meta.get("views", "?"), fmt_len(meta.get("duration")), row["flag"] or "-"))
            time.sleep(random.uniform(2, 6))
            if cfg["break_every"] and counter["n"] % cfg["break_every"] == 0:
                b = random.uniform(*cfg["break_seconds"])
                print("   ... taking a break (%.0f s) ..." % b)
                time.sleep(b)
        except Exception as e:
            print("   skip (%s)" % str(e)[:80])
    time.sleep(random.uniform(15, 40))


def _dismiss_banners(page):
    for sel in ("button[aria-label*='Accept all']",
                "button[aria-label*='Accept the use']",
                "tp-yt-paper-button#agree-button",
                "ytd-button-renderer button#agree-button",
                "button#accept-button"):
        try:
            b = page.query_selector(sel)
            if b and b.is_visible():
                b.click()
                time.sleep(1)
                return
        except Exception:
            pass


def main():
    cfg = load_cfg()
    if len(sys.argv) > 2 and sys.argv[1] == "--niche":
        cfg["niche"] = sys.argv[2].strip()
    niche = (cfg.get("niche") or "").strip()
    if not niche or "PASTE" in niche.upper():
        print("First set the 'niche' field in config.json (or pass --niche \"your niche\").")
        sys.exit(1)

    use_real_chrome = "--real-chrome" in sys.argv
    profile_dir = None
    for i, a in enumerate(sys.argv):
        if a == "--profile-dir" and i + 1 < len(sys.argv):
            profile_dir = sys.argv[i + 1]
    headless = "--headless" in sys.argv
    dedicated = HERE / "browser_profile"

    from playwright.sync_api import sync_playwright

    print("=" * 62)
    print("Auto-Player  (single account, watch-only, builds an Excel worksheet)")
    print("  niche    :", niche)
    print("  mode     :", "real Chrome profile" if use_real_chrome
          else "dedicated profile (log into ONE account once, optional)")
    print("  per video: %s ± %s s   break: every %d videos" % (
        cfg["play_seconds_per_video"], cfg["play_jitter"], cfg["break_every"]))
    print("  NO auto-like / NO auto-comment — you do those yourself.")
    print("  stop     : Ctrl+C  |  create stop.txt  |  close the window")
    print("=" * 62)
    if STOP_FILE.exists():
        STOP_FILE.unlink()

    outdir = HERE / cfg["output_dir"]
    outdir.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    xlsx_path = outdir / ("engagement_%s.xlsx" % stamp)
    log = outdir / "watch_log.csv"
    new_log = not log.exists()
    fh = open(log, "a", encoding="utf-8", newline="")
    if new_log:
        fh.write("time,video_url,title\n")

    rows = []
    watched = 0
    try:
        with sync_playwright() as p:
            if use_real_chrome:
                pdir = profile_dir or real_chrome_profile_dir()
                if not pdir:
                    print("Could not detect your Chrome profile. Pass: --profile-dir \"/path/to/Chrome/User Data\"")
                    sys.exit(1)
                print("Using real Chrome profile:", pdir, "(close Chrome first)")
                launched = p.chromium.launch(
                    executable_path=_chrome_exe(), headless=False,
                    args=["--user-data-dir=%s" % pdir, "--profile-directory=Default"])
                ctx = launched.new_context(viewport=None, locale="en-US")
            else:
                dedicated.mkdir(exist_ok=True)
                ctx = p.chromium.launch_persistent_context(
                    str(dedicated), headless=headless,
                    args=["--start-maximized"], viewport=None, locale="en-US")

            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.goto("https://www.youtube.com", timeout=60000)

            if not use_real_chrome and not headless:
                try:
                    print("Browser open. Optionally log into ONE account now.")
                    print("Press Enter when ready to start watching...")
                    input()
                except EOFError:
                    time.sleep(20)

            counter = {"n": 0}
            seen = set()
            while not stopped():
                try:
                    if page.is_closed():
                        raise RuntimeError("browser window was closed")
                    _run_search_loop(page, cfg, niche, seen, counter, rows,
                                     xlsx_path, fh)
                except Exception as e:
                    print("Session ended (%s)." % str(e)[:120])
                    break
                if cfg["max_videos"] and counter["n"] >= cfg["max_videos"]:
                    print("Reached max_videos (%d). Stopping." % cfg["max_videos"])
                    break
            watched = counter["n"]
            try:
                write_xlsx(rows, xlsx_path, niche)
            except Exception:
                pass
            try:
                ctx.close()
            except Exception:
                pass
    except KeyboardInterrupt:
        print("\nStopped by user (Ctrl+C).")

    fh.close()
    try:
        write_xlsx(rows, xlsx_path, niche)
    except Exception:
        pass
    print("\nDone. %d videos." % watched)
    print("  Excel worksheet : %s" % xlsx_path)
    print("  CSV log         : %s" % log)
    if STOP_FILE.exists():
        STOP_FILE.unlink()


if __name__ == "__main__":
    main()
