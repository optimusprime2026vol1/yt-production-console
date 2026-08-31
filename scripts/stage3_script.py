#!/usr/bin/env python3
"""
Stage 3 - Script generation.

For each topic cycle whose approved candidate doesn't have a script yet,
asks Claude (Bedrock or direct API, see llm_client.py) to write the full
production script, then writes it to scripts-content/{id}.md.

Required: LLM credentials (see llm_client.py)
Reads: data/topic-cycles.json
Writes: scripts-content/{id}.md, data/pipeline-state.json
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from llm_client import call_claude, has_llm_credentials, missing_credentials_message

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


def main():
    if not has_llm_credentials():
        print(f"Skipping script generation - {missing_credentials_message()}")
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

        script_text = call_claude(prompt, max_tokens=6000)
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
