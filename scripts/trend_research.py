#!/usr/bin/env python3
"""
Stage 1 - Trend research.

Pulls recent high-velocity videos in the channel's niche from the YouTube Data
API, then asks Claude to synthesize them into exactly 3 candidate video topics
in the same shape the production console's Topic approval tab expects.

Required secrets (env vars): YOUTUBE_API_KEY, ANTHROPIC_API_KEY
Writes: data/topic-cycles.json (appends one new pending cycle)
"""
import json
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

import requests

YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
DATA_PATH = "data/topic-cycles.json"

# Adjust these to match the channel's actual niche.
SEED_KEYWORDS = ["discipline", "motivation", "self improvement", "resilience"]
NICHE_BRIEF = (
    "A faceless long-form YouTube channel making motivational / self-improvement "
    "videos (16-20 minutes) that reframe common advice using real psychology "
    "and behavioral-science research, not generic hype."
)


def require_secrets():
    missing = [n for n, v in [("YOUTUBE_API_KEY", YOUTUBE_API_KEY),
                               ("ANTHROPIC_API_KEY", ANTHROPIC_API_KEY)] if not v]
    if missing:
        print(f"Skipping trend research - missing secrets: {', '.join(missing)}")
        sys.exit(0)  # exit cleanly - just not configured yet, not a failure


def fetch_trending_signals():
    published_after = (datetime.now(timezone.utc) - timedelta(days=14)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    signals = []
    for kw in SEED_KEYWORDS:
        resp = requests.get(
            "https://www.googleapis.com/youtube/v3/search",
            params={
                "key": YOUTUBE_API_KEY,
                "q": kw,
                "part": "snippet",
                "type": "video",
                "order": "viewCount",
                "publishedAfter": published_after,
                "maxResults": 5,
            },
            timeout=30,
        )
        resp.raise_for_status()
        for item in resp.json().get("items", []):
            signals.append({
                "keyword": kw,
                "title": item["snippet"]["title"],
                "channel": item["snippet"]["channelTitle"],
                "publishedAt": item["snippet"]["publishedAt"],
            })
    return signals


def synthesize_candidates(signals):
    prompt = f"""You are the trend-research stage of an automated YouTube pipeline.

Channel brief: {NICHE_BRIEF}

Here are recent high-view-velocity videos in adjacent keyword searches:
{json.dumps(signals, indent=2)}

Produce exactly 3 candidate video topics for this channel's next video, as a
JSON array. Each candidate must have: "title" (a real, non-clickbait video
title), "angle" (one sentence, the specific reframe/insight), "keyword" (2-4
word search phrase), "volume" (a short plain-language estimate of search
interest based on the signals above), "competition" (a short plain-language
read of how saturated this specific angle is based on the signals).

Ground every claim in the signals provided - do not invent view counts or
statistics not implied by the data above. Return ONLY the JSON array, no
other text."""

    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": "claude-sonnet-4-6",
            "max_tokens": 1500,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=60,
    )
    resp.raise_for_status()
    text = resp.json()["content"][0]["text"].strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text.split("\n", 1)[1] if "\n" in text else text
        text = text.rsplit("```", 1)[0]
    return json.loads(text)


def main():
    require_secrets()
    signals = fetch_trending_signals()
    if not signals:
        print("No trend signals returned - skipping this run.")
        return
    candidates = synthesize_candidates(signals)
    for c in candidates:
        c["id"] = str(uuid.uuid4())[:8]

    try:
        with open(DATA_PATH) as f:
            store = json.load(f)
    except FileNotFoundError:
        store = []

    store.append({
        "id": str(uuid.uuid4())[:8],
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "status": "pending",
        "approvedId": None,
        "candidates": candidates,
    })

    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    with open(DATA_PATH, "w") as f:
        json.dump(store, f, indent=2)
    print(f"Wrote new cycle with {len(candidates)} candidates.")


if __name__ == "__main__":
    main()
