          # Credentials checklist

Add these as GitHub repo secrets — **Settings → Secrets and variables →
Actions → New repository secret**. All the stage code is already pushed and
waiting; each secret you add unlocks the corresponding stage on the next
Pipeline run.

## `ANTHROPIC_API_KEY` — Stages 1 (synthesis), 3 (script), 8 (metadata)
- [console.anthropic.com](https://console.anthropic.com/) → API keys → Create key
- This must be a real key from that page — a Bedrock key will fail here
  with a 401, since Bedrock and the direct Anthropic API use different
  auth and aren't interchangeable. (Bedrock support was removed from this
  project on request — `scripts/llm_client.py` now only talks to the
  direct Anthropic API.)

## `YOUTUBE_API_KEY` — Stage 1 (trend research)
- [Google Cloud Console](https://console.cloud.google.com/) → enable **YouTube Data API v3** → Credentials → API key
- Read-only, low risk, generous free quota

## `ELEVENLABS_API_KEY` — Stage 4 (voiceover)
- [elevenlabs.io](https://elevenlabs.io/) → Profile → API keys
- Optional: `ELEVENLABS_VOICE_ID` to override the default voice (same
  "George" voice used earlier in this project: `JBFqnCBsd6RMkjVDRZzb`)

## `PEXELS_API_KEY` — Stage 5 (visual sourcing)
- [pexels.com/api](https://www.pexels.com/api/) — free, instant

## `YOUTUBE_OAUTH_CLIENT_ID`, `YOUTUBE_OAUTH_CLIENT_SECRET`, `YOUTUBE_OAUTH_REFRESH_TOKEN` — Stage 9 (publish)
- Full OAuth consent flow, not just an API key — build this one together
  rather than solo, since a leaked refresh token here is the
  highest-consequence mistake in this whole checklist
- Having this credential does **not** make publishing automatic — it only
  enables the separate, manual-only `publish.yml` workflow

## Not yet in the checklist

- An image-gen key (e.g. `STABILITY_API_KEY`) for thumbnails — Stage 8
  currently produces titles/description/tags only
- Anything for Stage 10 (analytics) — not built yet
