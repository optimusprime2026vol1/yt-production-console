# System plan — automated production pipeline

This extends the production console (topic approval + QC dashboard) with a
self-running backend. GitHub Actions does the automatable work; humans still
decide at three fixed points. That split doesn't change as automation grows.

## Why GitHub Actions, not vidIQ, for the automated track

Everything done earlier in this project via vidIQ (voiceover, trend data,
thumbnails) only works because it's called from inside a Claude conversation
over MCP — a GitHub Actions runner has no access to that connection. So the
self-running pipeline is built on **public, documented APIs** instead:
YouTube Data API, Anthropic API, ElevenLabs, Pexels/Pixabay. The vidIQ-in-chat
workflow still exists as a manual/assisted path; this is the unattended one.

## Design principle: automation between gates, humans at gates

Three points always require a person, regardless of how much heartbeat/cron
automation gets added later:

1. **Topic approval** — pick 1 of 3 candidates (dashboard, Topic approval tab)
2. **QC review** — pass or return-for-rectification (dashboard, QC review tab)
3. **Publish** — the video actually goes live

Publish in particular is deliberately **never** wired to the heartbeat or any
scheduled trigger. It only runs on an explicit manual `workflow_dispatch`,
same as a human pressing a button. Everything else — research, script,
voice, visuals, assembly, technical QA — can run unattended once its
credential exists.

## Pipeline stages

| # | Stage | Trigger | Reads | Writes | API / credential |
|---|---|---|---|---|---|
| 1 | Trend research | manual now → heartbeat later | seed keywords | `data/topic-cycles.json` (new pending cycle, 3 candidates) | `YOUTUBE_API_KEY` + `ANTHROPIC_API_KEY` |
| 2 | **Topic approval (human)** | dashboard click | `data/topic-cycles.json` | same file, `status: decided` | — |
| 3 | Script generation | on approved topic | approved candidate | `scripts/{id}.md` + fact-check log | `ANTHROPIC_API_KEY` |
| 4 | Voiceover | on new script | script VO text | `assets/{id}/voiceover-*.mp3` | `ELEVENLABS_API_KEY` |
| 5 | Visual sourcing | on new script | script visual-cue column | `assets/{id}/broll/*.mp4` + license log | `PEXELS_API_KEY` |
| 6 | Edit & render | on voice + visuals ready | above assets | `assets/{id}/render.mp4` + technical QA (loudness, resolution, runtime) | ffmpeg (no key needed, preinstalled on runners) |
| 7 | **QC review (human)** | dashboard click | rendered video + auto-QA results | `data/qc-queue.json` — pass → step 8, fail → rectification notes back to step 3 | — |
| 8 | Metadata & thumbnail | on QC pass | approved video | title/description/tags, thumbnail | `ANTHROPIC_API_KEY` (+ image gen, TBD) |
| 9 | **Publish (human-triggered only)** | manual `workflow_dispatch` | finished video + metadata | live YouTube video | `YOUTUBE_OAUTH_*` |
| 10 | Analytics | heartbeat | published video stats | feeds back into stage 1 scoring | `YOUTUBE_API_KEY` (Analytics scope) |

## Build order (matches "add credentials one by one")

Each stage is built and wired as its credential arrives, so nothing sits
half-finished waiting on a key that doesn't exist yet:

- [x] **Stage 1 — Trend research.** Built now (`.github/workflows/trend-research.yml`,
  `scripts/trend_research.py`). Needs `YOUTUBE_API_KEY` + `ANTHROPIC_API_KEY`.
  Runs on manual dispatch until the heartbeat is added.
- [ ] Stage 3 — Script generation. Builds next, once you confirm Stage 1 output
  looks right.
- [ ] Stage 4 — Voiceover (ElevenLabs).
- [ ] Stage 5 — Visual sourcing (Pexels/Pixabay).
- [ ] Stage 6 — Edit & render (ffmpeg assembly + automated QA checklist from
  the original blueprint: runtime, LUFS, resolution, caption accuracy).
- [ ] Stage 8 — Metadata & thumbnail.
- [ ] Stage 9 — Publish. Built last, deliberately — this is the one stage
  that stays manual-trigger forever, not just until it's "working."
- [ ] Heartbeat — a `schedule:` cron added to stage 1 (and eventually 10),
  once the earlier stages are confirmed working on manual runs. Publish is
  excluded from this by design, not by omission.

## Data layer

`data/topic-cycles.json` and `data/qc-queue.json` are the source of truth
going forward — both readable by Actions and (once wired) by the dashboard
via `raw.githubusercontent.com`. The dashboard currently still uses per-browser
local storage from before this automation existed; migrating it to read these
repo files (and write back via a user-supplied GitHub token, entered once,
never leaving the browser) is the next dashboard update, not done in this pass.

## Repo structure

```
.github/workflows/    one workflow per stage
scripts/              the actual stage logic (Python)
data/                 topic-cycles.json, qc-queue.json — pipeline state
assets/               generated audio/video, committed via the auto-fetch pattern
scripts-content/      generated video scripts (stage 3 output)
CREDENTIALS.md         ordered secrets checklist
```
