#!/usr/bin/env python3
"""
Shared Claude client - tries DeepSeek first (if DEEPSEEK_API_KEY is set),
then standard AWS Bedrock (if BEDROCK_API_KEY is set), then falls back to
the direct Anthropic API via ANTHROPIC_API_KEY. Only one is required.

DeepSeek: OpenAI-Chat-Completions-compatible, just an API key, no region
or model-access setup needed - https://api.deepseek.com/chat/completions

Bedrock: standard InvokeModel endpoint, AWS bearer-token API key from the
Bedrock console's "API keys" page, plus your account/region needing model
access granted for Claude (Bedrock console -> Model access).

Direct API: a real key from console.anthropic.com.

NOTE: GitHub Actions sets a secret-backed env var to an EMPTY STRING (not
unset) when the secret doesn't exist. os.environ.get(key, default) only
falls back to default when the key is truly absent, not when it's "" - so
every optional value below uses `or` instead, which treats "" as unset too.
"""
import os

import requests

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY") or None
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL") or "deepseek-chat"

BEDROCK_API_KEY = os.environ.get("BEDROCK_API_KEY") or None
BEDROCK_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID") or "anthropic.claude-sonnet-4-6"
AWS_REGION = os.environ.get("AWS_REGION") or "us-east-1"

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY") or None


def has_llm_credentials():
    return bool(DEEPSEEK_API_KEY) or bool(BEDROCK_API_KEY) or bool(ANTHROPIC_API_KEY)


def missing_credentials_message():
    return (
        "No LLM credentials configured. Set one of: DEEPSEEK_API_KEY, "
        "BEDROCK_API_KEY (AWS Bedrock), or ANTHROPIC_API_KEY (direct API)."
    )


def call_claude(prompt, max_tokens=2000):
    if DEEPSEEK_API_KEY:
        return _call_deepseek(prompt, max_tokens)
    if BEDROCK_API_KEY:
        return _call_bedrock(prompt, max_tokens)
    if ANTHROPIC_API_KEY:
        return _call_anthropic_direct(prompt, max_tokens)
    raise RuntimeError(missing_credentials_message())


def _call_deepseek(prompt, max_tokens):
    resp = requests.post(
        "https://api.deepseek.com/chat/completions",
        headers={
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": DEEPSEEK_MODEL,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        },
        timeout=180,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


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


def _call_bedrock(prompt, max_tokens):
    url = (
        f"https://bedrock-runtime.{AWS_REGION}.amazonaws.com"
        f"/model/{BEDROCK_MODEL_ID}/invoke"
    )
    resp = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {BEDROCK_API_KEY}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        json={
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=180,
    )
    resp.raise_for_status()
    return resp.json()["content"][0]["text"]
