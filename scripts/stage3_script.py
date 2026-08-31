#!/usr/bin/env python3
"""
Stage 3 - Script generation.

For each topic cycle whose approved candidate doesn't have a script yet,
asks Claude to write the full production script (cold open through close,
with visual cues and a fact-check log) in the structure used throughout
this project, then writes it to scripts-content/{id}.md.

Required secret: ANTHROPIC_API_KEY
Reads: data/topic-cycles.json
Writes: scripts-content/{id}.md, data/pipeline-state.json
"""
import json
import os
import sys

import requests

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
TOPICS_PATH = "data/topic-cycles.json"
STATE_PATH = "data/pipeline-state.json"
SCRIPTS_DIR = "scripts-content"

SCRIPT_SPEC = """Write a full production script for a 16-20 minute faceless
YouTube video, following this exact structure with timestamp markers:

[00:00-00:30] COLD OPEN - provocative hook, mid-scene or mid-tension, no
"hey guys welcome back". Promise a concrete payoff.
[00:30-02:00] CONTEXT / STAKES - why this matters now, plant a curiosity gap.
[02:00-14:00] BODY - 3 to 5 acts, each with a timestamp range, a core idea,
a concrete example, and a pattern interrupt every 45-90 seconds.
[14:00-17:00] TURN / REFRAME - the core insight, tie back to the hook.
[17:00-19:00] ACTIONABLE TAKEAWAY - 2-3 concrete, specific actions.
[19:00-19:30] CLOSE + CTA - callback to the opening hook, one clear CTA.

For every section, include a **VO:** block (the exact words to be spoken)
and a **Visual:** block (what's on screen - no AI imagery of real
identifiable people, no copyrighted characters or footage).

Hard rules:
- Never fabricate statistics, quotes, or attributions. Use soft language
  ("research suggests", "many report") for anything not independently
  verifiable, or cut the claim.
- Never invent quotes for real, named people.
- End with a "## Fact-check log" table: claim -> source basis, for every
  factual claim in the script.

Format the whole thing as markdown, matching this structure exactly so it
can be parsed programmatically later: section headers as
"## [MM:SS-MM:SS] NAME", VO as "**VO:**" followed by the spoken text,
Visual as "**Visual:**" followed by the description."""


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


def call_claude(prompt, max_tokens=6000):
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
        timeout=180,
    )
    resp.raise_for_status()
    return resp.json()["content"][0]["text"]


def main():
    if not ANTHROPIC_API_KEY:
        print("Skipping script generation - missing ANTHROPIC_API_KEY")
        sys.exit(0)

    cycles = load_json(TOPICS_PATH, [])
    state = load_json(STATE_PATH, {})

    for cycle in cycles:
        if cycle.get("status") != "decided" or not cycle.get("approvedId"):
            continue
        topic_id = cycle["approvedId"]
        if state.get(topic_id, {}).get("scriptGenerated"):
            continue
        candidate = next((c for c in cycle["candidates"] if c["id"] == topic_id), None)
        if not candidate:
            continue

        print(f"Generating script for: {candidate['title']}")
        prompt = f"""{SCRIPT_SPEC}

Video title: {candidate['title']}
Core angle: {candidate['angle']}
Target keyword: {candidate.get('keyword', '')}"""

        script_text = call_claude(prompt)
        os.makedirs(SCRIPTS_DIR, exist_ok=True)
        out_path = os.path.join(SCRIPTS_DIR, f"{topic_id}.md")
        with open(out_path, "w") as f:
            f.write(script_text)

        state.setdefault(topic_id, {})["scriptGenerated"] = True
        state[topic_id]["title"] = candidate["title"]
        state[topic_id]["scriptPath"] = out_path
        save_json(STATE_PATH, state)
        print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
