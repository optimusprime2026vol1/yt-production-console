#!/usr/bin/env python3
"""
Shared Claude client - routes to standard AWS Bedrock (InvokeModel API) if
BEDROCK_API_KEY is set, otherwise falls back to the direct Anthropic API
via ANTHROPIC_API_KEY.

This uses Bedrock's InvokeModel endpoint directly (not the Mantle gateway):
POST https://bedrock-runtime.{region}.amazonaws.com/model/{model_id}/invoke
with the native Anthropic Messages body shape plus "anthropic_version".

Auth is AWS's bearer-token Bedrock API key (from the Bedrock console's
"API keys" page) - not full SigV4/IAM access-key signing.

BEDROCK_MODEL_ID defaults to "anthropic.claude-sonnet-4-6" (confirmed
correct for the InvokeModel API from AWS's own model-card docs). Override
it if your account/region needs a different id or inference-profile id
(e.g. a "us." prefix). Optional: AWS_REGION (default us-east-1).

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
        "BEDROCK_API_KEY (standard AWS Bedrock) "
        "or ANTHROPIC_API_KEY (direct Anthropic API)."
    )


def call_claude(prompt, max_tokens=2000):
    if BEDROCK_API_KEY:
        return _call_bedrock(prompt, max_tokens)
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
