# System plan — automated production pipeline

Status: **full bridge built, end-to-end untested** — every stage below has
working code pushed to this repo. None of it has run against real
credentials yet. Add secrets per `CREDENTIALS.md`, then run the `Pipeline`
workflow manually and read the Actions logs before trusting any stage.

## Design principle: automation between gates, humans at gates

Three points always require a person, no matter how much heartbeat/cron
automation gets added later:

1. **Topic approval** — pick 1 of 3 candidates (dashboard, Topic approval tab)
2. **QC review** — pass or return-for-rectification (dashboard, QC review tab)
3. **Publish** — the video actually goes live

Publish is built as a **completely separate workflow**
(`.github/workflows/publish.yml`) that only runs on a manual
`workflow_dispatch` where a human types the video id and privacy status.
It is never called by the `Pipeline` workflow, never scheduled, and never
will be — that's not a temporary gap, it's the point.

## Why GitHub Actions, not vidIQ, for this track

Everything done earlier in this project via vidIQ (voiceover, trend data,
thumbnails) only works from inside a Claude conversation over MCP — a
GitHub Actions runner can't reach that. This automated track is built on
public, documented APIs instead: YouTube Data API, Anthropic API,
ElevenLabs, Pexels. The vidIQ-in-chat workflow still exists as a manual/
assisted alternative; this is the unattended one.

## Pipeline stages — all built

| # | Stage | Script | Trigger | Credential | Status |
|---|---|---|---|---|---|
| 1 | Trend research | `scripts/trend_research.py` | Pipeline workflow | `YOUTUBE_API_KEY` + `ANTHROPIC_API_KEY` | Built, previously test-run successfully |
| 2 | **Topic approval (human)** | — dashboard — | dashboard click | — | Built (local-storage version; repo-JSON version pending, see below) |
| 3 | Script generation | `scripts/stage3_script.py` | Pipeline workflow | `ANTHROPIC_API_KEY` | Built, untested |
| 4 | Voiceover | `scripts/stage4_voiceover.py` | Pipeline workflow | `ELEVENLABS_API_KEY` | Built, untested |
| 5 | Visual sourcing | `scripts/stage5_visuals.py` | Pipeline workflow | `PEXELS_API_KEY` | Built, untested |
| 6 | Edit & render | `scripts/stage6_render.py` | Pipeline workflow | none (ffmpeg) | Built, untested. Baseline assembly only — see "Known limitations" |
| 7 | **QC review (human)** | — dashboard — | dashboard click | — | Built (local-storage version) |
| 8 | Metadata & titles | `scripts/stage8_metadata.py` | Pipeline workflow | `ANTHROPIC_API_KEY` | Built, untested. No thumbnail yet — no image-gen credential in checklist |
| 9 | **Publish (human-triggered only)** | `scripts/publish_video.py` | separate `publish.yml`, manual only | `YOUTUBE_OAUTH_*` | Built, untested. Never wired to schedule or Pipeline |
| 10 | Analytics | — not built — | heartbeat (future) | `YOUTUBE_API_KEY` | Not started |

## How the Pipeline workflow chains stages

One workflow (`pipeline.yml`), one manual trigger for now, runs stages
1→3→4→5→6→8 as sequential steps in a single job. Each stage script checks
its own preconditions (does a decided-but-unscripted topic exist? does a
scripted-but-unvoiced video exist?) and silently no-ops if nothing's ready
or its secret is missing — so partial credential rollout never breaks the
run, it just does less. State lives in `data/pipeline-state.json` (per-video
booleans: scriptGenerated, voiceoverReady, visualsReady, rendered,
metadataReady, readyToPublish), plus the existing `data/topic-cycles.json`
and `data/qc-queue.json`.

## Known limitations (read before trusting a run)

- **Stage 6 render is a baseline, not the full blueprint edit.** It
  concatenates broll per section and lays voiceover on top. No cut-on-
  rhythm, no captions, no lower-thirds, no pattern-break at 8–10 minutes.
  Those are real, well-scoped next additions (the timing data already
  exists in the script) — not implemented now because a rushed version
  would look broken rather than simply basic.
- **No thumbnail generation.** Stage 8 does titles/description/tags only.
  Add an image-gen credential to extend it, or keep using vidIQ-in-chat for
  thumbnails specifically — it's genuinely strong at that.
- **Render resolution is 1080p, not 4K**, to keep CI render time reasonable
  on a shared runner.
- **Script-parsing regexes assume Claude's output matches the requested
  markdown structure exactly.** If Stage 3's output drifts from spec,
  Stages 5/6 will find zero sections and just skip — check Action logs.
- **The dashboard still uses per-browser local storage**, not
  `data/topic-cycles.json` / `data/qc-queue.json`. The automated pipeline
  writes to the repo files; the dashboard doesn't read them yet. Until that
  migration happens, treat the dashboard and the repo JSON as two views you
  reconcile manually, and check the JSON files directly in the repo to see
  what the pipeline actually produced.
- **Nothing here has run once.** Every stage compiles and follows documented
  API shapes, but none of it has touched a real API key. Expect to debug
  from Action logs on the first few runs.

## Repo structure

```
.github/workflows/pipeline.yml   stages 1,3,4,5,6,8 - manual now, heartbeat later
.github/workflows/publish.yml    stage 9 - always manual, never scheduled
scripts/                         one file per stage
data/                            topic-cycles.json, qc-queue.json, pipeline-state.json
scripts-content/                 generated video scripts (stage 3 output)
assets/{id}/                     voiceover-*.mp3, broll/, render.mp4, metadata.json
CREDENTIALS.md                   ordered secrets checklist
```

## Suggested first test, once secrets are in

Run the Pipeline workflow manually and watch the Actions log for each
step's print statements — every script logs what it's skipping and why.
Check `data/pipeline-state.json` after the run to see how far it got.
