          # Credentials checklist

Add these as GitHub repo secrets — **Settings → Secrets and variables →
Actions → New repository secret**. All the stage code is already pushed and
waiting; each secret you add unlocks the corresponding stage on the next
Pipeline run.

## LLM credential — pick ONE of these two (Stages 1 synthesis, 3, 8)

**Option A — AWS Bedrock** (what this project is currently set up to use)
- `AWS_BEARER_TOKEN_BEDROCK` — generate from the Bedrock console's **API
  keys** page. This is AWS's simpler bearer-token key type, not a full
  AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY pair, and not full SigV4 signing.
- `BEDROCK_MODEL_ID` — the exact Claude model/inference-profile id for your
  account and region, copied from the Bedrock console. This is **not** the
  same string as the direct API's model name (e.g. it may look like
  `us.anthropic.claude-...-v1:0`) — copy it exactly, don't guess it.
- `AWS_REGION` — optional, defaults to `us-east-1` if not set.

**Option B — direct Anthropic API**
- `ANTHROPIC_API_KEY` — [console.anthropic.com](https://console.anthropic.com/) → API keys → Create key
- Must be a real key from that page — a Bedrock key here will fail with a
  401, the two auth types aren't interchangeable.

`scripts/llm_client.py` checks for Bedrock credentials first, falls back to
`ANTHROPIC_API_KEY` if Bedrock isn't set. You only need one of the two —
if both are present, Bedrock wins.

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
