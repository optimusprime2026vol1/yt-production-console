# Credentials checklist

Add these as GitHub repo secrets, in this order — each one unlocks exactly
one pipeline stage, so you can test incrementally instead of configuring
everything up front.

Where to add them: repo → **Settings → Secrets and variables → Actions →
New repository secret**.

## 1. `YOUTUBE_API_KEY` — unlocks Stage 1 (trend research)
- Go to [Google Cloud Console](https://console.cloud.google.com/) → create/select a project
- Enable **YouTube Data API v3**
- Credentials → Create credentials → API key
- Read-only usage here, low risk. Free quota (10,000 units/day) is more than
  enough for a few research runs a day.

## 2. `ANTHROPIC_API_KEY` — unlocks Stage 1 synthesis, Stage 3 (script), Stage 8 (metadata)
- [console.anthropic.com](https://console.anthropic.com/) → API keys → Create key
- This is the same kind of key used in the `anthropic_api_in_artifacts`
  pattern — standard `/v1/messages` endpoint.

## 3. `ELEVENLABS_API_KEY` — unlocks Stage 4 (voiceover)
- [elevenlabs.io](https://elevenlabs.io/) → Profile → API keys
- Note: this replaces the vidIQ voiceover used earlier in chat — same idea,
  callable from a script instead of only from inside a conversation.

## 4. `PEXELS_API_KEY` — unlocks Stage 5 (visual sourcing)
- [pexels.com/api](https://www.pexels.com/api/) → free, instant signup
- (Pixabay can be added as a fallback source later the same way.)

## 5. `YOUTUBE_OAUTH_CLIENT_ID`, `YOUTUBE_OAUTH_CLIENT_SECRET`, `YOUTUBE_OAUTH_REFRESH_TOKEN` — unlocks Stage 9 (publish)
- Deliberately last and most involved — full OAuth consent flow, not just an
  API key, because this is the credential that can put a video on your real
  channel.
- Build this one together when we get there rather than doing it solo —
  wrong scopes or a leaked refresh token here are the highest-consequence
  mistake in this whole checklist.
- This stage stays manual-trigger regardless of what other automation exists
  (see SYSTEM_PLAN.md) — having the credential doesn't change that.
