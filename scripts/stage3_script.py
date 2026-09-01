#!/usr/bin/env python3
"""
Stage 3 - Script generation.

For each topic cycle whose approved candidate doesn't have a script yet,
asks Claude (Bedrock or direct API, see llm_client.py) to write the full
production script, then writes it to scripts-content/{id}.md.

Target runtime is configurable per candidate via "targetMinutes" (defaults
to 18 for a full-length video). Language is configurable via "language"
(defaults to "English").

New gate: after a script is generated, it sits at scriptApproved=null
(pending human review) and Stages 4/5 (voiceover, visuals) will NOT touch
it until scriptApproved is explicitly true. If a human rejects it
(scriptApproved=false, with a scriptRejectionNote), this stage regenerates
the script incorporating that note, then resets to pending again. This
catches problems - wrong language, wrong tone - at the cheap script stage
instead of after a full render.

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


def build_script_spec(minutes):
    if minutes >= 10:
        return f"""Write a full production script for a {minutes}-minute
faceless YouTube video, following this exact structure with timestamp markers:

[00:00-00:30] COLD OPEN - provocative hook, mid-scene or mid-tension, no
"hey guys welcome back". Promise a concrete payoff.
[00:30-02:00] CONTEXT / STAKES - why this matters now, plant a curiosity gap.
[02:00-{minutes - 5:02d}:00] BODY - 3 to 5 acts, each with a timestamp range,
a core idea, a concrete example, and a pattern interrupt every 45-90 seconds.
[{minutes - 5:02d}:00-{minutes - 2:02d}:00] TURN / REFRAME - the core insight, tie back to the hook.
[{minutes - 2:02d}:00-{minutes - 1:02d}:00] ACTIONABLE TAKEAWAY - 2-3 concrete, specific actions.
[{minutes - 1:02d}:00-{minutes:02d}:00] CLOSE + CTA - callback to the opening hook, one clear CTA."""
    # Short-form: same beats, no room for multiple acts.
    body_end = max(minutes - 1, 1)
    return f"""Write a full script for a {minutes}-minute faceless YouTube
video, following this compressed structure with timestamp markers:

[00:00-00:15] COLD OPEN - a hook, mid-scene or a provocative question, no
"hey guys welcome back". Promise a concrete payoff.
[00:15-00:35] CONTEXT - one or two sentences on why this matters now.
[00:35-0{body_end}:00] BODY - ONE clear idea with a concrete example - this
is a short video, don't try to cram in multiple acts.
[0{body_end}:00-{minutes:02d}:00] TAKEAWAY + CLOSE - one specific action step,
then a callback to the hook and a single clear CTA."""


SCRIPT_FOOTER = """

For every section, include a **VO:** block (the exact words to be spoken)
and a **Visual:** block (what's on screen - no AI imagery of real
identifiable people, no copyrighted characters or footage).

Timestamp rules (these are parsed by code afterward, so precision matters):
- Every section's start timestamp must exactly equal the previous
  section's end timestamp. Never restart from 00:00 partway through.
- The very last section's end timestamp must exactly equal the target
  total video length given above.

Hard rules:
- Write the ENTIRE script - VO and Visual blocks both - in {language}.
  This is not optional; do not default to English if {language} is set
  to something else.
- Never fabricate statistics, quotes, or attributions. Use soft language
  ("research suggests", "many report") for anything not independently
  verifiable, or cut the claim.
- Never invent quotes for real, named people.
- End with a "## Fact-check log" table: claim -> source basis, for every
  factual claim in the script.

Format the whole thing as markdown, matching this structure exactly so it
can be parsed programmatically later: section headers as
"## [MM:SS-MM:SS] NAME", VO as "**VO:**" followed by the spoken text,
Visual as "**Visual:**" followed by the description. Keep the section
header names and timestamps themselves in this exact English/numeric
format regardless of {language}, since code parses them - only the VO and
Visual content itself needs to be in {language}."""


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
        entry = state.get(topic_id, {})

        # Skip if: never generated yet -> proceed below.
        # Skip if: generated AND not explicitly rejected (pending review or
        # already approved) -> nothing to do here, wait for a human.
        # Proceed (regenerate) if: explicitly rejected (scriptApproved is
        # exactly False), incorporating the rejection note.
        if entry.get("scriptGenerated") and entry.get("scriptApproved") is not False:
            continue

        candidate = next((c for c in cycle["candidates"] if c["id"] == topic_id), None)
        if not candidate:
            continue

        minutes = candidate.get("targetMinutes", 18)
        language = candidate.get("language", "English")
        rejection_note = entry.get("scriptRejectionNote")

        print(f"Generating {minutes}-minute {language} script for: {candidate['title']}")
        prompt = f"""{build_script_spec(minutes)}{SCRIPT_FOOTER.format(language=language)}

Video title: {candidate['title']}
Core angle: {candidate['angle']}
Target keyword: {candidate.get('keyword', '')}"""

        if rejection_note:
            prompt += f"""

A previous draft of this script was reviewed and rejected for this
reason - address it directly in this version: {rejection_note}"""

        script_text = call_claude(prompt, max_tokens=6000)
        os.makedirs(SCRIPTS_DIR, exist_ok=True)
        out_path = os.path.join(SCRIPTS_DIR, f"{topic_id}.md")
        with open(out_path, "w") as f:
            f.write(script_text)

        entry["scriptGenerated"] = True
        entry["scriptApproved"] = None  # pending human review
        entry["scriptRejectionNote"] = None
        entry["title"] = candidate["title"]
        entry["scriptPath"] = out_path
        state[topic_id] = entry
        save_json(STATE_PATH, state)
        print(f"Wrote {out_path} - awaiting script approval before voice/visuals proceed")


if __name__ == "__main__":
    main()
