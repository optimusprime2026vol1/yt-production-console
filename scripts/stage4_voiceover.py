#!/usr/bin/env python3
"""
Stage 4 - Voiceover.

For each generated script without voiceover audio yet, extracts the VO-only
text, splits it into ElevenLabs-safe chunks (~4500 chars), synthesizes each
chunk, and saves the resulting MP3s.

Required secret: ELEVENLABS_API_KEY
Reads: data/pipeline-state.json, scripts-content/{id}.md
Writes: assets/{id}/voiceover-partN.mp3, data/pipeline-state.json
"""
import json
import os
import re
import sys

import requests

ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY")
STATE_PATH = "data/pipeline-state.json"
ASSETS_DIR = "assets"
VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "JBFqnCBsd6RMkjVDRZzb")
MAX_CHUNK_CHARS = 4500


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


def extract_vo_text(script_markdown):
    blocks = re.findall(
        r"\*\*VO:\*\*\s*\n(.*?)(?=\n\*\*Visual:\*\*|\Z)",
        script_markdown,
        re.DOTALL,
    )
    return [b.strip() for b in blocks if b.strip()]


def chunk_text(blocks, max_chars):
    chunks, current = [], ""
    for block in blocks:
        candidate = (current + "\n\n" + block).strip() if current else block
        if len(candidate) > max_chars and current:
            chunks.append(current)
            current = block
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def synthesize(text):
    resp = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}",
        headers={
            "xi-api-key": ELEVENLABS_API_KEY,
            "content-type": "application/json",
            "accept": "audio/mpeg",
        },
        json={
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {"stability": 0.45, "similarity_boost": 0.75},
        },
        timeout=120,
    )
    resp.raise_for_status()
    return resp.content


def main():
    if not ELEVENLABS_API_KEY:
        print("Skipping voiceover - missing ELEVENLABS_API_KEY")
        sys.exit(0)

    state = load_json(STATE_PATH, {})

    for topic_id, entry in state.items():
        if not entry.get("scriptGenerated") or entry.get("voiceoverReady"):
            continue
        script_path = entry.get("scriptPath")
        if not script_path or not os.path.exists(script_path):
            continue

        print(f"Generating voiceover for {topic_id}")
        with open(script_path) as f:
            script_text = f.read()

        vo_blocks = extract_vo_text(script_text)
        if not vo_blocks:
            print(f"  No VO blocks found in {script_path} - skipping")
            continue

        chunks = chunk_text(vo_blocks, MAX_CHUNK_CHARS)
        out_dir = os.path.join(ASSETS_DIR, topic_id)
        os.makedirs(out_dir, exist_ok=True)
        for i, chunk in enumerate(chunks, start=1):
            audio = synthesize(chunk)
            out_path = os.path.join(out_dir, f"voiceover-part{i}.mp3")
            with open(out_path, "wb") as f:
                f.write(audio)
            print(f"  Wrote {out_path} ({len(chunk)} chars)")

        entry["voiceoverReady"] = True
        entry["voiceoverParts"] = len(chunks)
        save_json(STATE_PATH, state)


if __name__ == "__main__":
    main()
