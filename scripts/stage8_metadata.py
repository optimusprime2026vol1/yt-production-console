#!/usr/bin/env python3
"""
Stage 8 - Metadata and titles.

For each QC-queue entry a human has approved, asks Claude for title
variants, a description with chapter timestamps, and a tag list.
Thumbnail generation is not wired yet - no image-gen credential is in
CREDENTIALS.md; add one (e.g. STABILITY_API_KEY) later to extend this stage.

Required secret: ANTHROPIC_API_KEY
Reads: data/qc-queue.json, data/pipeline-state.json, scripts-content/{id}.md
Writes: assets/{id}/metadata.json, data/pipeline-state.json
"""
import json
import os
import sys

import requests

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
QC_PATH = "data/qc-queue.json"
STATE_PATH = "data/pipeline-state.json"
ASSETS_DIR = "assets"


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


def call_claude(prompt, max_tokens=1200):
    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": "claude-sonnet-4-6",
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=90,
    )
    resp.raise_for_status()
    text = resp.json()["content"][0]["text"].strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text.split("\n", 1)[1] if "\n" in text else text
        text = text.rsplit("```", 1)[0]
    return json.loads(text)


def main():
    if not ANTHROPIC_API_KEY:
        print("Skipping metadata generation - missing ANTHROPIC_API_KEY")
        sys.exit(0)

    qc_queue = load_json(QC_PATH, [])
    state = load_json(STATE_PATH, {})

    for video in qc_queue:
        topic_id = video["id"]
        if video.get("stage") != "approved":
            continue
        if state.get(topic_id, {}).get("metadataReady"):
            continue

        script_path = os.path.join("scripts-content", f"{topic_id}.md")
        script_text = ""
        if os.path.exists(script_path):
            with open(script_path) as f:
                script_text = f.read()

        print(f"Generating metadata for {topic_id}")
        prompt = f"""Based on this video script, produce YouTube metadata as
JSON with keys: "titles" (5 title variants, 50-60 chars, primary keyword
near the front), "chosenTitle" (your pick of the 5), "description" (2-3
sentence hook, then a bullet list of takeaways, no fabricated links),
"tags" (15-25 tags, broad + long-tail). Return ONLY the JSON object.

Script:
{script_text[:12000]}"""

        metadata = call_claude(prompt)
        out_path = os.path.join(ASSETS_DIR, topic_id, "metadata.json")
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w") as f:
            json.dump(metadata, f, indent=2)

        state.setdefault(topic_id, {})["metadataReady"] = True
        state[topic_id]["readyToPublish"] = True
        save_json(STATE_PATH, state)
        print(f"  Wrote {out_path} - ready for manual publish")


if __name__ == "__main__":
    main()
