#!/usr/bin/env python3
"""
YouTube History Bot - Web UI Control Panel
==========================================
Interactive web dashboard and automation controller.
Serves a clean, modern UI to configure, monitor, start, and stop
multi-account YouTube watching, auto-liking, auto-commenting, and auto-subscribing.

Usage:
  python bot_ui.py
  (or double click bot_UI.bat on Windows / ./bot_UI.sh on Mac/Linux)
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

HERE = Path(__file__).resolve().parent
CONFIG_FILE = HERE / "config.json"
STOP_FILE = HERE / "stop.txt"
OUTPUT_DIR = HERE / "output"

# Global Shared Engine State
STATE = {
    "running": False,
    "status": "Idle — Ready to start",
    "active_account": "None",
    "active_account_idx": 0,
    "accounts_list": [],
    "rotation_timer_end": 0,
    "rotation_duration_sec": 0,
    "current_video": None,
    "stats": {
        "watched": 0,
        "likes": 0,
        "comments": 0,
        "subs": 0,
        "rotations": 0,
    },
    "logs": [],
    "started_at": None,
}
STATE_LOCK = threading.Lock()
BOT_THREAD = None


def add_log(message: str, category: str = "info"):
    now = datetime.now().strftime("%H:%M:%S")
    with STATE_LOCK:
        STATE["logs"].append({
            "time": now,
            "category": category,
            "message": message,
        })
        if len(STATE["logs"]) > 300:
            STATE["logs"].pop(0)


def engine_callback(event: dict):
    etype = event.get("type")
    with STATE_LOCK:
        STATE["last_heartbeat"] = time.time()
        if etype == "status":
            STATE["status"] = event.get("status", STATE["status"])
            add_log(event.get("status", ""), "info")

        elif etype == "started":
            STATE["running"] = True
            STATE["status"] = "Automation Engine Active"
            STATE["started_at"] = event.get("timestamp")
            add_log(f"Bot session started in niche: '{event.get('niche') or 'Trending'}'", "system")

        elif etype == "accounts_discovered":
            accs = event.get("accounts", [])
            STATE["accounts_list"] = accs
            acc_names = ", ".join(a["name"] for a in accs)
            add_log(f"Detected {len(accs)} account(s) in profile: {acc_names}", "account")

        elif etype == "account_changed":
            name = event.get("account", "Unknown")
            dur = event.get("duration", 0)
            STATE["active_account"] = name
            STATE["active_account_idx"] = event.get("index", 0)
            STATE["rotation_duration_sec"] = dur
            STATE["rotation_timer_end"] = time.time() + dur
            STATE["status"] = f"Active on [{name}]"
            add_log(f"Active account set to: [{name}] (active for {dur / 60:.1f} mins)", "account")

        elif etype == "account_rotating":
            curr = event.get("current", "")
            nxt = event.get("next", "")
            STATE["status"] = f"Rotating from [{curr}] to [{nxt}]..."
            add_log(f"Time elapsed on [{curr}]. Rotating to [{nxt}]...", "account")

        elif etype == "video_start":
            title = event.get("title", "")
            acc = event.get("account", "")
            dur = event.get("duration", 0)
            STATE["current_video"] = {
                "title": title,
                "url": event.get("url", ""),
                "account": acc,
                "duration": dur,
                "liked": False,
                "subscribed": False,
                "comment": "",
            }
            STATE["status"] = f"Watching: {title[:40]}... (~{dur}s)"
            add_log(f"[{acc}] Playing: \"{title}\" (~{dur}s)", "watch")

        elif etype == "action":
            act = event.get("action")
            acc = event.get("account", "")
            if STATE["current_video"]:
                if act == "liked":
                    STATE["current_video"]["liked"] = True
                    add_log(f"[{acc}] ♥ Liked video: \"{event.get('title', '')}\"", "like")
                elif act == "commented":
                    STATE["current_video"]["comment"] = event.get("comment", "")
                    add_log(f"[{acc}] 💬 Commented: \"{event.get('comment', '')[:40]}...\"", "comment")
                elif act == "subscribed":
                    STATE["current_video"]["subscribed"] = True
                    add_log(f"[{acc}] 🔔 Subscribed to creator", "subscribe")

        elif etype == "video_complete":
            stats = event.get("stats", {})
            vdata = event.get("video", {})
            for k in STATE["stats"]:
                if k in stats:
                    STATE["stats"][k] = stats[k]
            add_log(f"✓ Completed & Logged: \"{vdata.get('title', '')[:45]}\" | Views: {vdata.get('views', '?')}", "watch")

        elif etype == "break":
            dur = event.get("duration", 0)
            STATE["status"] = f"Taking a natural pause ({dur:.0f}s)..."
            add_log(f"☕ Taking a natural break ({dur:.0f}s)...", "break")

        elif etype == "error":
            msg = event.get("message", "")
            STATE["status"] = f"Error: {msg}"
            add_log(f"Error encountered: {msg}", "error")

        elif etype == "finished":
            STATE["running"] = False
            STATE["status"] = "Idle — Session Completed"
            stats = event.get("stats", {})
            for k in STATE["stats"]:
                if k in stats:
                    STATE["stats"][k] = stats[k]
            add_log(f"Session finished. Total videos watched: {STATE['stats']['watched']}", "system")


def bot_worker(cfg: dict, use_real_chrome: bool, profile_dir: str):
    import auto_player
    # Heartbeat so the UI can tell if the engine is alive (and recover the button
    # if it ever stalls). Updated via engine_callback; checked by _bot_watchdog.
    STATE["last_heartbeat"] = time.time()
    try:
        auto_player.run_player_engine(
            cfg=cfg,
            status_callback=engine_callback,
            use_real_chrome=use_real_chrome,
            profile_dir=profile_dir,
            headless=False,
        )
    except Exception as ex:
        with STATE_LOCK:
            STATE["running"] = False
            STATE["status"] = f"Stopped: {ex}"
        add_log(f"Bot worker exception: {ex}", "error")
    finally:
        with STATE_LOCK:
            STATE["running"] = False


def _bot_heartbeat_watchdog():
    """
    Runs in the background: if the bot state says 'running' but no engine event
    has been seen for a long time (e.g. the browser launch hung), force-release
    the 'running' flag so the START button stops being stuck. It also adds a log
    line explaining what likely went wrong.
    """
    while True:
        time.sleep(10)
        with STATE_LOCK:
            running = STATE["running"]
            last = STATE.get("last_heartbeat", 0)
            status = STATE.get("status", "")
        if not running:
            continue
        # Allow up to 90s without any heartbeat before recovering. The very first
        # browser launch can take a while (starting Chromium), so be generous but
        # not so long that the button stays dead for many minutes.
        if time.time() - last > 90:
            with STATE_LOCK:
                STATE["running"] = False
                STATE["status"] = "Automation stalled (browser did not respond) - press START to try again"
            add_log("Bot stalled after launch (no heartbeat). Press START BOT again.", "error")


# --------------------------------------------------------------------------
# Web Server & Request Handler
# --------------------------------------------------------------------------
HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>YouTube History Bot — Multi-Account Hub</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <style>
    body { background-color: #0b0f19; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
    .glass { background: rgba(22, 27, 44, 0.85); backdrop-filter: blur(12px); border: 1px solid rgba(255, 255, 255, 0.08); }
    .glass-card { background: #131b2e; border: 1px solid rgba(255, 255, 255, 0.07); }
    .pulse-dot { animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite; }
    @keyframes pulse { 0%, 100% { opacity: 1; transform: scale(1); } 50% { opacity: .4; transform: scale(1.15); } }
    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: #0b0f19; }
    ::-webkit-scrollbar-thumb { background: #263352; border-radius: 4px; }
  </style>
</head>
<body class="text-slate-200 min-h-screen flex flex-col">

  <!-- Header -->
  <header class="glass sticky top-0 z-50 border-b border-slate-800 px-6 py-3.5 flex items-center justify-between">
    <div class="flex items-center space-x-3">
      <div class="w-10 h-10 rounded-xl bg-red-600 flex items-center justify-center shadow-lg shadow-red-600/30">
        <i class="fab fa-youtube text-white text-xl"></i>
      </div>
      <div>
        <h1 class="font-bold text-lg text-white tracking-tight flex items-center space-x-2">
          <span>YouTube History Bot</span>
          <span class="text-xs font-semibold px-2 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">Multi-Account</span>
        </h1>
        <p class="text-xs text-slate-400">Automated Watch, Like, Comment & Subscribe Rotation</p>
      </div>
    </div>

    <!-- Status & Main Toggle -->
    <div class="flex items-center space-x-4">
      <div id="statusBadge" class="flex items-center space-x-2 px-3.5 py-1.5 rounded-full text-xs font-medium bg-slate-800 text-slate-300 border border-slate-700">
        <span class="w-2.5 h-2.5 rounded-full bg-slate-500"></span>
        <span id="statusText">Idle — Ready to start</span>
      </div>

      <button id="btnToggleBot" onclick="toggleBot()" class="flex items-center space-x-2 px-5 py-2.5 rounded-xl font-bold text-sm bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-600 hover:to-teal-700 text-white shadow-lg shadow-emerald-500/25 transition-all transform active:scale-95">
        <i id="btnIcon" class="fas fa-play"></i>
        <span id="btnLabel">START BOT</span>
      </button>
    </div>
  </header>

  <!-- Main Container -->
  <main class="flex-1 max-w-7xl w-full mx-auto p-6 space-y-6">

    <!-- Top Stats Grid -->
    <div class="grid grid-cols-2 md:grid-cols-5 gap-4">
      <div class="glass-card rounded-2xl p-4 flex items-center space-x-4">
        <div class="w-12 h-12 rounded-xl bg-blue-500/10 text-blue-400 flex items-center justify-center text-xl border border-blue-500/20">
          <i class="fas fa-play-circle"></i>
        </div>
        <div>
          <div class="text-xs text-slate-400 font-medium">Videos Watched</div>
          <div id="statWatched" class="text-2xl font-bold text-white">0</div>
        </div>
      </div>

      <div class="glass-card rounded-2xl p-4 flex items-center space-x-4">
        <div class="w-12 h-12 rounded-xl bg-purple-500/10 text-purple-400 flex items-center justify-center text-xl border border-purple-500/20">
          <i class="fas fa-users-cog"></i>
        </div>
        <div class="overflow-hidden">
          <div class="text-xs text-slate-400 font-medium">Active Account</div>
          <div id="statAccount" class="text-sm font-bold text-white truncate">None</div>
          <div id="statTimer" class="text-[11px] text-purple-400 font-mono">00:00 remaining</div>
        </div>
      </div>

      <div class="glass-card rounded-2xl p-4 flex items-center space-x-4">
        <div class="w-12 h-12 rounded-xl bg-rose-500/10 text-rose-400 flex items-center justify-center text-xl border border-rose-500/20">
          <i class="fas fa-heart"></i>
        </div>
        <div>
          <div class="text-xs text-slate-400 font-medium">Likes Given</div>
          <div id="statLikes" class="text-2xl font-bold text-white">0</div>
        </div>
      </div>

      <div class="glass-card rounded-2xl p-4 flex items-center space-x-4">
        <div class="w-12 h-12 rounded-xl bg-sky-500/10 text-sky-400 flex items-center justify-center text-xl border border-sky-500/20">
          <i class="fas fa-comment-dots"></i>
        </div>
        <div>
          <div class="text-xs text-slate-400 font-medium">Comments Left</div>
          <div id="statComments" class="text-2xl font-bold text-white">0</div>
        </div>
      </div>

      <div class="glass-card rounded-2xl p-4 flex items-center space-x-4">
        <div class="w-12 h-12 rounded-xl bg-amber-500/10 text-amber-400 flex items-center justify-center text-xl border border-amber-500/20">
          <i class="fas fa-bell"></i>
        </div>
        <div>
          <div class="text-xs text-slate-400 font-medium">Subscriptions</div>
          <div id="statSubs" class="text-2xl font-bold text-white">0</div>
        </div>
      </div>
    </div>

    <!-- Active Media & Live Activity -->
    <div class="grid grid-cols-1 lg:grid-cols-12 gap-6">

      <!-- Left 7 cols: Active Watching & Live Feed -->
      <div class="lg:col-span-7 space-y-6">

        <!-- Now Playing Card -->
        <div class="glass-card rounded-2xl p-5 border border-slate-800">
          <div class="flex items-center justify-between mb-3">
            <h2 class="text-sm font-semibold uppercase tracking-wider text-slate-400 flex items-center space-x-2">
              <span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
              <span>Currently Playing</span>
            </h2>
            <span id="nowPlayingType" class="text-xs px-2.5 py-0.5 rounded-full bg-slate-800 text-slate-300 font-mono">STANDBY</span>
          </div>

          <div id="noVideoMsg" class="py-8 text-center text-slate-500">
            <i class="fas fa-film text-3xl mb-2 block text-slate-600"></i>
            <span>No video active. Press "START BOT" to begin automated watching.</span>
          </div>

          <div id="videoDetails" class="hidden space-y-3">
            <div class="text-base font-semibold text-white line-clamp-2" id="videoTitle">—</div>
            <div class="flex items-center space-x-3 text-xs text-slate-400">
              <span id="videoAccount" class="text-purple-400 font-medium flex items-center space-x-1">
                <i class="fas fa-user-circle"></i>
                <span id="videoAccountName">—</span>
              </span>
              <span>•</span>
              <a id="videoUrl" href="#" target="_blank" class="text-blue-400 hover:underline flex items-center space-x-1">
                <span>Watch on YouTube</span>
                <i class="fas fa-external-link-alt text-[10px]"></i>
              </a>
            </div>

            <!-- Engagement Status Pills -->
            <div class="flex flex-wrap gap-2 pt-2 border-t border-slate-800/80">
              <span id="pillLike" class="px-2.5 py-1 rounded-lg text-xs font-medium bg-slate-800 text-slate-400 flex items-center space-x-1.5">
                <i class="fas fa-heart text-slate-500"></i>
                <span>Like: Pending</span>
              </span>
              <span id="pillComment" class="px-2.5 py-1 rounded-lg text-xs font-medium bg-slate-800 text-slate-400 flex items-center space-x-1.5">
                <i class="fas fa-comment text-slate-500"></i>
                <span>Comment: Pending</span>
              </span>
              <span id="pillSub" class="px-2.5 py-1 rounded-lg text-xs font-medium bg-slate-800 text-slate-400 flex items-center space-x-1.5">
                <i class="fas fa-bell text-slate-500"></i>
                <span>Subscribe: Pending</span>
              </span>
            </div>
          </div>
        </div>

        <!-- Real-Time Activity Log -->
        <div class="glass-card rounded-2xl p-5 border border-slate-800 flex flex-col h-[380px]">
          <div class="flex items-center justify-between mb-3">
            <h2 class="text-sm font-semibold uppercase tracking-wider text-slate-400 flex items-center space-x-2">
              <i class="fas fa-terminal text-xs text-indigo-400"></i>
              <span>Live Activity Feed</span>
            </h2>
            <button onclick="clearLogs()" class="text-xs text-slate-400 hover:text-white transition">Clear</button>
          </div>
          <div id="logContainer" class="flex-1 overflow-y-auto space-y-1.5 font-mono text-xs pr-1">
            <div class="text-slate-500 italic">Waiting for bot events...</div>
          </div>
        </div>

      </div>

      <!-- Right 5 cols: Settings & Configuration -->
      <div class="lg:col-span-5 space-y-6">

        <div class="glass-card rounded-2xl p-5 border border-slate-800">
          <div class="flex items-center justify-between border-b border-slate-800 pb-3 mb-4">
            <h2 class="text-sm font-semibold uppercase tracking-wider text-slate-300 flex items-center space-x-2">
              <i class="fas fa-sliders-h text-indigo-400"></i>
              <span>Bot Configuration</span>
            </h2>
            <button onclick="saveConfig()" class="px-3 py-1.5 rounded-lg text-xs font-bold bg-indigo-600 hover:bg-indigo-500 text-white transition shadow-sm">
              <i class="fas fa-save mr-1"></i> Save Settings
            </button>
          </div>

          <!-- Configuration Form (ALL Settings Controlled Here) -->
          <div class="space-y-4 text-xs">

            <!-- Niche & Content Type -->
            <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div>
                <label class="block text-slate-400 font-medium mb-1">Niche / Topic Keyword</label>
                <input id="cfgNiche" type="text" placeholder="e.g. tech gadgets under $50" class="w-full px-3 py-2 rounded-xl bg-slate-900/80 border border-slate-700 text-white focus:outline-none focus:border-indigo-500">
              </div>
              <div>
                <label class="block text-slate-400 font-medium mb-1">Content Mode</label>
                <select id="cfgContentType" class="w-full px-3 py-2 rounded-xl bg-slate-900/80 border border-slate-700 text-white focus:outline-none focus:border-indigo-500">
                  <option value="both">Trending Videos & Shorts</option>
                  <option value="shorts">Shorts Only</option>
                  <option value="videos">Standard Videos Only</option>
                </select>
              </div>
            </div>

            <!-- Feed Source -->
            <div>
              <label class="block text-slate-400 font-medium mb-1">Video Feed Source</label>
              <select id="cfgFeedSource" class="w-full px-3 py-2 rounded-xl bg-slate-900/80 border border-slate-700 text-white focus:outline-none focus:border-indigo-500">
                <option value="trending_and_niche">Trending Feeds + Niche Search (Recommended)</option>
                <option value="trending_only">YouTube Global Trending Only</option>
                <option value="niche_only">Niche Search Only</option>
              </select>
            </div>

            <!-- Browser Profile Choice -->
            <div class="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800/80 space-y-2">
              <div class="flex items-center justify-between">
                <span class="font-semibold text-slate-200 flex items-center space-x-2">
                  <i class="fab fa-chrome text-blue-400"></i>
                  <span>Use my real Chrome profile</span>
                </span>
                <input id="cfgRealChrome" type="checkbox" class="w-4 h-4 rounded text-blue-600 focus:ring-blue-500 bg-slate-800 border-slate-700">
              </div>
              <div>
                <label class="block text-[11px] text-slate-400 mb-0.5">Chrome profile to use (e.g. Default, Profile 5)</label>
                <input id="cfgProfileDir" type="text" value="Default" placeholder="Default" class="w-full px-2.5 py-1.5 rounded-lg bg-slate-800 border border-slate-700 text-white text-[11px]">
              </div>
              <p class="text-[11px] text-slate-500 leading-relaxed">
                <strong class="text-slate-400">OFF</strong> = the bot opens a fresh, dedicated profile
                (<code>browser_profile/</code>) and you log into Google once in that window.<br>
                <strong class="text-slate-400">ON</strong> = the bot reuses your existing
                Chrome session (already logged in, all your channel accounts saved).
                Close Chrome before starting if you enable this.
              </p>
            </div>

            <!-- Attach to Running Chrome (CDP) -->
            <div class="p-3.5 rounded-xl bg-indigo-500/10 border border-indigo-500/30 space-y-2">
              <div class="flex items-center justify-between">
                <span class="font-semibold text-indigo-200 flex items-center space-x-2">
                  <i class="fas fa-plug text-indigo-300"></i>
                  <span>Attach to running Chrome (CDP)</span>
                </span>
                <input id="cfgConnectCdp" type="checkbox" class="w-4 h-4 rounded text-indigo-600 focus:ring-indigo-500 bg-slate-800 border-slate-700">
              </div>
              <p class="text-[11px] text-slate-400 leading-relaxed">
                <strong class="text-indigo-300">ON</strong> = the bot connects to the Chrome that is
                ALREADY open (same profile & accounts you're using right now).
                Keep Chrome open; first run <code>launch-chrome-debug.bat</code> once so Chrome
                exposes the debug port. This is the easiest way to use your existing accounts.
              </p>
            </div>

            <!-- Account Rotation Settings -->
            <div class="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800/80 space-y-2.5">
              <div class="flex items-center justify-between">
                <span class="font-semibold text-slate-200 flex items-center space-x-2">
                  <i class="fas fa-sync-alt text-purple-400"></i>
                  <span>Multi-Account Rotation</span>
                </span>
                <input id="cfgRotateEnabled" type="checkbox" checked class="w-4 h-4 rounded text-purple-600 focus:ring-purple-500 bg-slate-800 border-slate-700">
              </div>
              <div class="grid grid-cols-2 gap-2 text-slate-400">
                <div>
                  <label class="block text-[11px] mb-0.5">Min Mins per Account</label>
                  <input id="cfgRotateMin" type="number" value="15" min="1" max="120" class="w-full px-2.5 py-1.5 rounded-lg bg-slate-800 border border-slate-700 text-white">
                </div>
                <div>
                  <label class="block text-[11px] mb-0.5">Max Mins per Account</label>
                  <input id="cfgRotateMax" type="number" value="25" min="1" max="180" class="w-full px-2.5 py-1.5 rounded-lg bg-slate-800 border border-slate-700 text-white">
                </div>
              </div>
              <div>
                <label class="block text-[11px] text-slate-400 mb-0.5">Accounts List (one per line — leave empty for Auto-Detect)</label>
                <textarea id="cfgAccountsList" rows="2" placeholder="Leave empty to automatically discover all accounts in your Chrome profile" class="w-full px-2.5 py-1.5 rounded-lg bg-slate-800 border border-slate-700 text-white text-[11px]"></textarea>
              </div>
            </div>

            <!-- Engagement Controls: Like, Comment, Subscribe -->
            <div class="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800/80 space-y-3">
              <div class="font-semibold text-slate-200 flex items-center space-x-2 mb-1">
                <i class="fas fa-magic text-emerald-400"></i>
                <span>Automated Engagement Settings</span>
              </div>

              <!-- Like -->
              <div class="flex items-center justify-between">
                <label class="flex items-center space-x-2 text-slate-300">
                  <input id="cfgAutoLike" type="checkbox" checked class="w-4 h-4 rounded text-rose-600 bg-slate-800 border-slate-700">
                  <span>Auto-Like Videos</span>
                </label>
                <div class="flex items-center space-x-1 text-slate-400 text-[11px]">
                  <span>Prob:</span>
                  <input id="cfgLikeProb" type="number" step="0.05" min="0" max="1" value="0.80" class="w-14 px-1.5 py-1 rounded bg-slate-800 border border-slate-700 text-white text-center">
                </div>
              </div>

              <!-- Comment -->
              <div class="flex items-center justify-between">
                <label class="flex items-center space-x-2 text-slate-300">
                  <input id="cfgAutoComment" type="checkbox" checked class="w-4 h-4 rounded text-sky-600 bg-slate-800 border-slate-700">
                  <span>Auto-Comment</span>
                </label>
                <div class="flex items-center space-x-1 text-slate-400 text-[11px]">
                  <span>Prob:</span>
                  <input id="cfgCommentProb" type="number" step="0.05" min="0" max="1" value="0.50" class="w-14 px-1.5 py-1 rounded bg-slate-800 border border-slate-700 text-white text-center">
                </div>
              </div>

              <!-- Subscribe -->
              <div class="flex items-center justify-between">
                <label class="flex items-center space-x-2 text-slate-300">
                  <input id="cfgAutoSub" type="checkbox" checked class="w-4 h-4 rounded text-amber-600 bg-slate-800 border-slate-700">
                  <span>Auto-Subscribe to Creators</span>
                </label>
                <div class="flex items-center space-x-1 text-slate-400 text-[11px]">
                  <span>Prob:</span>
                  <input id="cfgSubProb" type="number" step="0.05" min="0" max="1" value="0.25" class="w-14 px-1.5 py-1 rounded bg-slate-800 border border-slate-700 text-white text-center">
                </div>
              </div>
            </div>

            <!-- Comment Pool Editor -->
            <div>
              <label class="block text-slate-400 font-medium mb-1">Comment Pool (one template per line)</label>
              <textarea id="cfgComments" rows="4" class="w-full px-3 py-2 rounded-xl bg-slate-900/80 border border-slate-700 text-white text-xs focus:outline-none focus:border-indigo-500"></textarea>
            </div>

            <!-- Timing, Jitter & Breaks -->
            <div class="grid grid-cols-2 gap-3 text-slate-400">
              <div>
                <label class="block text-[11px] mb-0.5">Watch Seconds</label>
                <input id="cfgWatchSec" type="number" value="40" min="15" max="600" class="w-full px-2.5 py-1.5 rounded-lg bg-slate-900 border border-slate-700 text-white">
              </div>
              <div>
                <label class="block text-[11px] mb-0.5">Watch Jitter (±s)</label>
                <input id="cfgWatchJitter" type="number" value="12" min="0" max="60" class="w-full px-2.5 py-1.5 rounded-lg bg-slate-900 border border-slate-700 text-white">
              </div>
            </div>

            <div class="grid grid-cols-3 gap-2 text-slate-400">
              <div>
                <label class="block text-[11px] mb-0.5">Break Every (vids)</label>
                <input id="cfgBreakEvery" type="number" value="8" min="1" max="50" class="w-full px-2.5 py-1.5 rounded-lg bg-slate-900 border border-slate-700 text-white">
              </div>
              <div>
                <label class="block text-[11px] mb-0.5">Break Min (s)</label>
                <input id="cfgBreakMin" type="number" value="90" min="10" max="600" class="w-full px-2.5 py-1.5 rounded-lg bg-slate-900 border border-slate-700 text-white">
              </div>
              <div>
                <label class="block text-[11px] mb-0.5">Break Max (s)</label>
                <input id="cfgBreakMax" type="number" value="180" min="10" max="1200" class="w-full px-2.5 py-1.5 rounded-lg bg-slate-900 border border-slate-700 text-white">
              </div>
            </div>

            <div>
              <label class="block text-[11px] text-slate-400 mb-0.5">Max Videos Target (0 = Unlimited)</label>
              <input id="cfgMaxVideos" type="number" value="0" min="0" max="10000" class="w-full px-2.5 py-1.5 rounded-lg bg-slate-900 border border-slate-700 text-white">
            </div>

          </div>
        </div>

        <!-- Output Files & Worksheets -->
        <div class="glass-card rounded-2xl p-4 border border-slate-800">
          <div class="flex items-center justify-between mb-2">
            <h3 class="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center space-x-1.5">
              <i class="fas fa-file-excel text-emerald-400"></i>
              <span>Generated Excel & CSV Reports</span>
            </h3>
            <button onclick="loadHistory()" class="text-xs text-indigo-400 hover:underline">Refresh</button>
          </div>
          <div id="historyList" class="text-xs space-y-1.5 max-h-36 overflow-y-auto">
            <div class="text-slate-500">Checking output folder...</div>
          </div>
        </div>

      </div>

    </div>

  </main>

  <footer class="glass border-t border-slate-800 px-6 py-3 text-center text-xs text-slate-500">
    YouTube History Bot &bull; Multi-Account Rotation &bull; Single Profile Automation
  </footer>

  <script>
    let isRunning = false;
    let configCache = {};

    async function fetchStatus() {
      try {
        const res = await fetch('/api/status');
        const data = await res.json();
        updateUI(data);
      } catch (e) {
        console.error('Status fetch error:', e);
      }
    }

    async function loadConfig() {
      try {
        const res = await fetch('/api/config');
        const cfg = await res.json();
        configCache = cfg;

        document.getElementById('cfgNiche').value = cfg.niche || '';
        document.getElementById('cfgContentType').value = (cfg.trending && cfg.trending.content_type) || 'both';
        document.getElementById('cfgFeedSource').value = (cfg.trending && cfg.trending.source) || 'trending_and_niche';
        document.getElementById('cfgRealChrome').checked = !!cfg.use_real_chrome;
        document.getElementById('cfgConnectCdp').checked = !!cfg.connect_cdp;
        document.getElementById('cfgProfileDir').value = cfg.chrome_profile_dir || 'Default';

        document.getElementById('cfgWatchSec').value = cfg.play_seconds_per_video || 40;
        document.getElementById('cfgWatchJitter').value = cfg.play_jitter ?? 12;
        document.getElementById('cfgBreakEvery').value = cfg.break_every || 8;
        document.getElementById('cfgMaxVideos').value = cfg.max_videos || 0;

        const bSecs = cfg.break_seconds || [90, 180];
        document.getElementById('cfgBreakMin').value = bSecs[0] || 90;
        document.getElementById('cfgBreakMax').value = bSecs[1] || 180;

        if (cfg.account_rotation) {
          document.getElementById('cfgRotateEnabled').checked = cfg.account_rotation.enabled !== false;
          const mins = cfg.account_rotation.rotate_minutes || [15, 25];
          document.getElementById('cfgRotateMin').value = mins[0];
          document.getElementById('cfgRotateMax').value = mins[1];
          const accs = cfg.account_rotation.accounts || [];
          document.getElementById('cfgAccountsList').value = accs.join('\\n');
        }

        if (cfg.engagement) {
          document.getElementById('cfgAutoLike').checked = cfg.engagement.auto_like !== false;
          document.getElementById('cfgLikeProb').value = cfg.engagement.like_probability ?? 0.8;
          document.getElementById('cfgAutoComment').checked = cfg.engagement.auto_comment !== false;
          document.getElementById('cfgCommentProb').value = cfg.engagement.comment_probability ?? 0.5;
          document.getElementById('cfgAutoSub').checked = cfg.engagement.auto_subscribe !== false;
          document.getElementById('cfgSubProb').value = cfg.engagement.subscribe_probability ?? 0.25;

          const pool = cfg.engagement.comment_pool || [];
          document.getElementById('cfgComments').value = pool.join('\\n');
        }
      } catch (e) {
        console.error('Config load error:', e);
      }
    }

    async function saveConfig() {
      const comments = document.getElementById('cfgComments').value.split('\\n').map(s => s.trim()).filter(Boolean);
      const accounts = document.getElementById('cfgAccountsList').value.split('\\n').map(s => s.trim()).filter(Boolean);

      const newCfg = {
        ...configCache,
        niche: document.getElementById('cfgNiche').value.trim(),
        use_real_chrome: document.getElementById('cfgRealChrome').checked,
        connect_cdp: document.getElementById('cfgConnectCdp').checked,
        cdp_url: configCache.cdp_url || 'http://localhost:9222',
        chrome_profile_dir: document.getElementById('cfgProfileDir').value.trim() || 'Default',
        play_seconds_per_video: parseInt(document.getElementById('cfgWatchSec').value) || 40,
        play_jitter: parseInt(document.getElementById('cfgWatchJitter').value) || 12,
        break_every: parseInt(document.getElementById('cfgBreakEvery').value) || 8,
        break_seconds: [
          parseInt(document.getElementById('cfgBreakMin').value) || 90,
          parseInt(document.getElementById('cfgBreakMax').value) || 180
        ],
        max_videos: parseInt(document.getElementById('cfgMaxVideos').value) || 0,
        account_rotation: {
          enabled: document.getElementById('cfgRotateEnabled').checked,
          rotate_minutes: [
            parseInt(document.getElementById('cfgRotateMin').value) || 15,
            parseInt(document.getElementById('cfgRotateMax').value) || 25
          ],
          accounts: accounts
        },
        trending: {
          enabled: true,
          content_type: document.getElementById('cfgContentType').value,
          source: document.getElementById('cfgFeedSource').value,
          categories: ["trending", "gaming", "music"]
        },
        engagement: {
          auto_like: document.getElementById('cfgAutoLike').checked,
          like_probability: parseFloat(document.getElementById('cfgLikeProb').value) || 0.8,
          auto_comment: document.getElementById('cfgAutoComment').checked,
          comment_probability: parseFloat(document.getElementById('cfgCommentProb').value) || 0.5,
          auto_subscribe: document.getElementById('cfgAutoSub').checked,
          subscribe_probability: parseFloat(document.getElementById('cfgSubProb').value) || 0.25,
          comment_pool: comments
        }
      };

      try {
        const res = await fetch('/api/config', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(newCfg)
        });
        if (res.ok) {
          configCache = newCfg;
          alert('Configuration saved successfully!');
        }
      } catch (e) {
        alert('Failed to save config: ' + e);
      }
    }

    async function toggleBot() {
      if (isRunning) {
        if (!confirm('Stop the running bot session?')) return;
        await fetch('/api/stop', { method: 'POST' });
      } else {
        await saveConfig();
        const res = await fetch('/api/start', { method: 'POST' });
        const result = await res.json();
        if (!result.success) {
          alert('Failed to start: ' + (result.message || 'Unknown error'));
        }
      }
      fetchStatus();
    }

    function updateUI(data) {
      isRunning = data.running;
      const btn = document.getElementById('btnToggleBot');
      const btnLabel = document.getElementById('btnLabel');
      const btnIcon = document.getElementById('btnIcon');
      const badge = document.getElementById('statusBadge');

      if (isRunning) {
        btn.className = "flex items-center space-x-2 px-5 py-2.5 rounded-xl font-bold text-sm bg-gradient-to-r from-rose-600 to-red-700 hover:from-rose-700 hover:to-red-800 text-white shadow-lg shadow-rose-600/25 transition-all transform active:scale-95";
        btnLabel.innerText = "STOP BOT";
        btnIcon.className = "fas fa-stop";
        badge.className = "flex items-center space-x-2 px-3.5 py-1.5 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-300 border border-emerald-500/30";
        badge.innerHTML = '<span class="w-2.5 h-2.5 rounded-full bg-emerald-400 pulse-dot"></span><span>' + (data.status || 'Running') + '</span>';
      } else {
        btn.className = "flex items-center space-x-2 px-5 py-2.5 rounded-xl font-bold text-sm bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-600 hover:to-teal-700 text-white shadow-lg shadow-emerald-500/25 transition-all transform active:scale-95";
        btnLabel.innerText = "START BOT";
        btnIcon.className = "fas fa-play";
        badge.className = "flex items-center space-x-2 px-3.5 py-1.5 rounded-full text-xs font-medium bg-slate-800 text-slate-300 border border-slate-700";
        badge.innerHTML = '<span class="w-2.5 h-2.5 rounded-full bg-slate-500"></span><span>' + (data.status || 'Idle — Ready to start') + '</span>';
      }

      // Stats
      document.getElementById('statWatched').innerText = data.stats.watched || 0;
      document.getElementById('statLikes').innerText = data.stats.likes || 0;
      document.getElementById('statComments').innerText = data.stats.comments || 0;
      document.getElementById('statSubs').innerText = data.stats.subs || 0;
      document.getElementById('statAccount').innerText = data.active_account || 'None';

      // Rotation timer
      if (data.rotation_timer_end && data.running) {
        const remaining = Math.max(0, Math.floor(data.rotation_timer_end - Date.now() / 1000));
        const m = Math.floor(remaining / 60);
        const s = remaining % 60;
        document.getElementById('statTimer').innerText = `${m}m ${s < 10 ? '0' : ''}${s}s to rotation`;
      } else {
        document.getElementById('statTimer').innerText = 'Rotation inactive';
      }

      // Current video
      const v = data.current_video;
      const noVideoMsg = document.getElementById('noVideoMsg');
      const vDetails = document.getElementById('videoDetails');
      if (v && isRunning) {
        noVideoMsg.classList.add('hidden');
        vDetails.classList.remove('hidden');
        document.getElementById('videoTitle').innerText = v.title || 'Untitled Video';
        document.getElementById('videoAccountName').innerText = v.account || 'Default';
        document.getElementById('videoUrl').href = v.url || '#';

        // Pills
        document.getElementById('pillLike').innerHTML = v.liked
          ? '<i class="fas fa-heart text-rose-500"></i><span class="text-rose-300 font-bold">Liked: YES</span>'
          : '<i class="fas fa-heart text-slate-500"></i><span>Like: Pending</span>';

        document.getElementById('pillComment').innerHTML = v.comment
          ? '<i class="fas fa-comment text-sky-400"></i><span class="text-sky-300 font-bold">Commented</span>'
          : '<i class="fas fa-comment text-slate-500"></i><span>Comment: Pending</span>';

        document.getElementById('pillSub').innerHTML = v.subscribed
          ? '<i class="fas fa-bell text-amber-400"></i><span class="text-amber-300 font-bold">Subscribed: YES</span>'
          : '<i class="fas fa-bell text-slate-500"></i><span>Subscribe: Pending</span>';
      } else {
        noVideoMsg.classList.remove('hidden');
        vDetails.classList.add('hidden');
      }

      // Logs
      renderLogs(data.logs || []);
    }

    function renderLogs(logs) {
      const container = document.getElementById('logContainer');
      if (!logs.length) return;
      container.innerHTML = logs.map(l => {
        let color = 'text-slate-300';
        let badge = 'text-slate-500';
        if (l.category === 'watch') { color = 'text-blue-300'; badge = 'text-blue-500'; }
        if (l.category === 'like') { color = 'text-rose-300'; badge = 'text-rose-500'; }
        if (l.category === 'comment') { color = 'text-sky-300'; badge = 'text-sky-500'; }
        if (l.category === 'subscribe') { color = 'text-amber-300'; badge = 'text-amber-500'; }
        if (l.category === 'account') { color = 'text-purple-300 font-semibold'; badge = 'text-purple-400'; }
        if (l.category === 'break') { color = 'text-emerald-300'; badge = 'text-emerald-500'; }
        if (l.category === 'error') { color = 'text-red-400'; badge = 'text-red-500'; }

        return `<div class="flex items-start space-x-2">
          <span class="text-slate-600 select-none">[${l.time}]</span>
          <span class="${color}">${escapeHtml(l.message)}</span>
        </div>`;
      }).join('');
      container.scrollTop = container.scrollHeight;
    }

    function escapeHtml(text) {
      return (text || '').replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }

    function clearLogs() {
      document.getElementById('logContainer').innerHTML = '<div class="text-slate-500 italic">Logs cleared.</div>';
    }

    async function loadHistory() {
      try {
        const res = await fetch('/api/history');
        const files = await res.json();
        const list = document.getElementById('historyList');
        if (!files.length) {
          list.innerHTML = '<div class="text-slate-500">No output reports generated yet.</div>';
          return;
        }
        list.innerHTML = files.map(f => `
          <div class="flex items-center justify-between p-2 rounded-lg bg-slate-900/60 border border-slate-800">
            <div class="truncate mr-2">
              <span class="font-medium text-slate-200 block truncate">${f.name}</span>
              <span class="text-[10px] text-slate-500">${f.time} &bull; ${f.size}</span>
            </div>
            <a href="/api/download?file=${encodeURIComponent(f.name)}" download class="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-indigo-400 text-[11px] font-medium transition">
              <i class="fas fa-download mr-1"></i> Save
            </a>
          </div>
        `).join('');
      } catch (e) {
        console.error('Failed to load history:', e);
      }
    }

    // Init
    loadConfig();
    fetchStatus();
    loadHistory();
    setInterval(fetchStatus, 2000);
  </script>
</body>
</html>
"""


