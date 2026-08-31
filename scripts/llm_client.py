#!/usr/bin/env python3
"""
Shared Claude client - routes to AWS Bedrock (via the Mantle OpenAI-
compatible gateway) if BEDROCK_API_KEY is set, otherwise falls back to the
direct Anthropic API via ANTHROPIC_API_KEY.

Bedrock/Mantle only needs the API key - no separate model/inference-profile
ID lookup required, since Mantle takes a plain model name in an
OpenAI-Chat-Completions-shaped request. Optional: BEDROCK_MODEL_ID to
override the default model, AWS_REGION (default us-east-1).

Required for direct API: ANTHROPIC_API_KEY.
"""
import os

import requests

BEDROCK_API_KEY = os.environ.get("BEDROCK_API_KEY")
BEDROCK_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-sonnet-4-6")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")


def has_llm_credentials():
    return bool(BEDROCK_API_KEY) or bool(ANTHROPIC_API_KEY)


def missing_credentials_message():
    return (
        "No LLM credentials configured. Set either "
        "BEDROCK_API_KEY (Bedrock, via Mantle) "
        "or ANTHROPIC_API_KEY (direct Anthropic API)."
    )


def call_claude(prompt, max_tokens=2000):
    if BEDROCK_API_KEY:
        return _call_bedrock_mantle(prompt, max_tokens)
    if ANTHROPIC_API_KEY:
        return _call_anthropic_direct(prompt, max_tokens)
    raise RuntimeError(missing_credentials_message())


def _call_anthropic_direct(prompt, max_tokens):
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


def _call_bedrock_mantle(prompt, max_tokens):
    # Mantle is OpenAI-Chat-Completions-compatible: plain model name, no
    # inference-profile ID needed.
    url = f"https://bedrock-mantle.{AWS_REGION}.api.aws/v1/chat/completions"
    resp = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {BEDROCK_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": BEDROCK_MODEL_ID,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=180,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]
