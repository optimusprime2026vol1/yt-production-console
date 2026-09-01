#!/usr/bin/env python3
"""
Stage 6 - Edit and render.

Baseline automatic assembly, not the full hand-tuned edit described in the
original blueprint: concatenates the sourced broll per section (looped/
trimmed to that section's duration), lays the concatenated voiceover on
top, and runs basic automated QA (runtime, loudness, resolution). Output
goes to the QC queue for human review like everything else in this
pipeline.

Duration safety: per-clip trimming can drift (source clip frame rate/
timebase quirks compounding across a concat), so both the concatenated
silent video AND the final audio+video merge are additionally hard-capped
at the script's own intended total runtime (sections[-1]['end']) via an
explicit -t, on top of normal per-clip trimming and -shortest. Per-section
actual-vs-target duration is logged so drift is visible if it recurs.

Resolution is 1920x1080, not native 4K - a deliberate tradeoff to keep
render time reasonable on a shared GitHub Actions runner.

Caption burn-in is NOT implemented in this baseline - see SYSTEM_PLAN.md.

No API key needed - uses ffmpeg (installed explicitly by the workflow).

Reads: data/pipeline-state.json, assets/{id}/voiceover-*.mp3,
       assets/{id}/broll/section-*.mp4
Writes: assets/{id}/render.mp4, data/qc-queue.json, data/pipeline-state.json
"""
import glob
import json
import os
import subprocess

STATE_PATH = "data/pipeline-state.json"
QC_PATH = "data/qc-queue.json"
ASSETS_DIR = "assets"

QC_CHECKLIST_TEMPLATE = [
    {"id": "hook", "label": "Hook lands in the first 30 seconds - not a generic \"welcome back\"", "status": "pending", "note": ""},
    {"id": "facts", "label": "Claims are accurate, sourced, or softened where unverifiable", "status": "pending", "note": ""},
    {"id": "thumb", "label": "Title and thumbnail represent the actual content, no bait-and-switch", "status": "pending", "note": ""},
    {"id": "tone", "label": "Tone and framing fit brand voice and niche boundaries", "status": "pending", "note": ""},
    {"id": "visuals", "label": "Visuals feel distinct, not generic AI stock", "status": "pending", "note": ""},
    {"id": "pacing", "label": "Pacing holds - no dead stretch in the body section", "status": "pending", "note": ""},
    {"id": "cta", "label": "Close and CTA land naturally, single clear ask", "status": "pending", "note": ""},
]


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


def run(cmd):
    subprocess.run(cmd, check=True)


def ffprobe_duration(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def concat_voiceover(topic_id, out_path):
    parts = sorted(glob.glob(os.path.join(ASSETS_DIR, topic_id, "voiceover-part*.mp3")))
    if not parts:
        return None
    list_path = out_path + ".txt"
    with open(list_path, "w") as f:
        for p in parts:
            f.write(f"file '{os.path.abspath(p)}'\n")
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_path, "-c", "copy", out_path])
    os.remove(list_path)
    return out_path


def assemble_video(sections, broll_dir, voiceover_path, out_path, total_duration):
    clip_inputs = []
    for i, sec in enumerate(sections, start=1):
        clip_path = os.path.join(broll_dir, f"section-{i}.mp4")
        if not os.path.exists(clip_path):
            continue
        trimmed = os.path.join(broll_dir, f"_trimmed-{i}.mp4")
        duration = sec["duration"]
        run([
            "ffmpeg", "-y", "-stream_loop", "-1", "-i", clip_path,
            "-t", str(duration),
            "-vf", "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080",
            "-an", trimmed,
        ])
        try:
            actual = ffprobe_duration(trimmed)
            print(f"    section-{i}: target {duration}s, actual {actual:.1f}s")
        except Exception:
            pass
        clip_inputs.append(trimmed)

    if not clip_inputs:
        raise RuntimeError("No broll clips available to assemble")

    concat_list = os.path.join(broll_dir, "_concat.txt")
    with open(concat_list, "w") as f:
        for c in clip_inputs:
            f.write(f"file '{os.path.abspath(c)}'\n")
    silent_video = os.path.join(broll_dir, "_silent.mp4")
    # -t here is a safety cap: forces the concatenated result to the
    # script's intended total runtime regardless of any per-clip drift.
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_list,
         "-t", str(total_duration),
         "-c:v", "libx264", "-crf", "26", "-r", "30", "-pix_fmt", "yuv420p", silent_video])

    # Second safety cap on the final merge, on top of -shortest.
    run([
        "ffmpeg", "-y", "-i", silent_video, "-i", voiceover_path,
        "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac",
        "-b:a", "192k", "-shortest", "-t", str(total_duration), out_path,
    ])


def measure_loudness(audio_path):
    out = subprocess.run(
        ["ffmpeg", "-i", audio_path, "-af", "loudnorm=print_format=json", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    text = out.stderr
    try:
        json_str = text[text.rindex("{"):text.rindex("}") + 1]
        return json.loads(json_str).get("input_i", "unknown")
    except Exception:
        return "unknown"


def main():
    state = load_json(STATE_PATH, {})
    qc_queue = load_json(QC_PATH, [])

    for topic_id, entry in state.items():
        if not entry.get("voiceoverReady") or not entry.get("visualsReady") or entry.get("rendered"):
            continue

        print(f"Rendering {topic_id}")
        out_dir = os.path.join(ASSETS_DIR, topic_id)
        broll_dir = os.path.join(out_dir, "broll")
        voiceover_master = os.path.join(out_dir, "_voiceover-master.mp3")
        render_path = os.path.join(out_dir, "render.mp4")

        vo_path = concat_voiceover(topic_id, voiceover_master)
        if not vo_path:
            print("  No voiceover parts found - skipping")
            continue

        sections = entry.get("sections", [])
        if not sections:
            print("  No section timing found - skipping")
            continue
        total_duration = sections[-1]["end"]

        try:
            assemble_video(sections, broll_dir, vo_path, render_path, total_duration)
        except Exception as exc:
            print(f"  Render failed: {exc}")
            continue

        duration = ffprobe_duration(render_path)
        loudness = measure_loudness(vo_path)
        minutes, seconds = divmod(int(duration), 60)
        size_mb = os.path.getsize(render_path) / (1024 * 1024)

        entry["rendered"] = True
        entry["renderPath"] = render_path
        save_json(STATE_PATH, state)

        qc_queue.append({
            "id": topic_id,
            "title": entry.get("title", topic_id),
            "topic": entry.get("title", topic_id),
            "stage": "pending",
            "runtime": f"{minutes}:{seconds:02}",
            "loudness": f"{loudness} LUFS" if loudness != "unknown" else "unknown",
            "resolution": "1920x1080",
            "checklist": [dict(item) for item in QC_CHECKLIST_TEMPLATE],
            "history": [],
        })
        save_json(QC_PATH, qc_queue)
        print(f"  Added {topic_id} to QC queue - runtime {minutes}:{seconds:02}, {size_mb:.1f} MB")


if __name__ == "__main__":
    main()
