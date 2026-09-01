#!/usr/bin/env python3
"""
Stage 4 - Voiceover.

Tries ElevenLabs first (if ELEVENLABS_API_KEY is set) - better quality,
but has a character quota. Falls back to Piper TTS otherwise (or if
ElevenLabs fails partway through, e.g. quota exceeded): fully offline, no
API key, no character limit, since it runs entirely inside the GitHub
Actions runner instead of calling an external service.

Piper: pip-installed in the workflow, voice model downloaded once from
Hugging Face (~60MB), synthesizes the whole script in one pass - no
chunking needed since there's no per-request character cap.

Reads: data/pipeline-state.json, scripts-content/{id}.md
Writes: assets/{id}/voiceover-part1.mp3 (+ partN.mp3 if ElevenLabs chunks
        it), data/pipeline-state.json
"""
import glob
import json
import os
import re
import subprocess
import urllib.request

import requests

STATE_PATH = "data/pipeline-state.json"
ASSETS_DIR = "assets"
MODELS_DIR = "piper-models"

ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY") or None
ELEVENLABS_VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID") or "JBFqnCBsd6RMkjVDRZzb"
MAX_CHUNK_CHARS = 4500

PIPER_VOICE = os.environ.get("PIPER_VOICE") or "en_US-lessac-medium"
_locale, _speaker, _quality = PIPER_VOICE.split("-")
_lang = _locale.split("_")[0]
PIPER_BASE_URL = (
    f"https://huggingface.co/rhasspy/piper-voices/resolve/main/"
    f"{_lang}/{_locale}/{_speaker}/{_quality}"
)
PIPER_ONNX_URL = f"{PIPER_BASE_URL}/{PIPER_VOICE}.onnx"
PIPER_CONFIG_URL = f"{PIPER_BASE_URL}/{PIPER_VOICE}.onnx.json"


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
    # VO text can appear right after "**VO:**" on the same line, or on the
    # next line - the LLM's formatting varies, especially on shorter
    # scripts. \s* (not \s*\n) handles both.
    blocks = re.findall(
        r"\*\*VO:\*\*\s*(.*?)(?=\n\*\*Visual:\*\*|\Z)",
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


def synthesize_elevenlabs_chunk(text):
    resp = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}",
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


def run_elevenlabs(vo_blocks, out_dir):
    chunks = chunk_text(vo_blocks, MAX_CHUNK_CHARS)
    for i, chunk in enumerate(chunks, start=1):
        audio = synthesize_elevenlabs_chunk(chunk)
        out_path = os.path.join(out_dir, f"voiceover-part{i}.mp3")
        with open(out_path, "wb") as f:
            f.write(audio)
        print(f"  Wrote {out_path} ({len(chunk)} chars)")
    return len(chunks)


def ensure_piper_model():
    os.makedirs(MODELS_DIR, exist_ok=True)
    onnx_path = os.path.join(MODELS_DIR, f"{PIPER_VOICE}.onnx")
    config_path = os.path.join(MODELS_DIR, f"{PIPER_VOICE}.onnx.json")
    if not os.path.exists(onnx_path):
        print(f"  Downloading Piper voice model: {PIPER_ONNX_URL}")
        urllib.request.urlretrieve(PIPER_ONNX_URL, onnx_path)
    if not os.path.exists(config_path):
        print(f"  Downloading Piper voice config: {PIPER_CONFIG_URL}")
        urllib.request.urlretrieve(PIPER_CONFIG_URL, config_path)
    return onnx_path


def run_piper(vo_blocks, out_dir):
    onnx_path = ensure_piper_model()
    full_text = "\n\n".join(vo_blocks)
    wav_path = os.path.join(out_dir, "_voiceover.wav")
    mp3_path = os.path.join(out_dir, "voiceover-part1.mp3")

    subprocess.run(
        ["piper", "--model", onnx_path, "--output_file", wav_path],
        input=full_text,
        text=True,
        check=True,
    )
    subprocess.run(
        ["ffmpeg", "-y", "-i", wav_path, "-codec:a", "libmp3lame",
         "-qscale:a", "2", mp3_path],
        check=True,
    )
    os.remove(wav_path)
    print(f"  Wrote {mp3_path} ({len(full_text)} chars, Piper local TTS)")
    return 1


def main():
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

        out_dir = os.path.join(ASSETS_DIR, topic_id)
        os.makedirs(out_dir, exist_ok=True)
        for stale in glob.glob(os.path.join(out_dir, "voiceover-part*.mp3")):
            os.remove(stale)  # clear any partial output from a prior failed attempt

        part_count = None
        if ELEVENLABS_API_KEY:
            print("  Using ElevenLabs")
            try:
                part_count = run_elevenlabs(vo_blocks, out_dir)
            except Exception as exc:
                print(f"  ElevenLabs failed ({exc}) - falling back to Piper")
                for stale in glob.glob(os.path.join(out_dir, "voiceover-part*.mp3")):
                    os.remove(stale)  # clear partial output from the failed attempt
        if part_count is None:
            print("  Using Piper (local, free, no quota)")
            part_count = run_piper(vo_blocks, out_dir)

        entry["voiceoverReady"] = True
        entry["voiceoverParts"] = part_count
        save_json(STATE_PATH, state)


if __name__ == "__main__":
    main()
