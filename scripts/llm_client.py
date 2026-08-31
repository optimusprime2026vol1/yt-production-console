#!/usr/bin/env python3
"""
Shared Claude client - direct Anthropic API only.

Required: ANTHROPIC_API_KEY (a real key from console.anthropic.com - not
a Bedrock key, they use different auth and are not interchangeable).
"""
import os

import requests

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")


def has_llm_credentials():
    return bool(ANTHROPIC_API_KEY)


def missing_credentials_message():
    return "No LLM credentials configured. Set ANTHROPIC_API_KEY."


def call_claude(prompt, max_tokens=2000):
    if not ANTHROPIC_API_KEY:
        raise RuntimeError(missing_credentials_message())
    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": "claude-sonnet-4-6",
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=180,
    )
    resp.raise_for_status()
    return resp.json()["content"][0]["text"]
