#!/usr/bin/env python3
"""
Stage 5 - Visual sourcing.

For each scripted video, reads each section's **Visual:** cue and section
duration, and pulls a matching stock clip from Pexels for each one. Only
depends on the script existing - not on voiceover being ready, since
sourcing visuals doesn't need audio to already exist. (Stage 6, the
render, is what needs both to be ready.)

Section parsing is two-step: first find every ## or ### timestamped
header, then take each header's own text block (up to the NEXT header,
whichever level) and look for a **Visual:** cue only within that block.
This matters because a script has both outer "## BODY" umbrella headers
and inner "### ACT ONE" sub-headers - a single-pass regex can accidentally
tunnel from an outer header past its own sub-headers to grab a sub-section's
Visual text, mislabeling it with the outer header's much longer timestamp
range. The umbrella header's own block (empty, just its sub-headers) has no
Visual of its own and is correctly skipped instead of producing a bad entry.

Required secret: PEXELS_API_KEY
Reads: data/pipeline-state.json, scripts-content/{id}.md
Writes: assets/{id}/broll/section-N.mp4, assets/{id}/broll/credits.json
"""
import json
import os
import re
import sys

import requests

PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY") or None
STATE_PATH = "data/pipeline-state.json"
ASSETS_DIR = "assets"

HEADER_RE = re.compile(
    r"^#{2,3}\s*\[(\d{2}):(\d{2})[-\u2013](\d{2}):(\d{2})\][^\n]*$",
    re.MULTILINE,
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
    headers = list(HEADER_RE.finditer(script_text))
    sections = []
    for i, m in enumerate(headers):
        start = int(m.group(1)) * 60 + int(m.group(2))
        end = int(m.group(3)) * 60 + int(m.group(4))
        block_start = m.end()
        block_end = headers[i + 1].start() if i + 1 < len(headers) else len(script_text)
        block = script_text[block_start:block_end]

        visual_match = re.search(r"\*\*Visual:\*\*\s*\n(.*?)(?=\n---|\Z)", block, re.DOTALL)
        if not visual_match:
            continue  # umbrella header (e.g. "## BODY") with no direct Visual of its own

        sections.append({
            "start": start,
            "end": end,
            "duration": max(end - start, 1),
            "visual": visual_match.group(1).strip(),
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
        if not entry.get("scriptGenerated") or entry.get("visualsReady"):
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
