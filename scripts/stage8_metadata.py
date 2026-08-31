#!/usr/bin/env python3
"""
Stage 8 - Metadata and titles.

For each QC-queue entry a human has approved, asks Claude (Bedrock or
direct API, see llm_client.py) for title variants, a description, and tags.
Thumbnail generation is not wired yet.

Required: LLM credentials (see llm_client.py)
Reads: data/qc-queue.json, data/pipeline-state.json, scripts-content/{id}.md
Writes: assets/{id}/metadata.json, data/pipeline-state.json
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from llm_client import call_claude, has_llm_credentials, missing_credentials_message

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


def main():
    if not has_llm_credentials():
        print(f"Skipping metadata generation - {missing_credentials_message()}")
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

        text = call_claude(prompt, max_tokens=1200).strip()
        if text.startswith("```"):
            text = text.strip("`")
            text = text.split("\n", 1)[1] if "\n" in text else text
            text = text.rsplit("```", 1)[0]
        metadata = json.loads(text)

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
