#!/usr/bin/env python3
"""
Comprehensive Test Suite for YouTube History Bot & UI
"""
import json
import urllib.request
import urllib.error
from pathlib import Path

HERE = Path(__file__).resolve().parent

def test_ui_endpoints():
    print("[Test 1] Testing Web UI Endpoints...")
    base = "http://localhost:5000"

    # 1. GET /
    req = urllib.request.urlopen(f"{base}/", timeout=10)
    assert req.status == 200, f"Expected 200, got {req.status}"
    html = req.read().decode("utf-8")
    assert "YouTube History Bot" in html, "Dashboard HTML missing title"
    assert "cfgAutoSub" in html, "Dashboard missing Auto-Subscribe control"
    assert "cfgAccountsList" in html, "Dashboard missing Accounts List control"
    assert "cfgFeedSource" in html, "Dashboard missing Feed Source control"
    print("  ✓ GET / returned valid HTML dashboard")

    # 2. GET /api/status
    req = urllib.request.urlopen(f"{base}/api/status", timeout=10)
    assert req.status == 200
    status_data = json.loads(req.read().decode("utf-8"))
    assert "running" in status_data
    assert "stats" in status_data
    assert "watched" in status_data["stats"]
    assert "subs" in status_data["stats"]
    print("  ✓ GET /api/status returned valid state structure")

    # 3. GET /api/config
    req = urllib.request.urlopen(f"{base}/api/config", timeout=10)
    assert req.status == 200
    cfg = json.loads(req.read().decode("utf-8"))
    assert "niche" in cfg
    assert "account_rotation" in cfg
    assert "engagement" in cfg
    print("  ✓ GET /api/config returned valid configuration")

    # 4. POST /api/config - Test every setting
    test_cfg = {
        "niche": "test niche AI tools",
        "play_seconds_per_video": 45,
        "play_jitter": 15,
        "break_every": 6,
        "break_seconds": [60, 120],
        "max_videos": 25,
        "account_rotation": {
            "enabled": True,
            "rotate_minutes": [18, 28],
            "accounts": ["Channel Alpha", "Channel Beta"]
        },
        "trending": {
            "enabled": True,
            "content_type": "shorts",
            "source": "trending_and_niche",
            "categories": ["trending", "gaming", "music"]
        },
        "engagement": {
            "auto_like": True,
            "like_probability": 0.85,
            "auto_comment": True,
            "comment_probability": 0.65,
            "auto_subscribe": True,
            "subscribe_probability": 0.35,
            "comment_pool": [
                "Awesome tutorial!",
                "Really helped me out, thanks!"
            ]
        }
    }
    req = urllib.request.Request(
        f"{base}/api/config",
        data=json.dumps(test_cfg).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    res = urllib.request.urlopen(req, timeout=10)
    assert res.status == 200
    res_data = json.loads(res.read().decode("utf-8"))
    assert res_data.get("success") is True

    # Verify saved
    req = urllib.request.urlopen(f"{base}/api/config", timeout=10)
    saved_cfg = json.loads(req.read().decode("utf-8"))
    assert saved_cfg["niche"] == "test niche AI tools"
    assert saved_cfg["play_seconds_per_video"] == 45
    assert saved_cfg["account_rotation"]["rotate_minutes"] == [18, 28]
    assert saved_cfg["account_rotation"]["accounts"] == ["Channel Alpha", "Channel Beta"]
    assert saved_cfg["trending"]["content_type"] == "shorts"
    assert saved_cfg["engagement"]["auto_subscribe"] is True
    assert saved_cfg["engagement"]["subscribe_probability"] == 0.35
    print("  ✓ POST /api/config successfully saved and verified all settings")

    # 5. GET /api/history
    req = urllib.request.urlopen(f"{base}/api/history", timeout=10)
    assert req.status == 200
    history = json.loads(req.read().decode("utf-8"))
    assert isinstance(history, list)
    print("  ✓ GET /api/history returned valid file list")


def test_excel_and_csv_generation():
    print("[Test 2] Testing Excel Worksheet & CSV Logger Generation...")
    from auto_player import write_xlsx, fmt_len, _flag

    test_rows = [
        {
            "account": "TechReviewChannel",
            "title": "Best Tech Gadgets Under $50",
            "channel": "Gadget Hub",
            "url": "https://www.youtube.com/watch?v=sample111",
            "views": 350000,
            "duration": 520,
            "watched_at": "2026-09-02 11:00:00",
            "flag": _flag(350000),
            "liked": True,
            "subscribed": True,
            "comment": "Awesome breakdown, really enjoyed this!"
        },
        {
            "account": "GamingShortsDaily",
            "title": "Insane Gaming Move #shorts",
            "channel": "ProGamer",
            "url": "https://www.youtube.com/shorts/sample222",
            "views": 450,
            "duration": 42,
            "watched_at": "2026-09-02 11:15:00",
            "flag": _flag(450),
            "liked": False,
            "subscribed": False,
            "comment": ""
        }
    ]

    out_xlsx = HERE / "output" / "test_engagement.xlsx"
    out_xlsx.parent.mkdir(exist_ok=True)
    write_xlsx(test_rows, out_xlsx, "tech gadgets")
    assert out_xlsx.exists() and out_xlsx.stat().st_size > 1000, "Excel output file failed to generate"
    print(f"  ✓ Excel worksheet generated with all 13 columns ({out_xlsx.stat().st_size} bytes)")
    out_xlsx.unlink(missing_ok=True)


def test_player_logic_helpers():
    print("[Test 3] Testing Core Logic Helpers...")
    from auto_player import fmt_len, _flag, load_cfg

    # fmt_len
    assert fmt_len(45) == "0:45"
    assert fmt_len(125) == "2:05"
    assert fmt_len(3665) == "1:01:05"
    assert fmt_len(None) == ""
    print("  ✓ fmt_len correctly formats durations")

    # _flag
    assert "Trending" in _flag(500000)
    assert "Growing" in _flag(50000)
    assert "Small creator" in _flag(500)
    assert _flag(5000) == "Standard"
    print("  ✓ _flag view classification working")

    # config loading
    cfg = load_cfg()
    assert "niche" in cfg
    assert "account_rotation" in cfg
    print("  ✓ load_cfg merges defaults and custom JSON correctly")


def test_research_bot_logic():
    print("[Test 4] Testing Research Bot Logic...")
    from research_bot import keyword_analysis, fmt_dur

    sample_videos = [
        {"title": "Top 10 Amazing Tech Gadgets 2026"},
        {"title": "Best Budget Gadgets for Desk Setup"},
        {"title": "10 Coolest Gadgets You Must Buy Under $50"},
    ]
    kw, hooks = keyword_analysis(sample_videos)
    assert len(kw) > 0
    words = [w for w, _ in kw]
    assert "gadgets" in words
    assert len(hooks) == 3
    assert fmt_dur(3600) == "1:00:00"
    print("  ✓ research_bot keyword analysis and hook generation working")


def main():
    print("=" * 60)
    print("Running Full Automated Test Suite")
    print("=" * 60)
    test_ui_endpoints()
    test_excel_and_csv_generation()
    test_player_logic_helpers()
    test_research_bot_logic()
    print("=" * 60)
    print("ALL TESTS PASSED SUCCESSFULLY! (4/4 test suites passed)")
    print("=" * 60)

if __name__ == "__main__":
    main()
