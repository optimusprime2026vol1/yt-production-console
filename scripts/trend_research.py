#!/usr/bin/env python3
"""
Stage 1 - Trend research.

Pulls recent high-velocity videos in the channel's niche from the YouTube
Data API, then asks Claude (Bedrock or direct API, see llm_client.py) to
synthesize them into exactly 3 candidate video topics in the shape the
production console's Topic approval tab expects.

Required: YOUTUBE_API_KEY, plus LLM credentials (see llm_client.py)
Writes: data/topic-cycles.json (appends one new pending cycle)
"""
import json
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from llm_client import call_claude, has_llm_credentials, missing_credentials_message

YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")
DATA_PATH = "data/topic-cycles.json"

SEED_KEYWORDS = ["discipline", "motivation", "self improvement", "resilience"]
NICHE_BRIEF = (
    "A faceless long-form YouTube channel making motivational / self-improvement "
    "videos (16-20 minutes) that reframe common advice using real psychology "
    "and behavioral-science research, not generic hype."
)


def require_secrets():
    missing = []
    if not YOUTUBE_API_KEY:
        missing.append("YOUTUBE_API_KEY")
    if not has_llm_credentials():
        missing.append("LLM credentials (" + missing_credentials_message() + ")")
    if missing:
        print(f"Skipping trend research - missing: {', '.join(missing)}")
        sys.exit(0)


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
JSON array. Each candidate must have: "title", "angle", "keyword", "volume",
"competition". Ground every claim in the signals provided. Return ONLY the
JSON array, no other text."""

    text = call_claude(prompt, max_tokens=1500).strip()
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
