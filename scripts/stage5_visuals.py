#!/usr/bin/env python3
"""
Stage 5 - Visual sourcing.

For each scripted video with voiceover ready, reads each section's
**Visual:** cue and section duration, and pulls a matching stock clip from
Pexels for each one.

Required secret: PEXELS_API_KEY
Reads: data/pipeline-state.json, scripts-content/{id}.md
Writes: assets/{id}/broll/section-N.mp4, assets/{id}/broll/credits.json
"""
import json
import os
import re
import sys

import requests

PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")
STATE_PATH = "data/pipeline-state.json"
ASSETS_DIR = "assets"

SECTION_RE = re.compile(
    r"##\s*\[(\d{2}):(\d{2})[-\u2013](\d{2}):(\d{2})\][^\n]*\n"
    r"(?:.*?\*\*VO:\*\*\s*\n.*?)?"
    r"\*\*Visual:\*\*\s*\n(.*?)(?=\n##|\n---|\Z)",
    re.DOTALL,
)


def load_json(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def save_json(path, data):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def parse_sections(script_text):
    sections = []
    for m in SECTION_RE.finditer(script_text):
        start = int(m.group(1)) * 60 + int(m.group(2))
        end = int(m.group(3)) * 60 + int(m.group(4))
        visual_desc = m.group(5).strip()
        sections.append({
            "start": start,
            "end": end,
            "duration": max(end - start, 1),
            "visual": visual_desc,
        })
    return sections


def to_search_query(visual_desc):
    first_clause = re.split(r"[.:]", visual_desc)[0]
    words = re.findall(r"[A-Za-z]+", first_clause)
    stopwords = {"a", "an", "the", "on", "of", "to", "with", "and", "then",
                 "cut", "close", "up", "style", "shot"}
    keep = [w for w in words if w.lower() not in stopwords]
    return " ".join(keep[:6]) or "abstract background"


def search_pexels(query):
    resp = requests.get(
        "https://api.pexels.com/videos/search",
        headers={"Authorization": PEXELS_API_KEY},
        params={"query": query, "per_page": 3, "orientation": "landscape"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json().get("videos", [])


def pick_video_file(video):
    files = sorted(video.get("video_files", []), key=lambda f: f.get("width", 0))
    for f in files:
        if f.get("width", 0) <= 1920 and f.get("file_type") == "video/mp4":
            return f
    return files[-1] if files else None


def main():
    if not PEXELS_API_KEY:
        print("Skipping visual sourcing - missing PEXELS_API_KEY")
        sys.exit(0)

    state = load_json(STATE_PATH, {})

    for topic_id, entry in state.items():
        if not entry.get("voiceoverReady") or entry.get("visualsReady"):
            continue
        script_path = entry.get("scriptPath")
        if not script_path or not os.path.exists(script_path):
            continue

        print(f"Sourcing visuals for {topic_id}")
        with open(script_path) as f:
            script_text = f.read()

        sections = parse_sections(script_text)
        if not sections:
            print("  No sections parsed - skipping")
            continue

        broll_dir = os.path.join(ASSETS_DIR, topic_id, "broll")
        os.makedirs(broll_dir, exist_ok=True)
        credits = []

        for i, section in enumerate(sections, start=1):
            query = to_search_query(section["visual"])
            results = search_pexels(query)
            if not results:
                print(f"  Section {i}: no results for '{query}'")
                continue
            video = results[0]
            file_info = pick_video_file(video)
            if not file_info:
                continue
            out_path = os.path.join(broll_dir, f"section-{i}.mp4")
            data = requests.get(file_info["link"], timeout=120)
            data.raise_for_status()
            with open(out_path, "wb") as f:
                f.write(data.content)
            credits.append({
                "section": i,
                "query": query,
                "photographer": video.get("user", {}).get("name"),
                "source_url": video.get("url"),
                "duration_needed": section["duration"],
            })
            print(f"  Section {i}: '{query}' -> {out_path}")

        with open(os.path.join(broll_dir, "credits.json"), "w") as f:
            json.dump(credits, f, indent=2)

        entry["visualsReady"] = True
        entry["sections"] = sections
        save_json(STATE_PATH, state)


if __name__ == "__main__":
    main()
