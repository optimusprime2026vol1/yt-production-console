# System plan — automated production pipeline

Status: **stages 1, 3, and 5 confirmed working end-to-end with real
credentials and real output.** Stage 4 (voiceover) is confirmed working
via Piper fallback (ElevenLabs works too, up to its character quota).
Stages 6, 8, 9 are built and syntax-checked but not yet run to completion.
See the table below for the honest per-stage status.

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

## LLM and voice backends (each stage tries in order, first available wins)

- **Script/metadata/research (Stages 1, 3, 8):** DeepSeek → AWS Bedrock →
  direct Anthropic API. Configured via `scripts/llm_client.py`. DeepSeek
  is currently the one actually being used (only DeepSeek credentials are
  set as of this writing).
- **Voiceover (Stage 4):** ElevenLabs → Piper TTS (local, free, no quota,
  runs inside the GitHub Actions runner itself — see
  `scripts/stage4_voiceover.py`). If ElevenLabs fails partway (e.g. quota
  exceeded), it automatically falls back to Piper for that run rather than
  failing the stage.

## Pipeline stages — real status

| # | Stage | Script | Credential(s) | Status |
|---|---|---|---|---|
| 1 | Trend research | `scripts/trend_research.py` | `YOUTUBE_API_KEY` + one LLM credential | Built. Runs cleanly when its secrets are set; skips cleanly otherwise |
| 2 | **Topic approval (human)** | — dashboard — | — | Built. Dashboard now fetches live `data/topic-cycles.json` from the repo (see "Dashboard sync" below) |
| 3 | Script generation | `scripts/stage3_script.py` | one LLM credential | **Confirmed working** — real ~2,850-word script generated via DeepSeek for the approved topic, following the full structure spec with a fact-check log |
| 4 | Voiceover | `scripts/stage4_voiceover.py` | `ELEVENLABS_API_KEY` (optional) | **Confirmed working** — Piper fallback produces a full voiceover with no quota limit; ElevenLabs path also confirmed (partial, quota-limited on the free tier) |
| 5 | Visual sourcing | `scripts/stage5_visuals.py` | `PEXELS_API_KEY` | **Confirmed working** — 10 real broll clips downloaded and correctly time-matched to script sections (after fixing a header-parsing bug that originally mislabeled one section's duration) |
| 6 | Edit & render | `scripts/stage6_render.py` | none (ffmpeg) | Built, not yet run to completion. Depends on Stage 4 + 5 both being ready in the same pipeline-state entry |
| 7 | **QC review (human)** | — dashboard — | — | Built. Dashboard now fetches live `data/qc-queue.json` from the repo |
| 8 | Metadata & titles | `scripts/stage8_metadata.py` | one LLM credential | Built, not yet run — needs a QC-approved video first, which needs Stage 6 to have produced one |
| 9 | **Publish (human-triggered only)** | `scripts/publish_video.py` | `YOUTUBE_OAUTH_*` | Built, untested. Never wired to schedule or Pipeline |
| 10 | Analytics | — not built — | heartbeat (future) | Not started |

## Dashboard sync (new)

`index.html` now fetches `data/topic-cycles.json` and `data/qc-queue.json`
live from `raw.githubusercontent.com` on load, instead of using hardcoded
seed data. Any topic Stage 1 generates or video Stage 6 renders shows up
automatically next time the dashboard is opened. Human decisions (approve
a topic, pass/flag a checklist item) still save to browser local storage
only — writing a decision back into the repo itself still isn't wired up,
since that needs either a user-supplied GitHub token entered client-side
or a small backend, neither built yet. Practically: the dashboard always
shows the pipeline's latest output, and your own decisions persist on
whichever device/browser you made them on.

## How the Pipeline workflow chains stages

One workflow (`pipeline.yml`), manual trigger for now, runs stages
1→3→4→5→6→8 as sequential steps in a single job, each with
`continue-on-error: true` so one stage failing doesn't discard work an
earlier, independent stage already did in the same run — the final commit
step runs with `if: always()` for the same reason. Each stage script
checks its own preconditions and silently no-ops if nothing's ready or
its secret is missing. State lives in `data/pipeline-state.json`
(per-video booleans: scriptGenerated, voiceoverReady, visualsReady,
rendered, metadataReady, readyToPublish).

## Known limitations (read before trusting a run)

- **Stage 6 render is a baseline, not the full blueprint edit.** It
  concatenates broll per section and lays voiceover on top. No cut-on-
  rhythm, no captions, no lower-thirds, no pattern-break at 8–10 minutes.
- **No thumbnail generation in the pipeline.** Stage 8 does titles/
  description/tags only. A real thumbnail was generated manually via
  vidIQ earlier in this project and archived to `assets/t2-thumbnail-v1.png`
  — extending Stage 8 with an image-gen credential is the automatable path.
- **Render resolution is 1080p, not 4K**, to keep CI render time reasonable
  on a shared runner.
- **GitHub Actions sets a secret-backed env var to an empty string (not
  unset) when the secret doesn't exist.** Any code using
  `os.environ.get(key, default)` gets `""`, not `default`, in that case —
  every optional value in this codebase now uses `os.environ.get(key) or
  default` instead. Worth remembering if adding new optional secrets.
- **Dashboard decisions don't write back to the repo** — see "Dashboard
  sync" above.

## Repo structure

```
.github/workflows/pipeline.yml   stages 1,3,4,5,6,8 - manual now, heartbeat later
.github/workflows/publish.yml    stage 9 - always manual, never scheduled
scripts/llm_client.py            shared LLM router: DeepSeek -> Bedrock -> direct API
scripts/                         one file per stage
data/                            topic-cycles.json, qc-queue.json, pipeline-state.json
scripts-content/                 generated video scripts (stage 3 output)
assets/{id}/                     voiceover-*.mp3, broll/, render.mp4, metadata.json
index.html                       dashboard - now syncs live from data/*.json
CREDENTIALS.md                   ordered secrets checklist
```

## Suggested next test

Once ElevenLabs (or Piper, already working) produces voiceover and
visuals exist for a video, run the Pipeline workflow again and check
whether Stage 6 successfully produces `assets/{id}/render.mp4` and adds
an entry to `data/qc-queue.json`. Then open the dashboard to confirm the
video shows up there automatically.