class UIHandler(BaseHTTPRequestHandler):
    def _send_json(self, data, status=200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html_text: str):
        body = html_text.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/" or path == "/index.html":
            self._send_html(HTML_PAGE)

        elif path == "/api/status":
            with STATE_LOCK:
                snapshot = dict(STATE)
                snapshot["logs"] = list(STATE["logs"])
                if STATE["current_video"]:
                    snapshot["current_video"] = dict(STATE["current_video"])
            self._send_json(snapshot)

        elif path == "/api/config":
            import auto_player
            cfg = auto_player.load_cfg()
            self._send_json(cfg)

        elif path == "/api/history":
            files = []
            if OUTPUT_DIR.exists():
                for f in sorted(OUTPUT_DIR.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
                    if f.is_file() and (f.suffix in [".xlsx", ".csv", ".md"]):
                        mtime = datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
                        size_kb = f.stat().st_size / 1024
                        size_str = f"{size_kb:.1f} KB" if size_kb >= 1 else f"{f.stat().st_size} B"
                        files.append({
                            "name": f.name,
                            "time": mtime,
                            "size": size_str,
                        })
            self._send_json(files)

        elif path == "/api/download":
            qs = parse_qs(parsed.query)
            fname = qs.get("file", [""])[0]
            target = OUTPUT_DIR / Path(fname).name
            if target.exists() and target.is_file():
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Disposition", f'attachment; filename="{target.name}"')
                self.send_header("Content-Length", str(target.stat().st_size))
                self.end_headers()
                with open(target, "rb") as f:
                    self.wfile.write(f.read())
            else:
                self.send_error(404, "File not found")

        else:
            self.send_error(404, "Endpoint not found")

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length > 0 else b"{}"

        if path == "/api/config":
            try:
                new_cfg = json.loads(body.decode("utf-8"))
                CONFIG_FILE.write_text(json.dumps(new_cfg, indent=2), encoding="utf-8")
                self._send_json({"success": True, "message": "Config updated"})
            except Exception as e:
                self._send_json({"success": False, "message": str(e)}, 400)

        elif path == "/api/start":
            global BOT_THREAD
            with STATE_LOCK:
                if STATE["running"]:
                    self._send_json({"success": False, "message": "Bot is already running"})
                    return

            import auto_player
            cfg = auto_player.load_cfg()

            if STOP_FILE.exists():
                STOP_FILE.unlink()

            with STATE_LOCK:
                STATE["running"] = True
                STATE["status"] = "Launching browser session..."
                STATE["stats"] = {"watched": 0, "likes": 0, "comments": 0, "subs": 0, "rotations": 0}

            add_log("Starting bot worker thread...", "system")
            use_real_chrome = "--real-chrome" in sys.argv or "--cdp" in sys.argv or bool(cfg.get("use_real_chrome", False))
            BOT_THREAD = threading.Thread(
                target=bot_worker,
                args=(cfg, use_real_chrome, None),
                daemon=True,
            )
            BOT_THREAD.start()
            self._send_json({"success": True, "message": "Bot started"})

        elif path == "/api/stop":
            STOP_FILE.write_text("stop", encoding="utf-8")
            with STATE_LOCK:
                STATE["status"] = "Stopping bot gracefully..."
            add_log("Stop requested by user...", "system")
            self._send_json({"success": True, "message": "Stop signal sent"})

        else:
            self.send_error(404, "Endpoint not found")

    def log_message(self, format, *args):
        # Silence the harmless "ConnectionAbortedError / 10053" tracebacks that appear
        # when the user refreshes or closes the dashboard tab mid-request.  These are
        # normal HTTP client disconnects, not bot errors.
        return


class QuietHTTPServer(HTTPServer):
    """HTTPServer that doesn't print client-disconnect noise to the console."""
    def handle_error(self, request, client_address):
        import sys
        import traceback
        exc = sys.exc_info()[1]
        # Windows client aborts (WinError 10053) and similar brief disconnects are
        # normal when the browser tab is refreshed/closed mid-request.  Don't spam.
        name = type(exc).__name__ if exc else ""
        msg = str(exc) if exc else ""
        if "ConnectionAborted" in name or "10053" in msg or "ConnectionReset" in name or "10054" in msg:
            return
        # Otherwise show the real error (bugs, not disconnects).
        traceback.print_exc()


def run_ui_server(port: int = 5000):
    host = "0.0.0.0"
    server = QuietHTTPServer((host, port), UIHandler)
    print("=" * 60)
    print("  YouTube History Bot — Control Panel UI")
    print(f"  Access local dashboard : http://localhost:{port}")
    print(f"  Listening on host      : {host}:{port}")
    print("=" * 60)
    # Start the stalled-engine watchdog so the START button can never be permanently stuck.
    watchdog = threading.Thread(target=_bot_heartbeat_watchdog, daemon=True)
    watchdog.start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nUI Server terminated.")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    run_ui_server(port=port)
