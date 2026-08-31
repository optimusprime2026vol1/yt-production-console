#!/usr/bin/env python3
"""
Stage 9 - Publish. MANUAL TRIGGER ONLY.

Only ever invoked by the "Stage 9 - Publish (manual only)" workflow, which
requires a human to enter the video id and press "Run workflow" in the
GitHub Actions UI. Deliberately never wired to the heartbeat, a push
trigger, or any other automatic event - see SYSTEM_PLAN.md.

Required secrets: YOUTUBE_OAUTH_CLIENT_ID, YOUTUBE_OAUTH_CLIENT_SECRET,
                   YOUTUBE_OAUTH_REFRESH_TOKEN
Reads: assets/{id}/render.mp4, assets/{id}/metadata.json
"""
import json
import os
import sys

import requests

CLIENT_ID = os.environ.get("YOUTUBE_OAUTH_CLIENT_ID")
CLIENT_SECRET = os.environ.get("YOUTUBE_OAUTH_CLIENT_SECRET")
REFRESH_TOKEN = os.environ.get("YOUTUBE_OAUTH_REFRESH_TOKEN")
VIDEO_ID = os.environ.get("VIDEO_ID")
PRIVACY_STATUS = os.environ.get("PRIVACY_STATUS", "private")


def require_config():
    missing = [n for n, v in [
        ("YOUTUBE_OAUTH_CLIENT_ID", CLIENT_ID),
        ("YOUTUBE_OAUTH_CLIENT_SECRET", CLIENT_SECRET),
        ("YOUTUBE_OAUTH_REFRESH_TOKEN", REFRESH_TOKEN),
        ("video_id input", VIDEO_ID),
    ] if not v]
    if missing:
        print(f"Cannot publish - missing: {', '.join(missing)}")
        sys.exit(1)


def get_access_token():
    resp = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "refresh_token": REFRESH_TOKEN,
            "grant_type": "refresh_token",
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def upload_video(access_token, render_path, metadata):
    body = {
        "snippet": {
            "title": metadata["chosenTitle"][:100],
            "description": metadata["description"],
            "tags": metadata.get("tags", []),
            "categoryId": "22",
        },
        "status": {"privacyStatus": PRIVACY_STATUS},
    }
    file_size = os.path.getsize(render_path)

    init = requests.post(
        "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Length": str(file_size),
            "X-Upload-Content-Type": "video/mp4",
        },
        json=body,
        timeout=30,
    )
    init.raise_for_status()
    upload_url = init.headers["Location"]

    with open(render_path, "rb") as f:
        upload_resp = requests.put(
            upload_url,
            headers={"Content-Length": str(file_size), "Content-Type": "video/mp4"},
            data=f,
            timeout=None,
        )
    upload_resp.raise_for_status()
    return upload_resp.json()


def main():
    require_config()
    render_path = os.path.join("assets", VIDEO_ID, "render.mp4")
    metadata_path = os.path.join("assets", VIDEO_ID, "metadata.json")

    if not os.path.exists(render_path):
        print(f"No render found at {render_path}")
        sys.exit(1)
    if not os.path.exists(metadata_path):
        print(f"No metadata found at {metadata_path}")
        sys.exit(1)

    with open(metadata_path) as f:
        metadata = json.load(f)

    print(f"Publishing {VIDEO_ID} as {PRIVACY_STATUS}...")
    token = get_access_token()
    result = upload_video(token, render_path, metadata)
    print(f"Published: https://youtube.com/watch?v={result['id']}")


if __name__ == "__main__":
    main()
