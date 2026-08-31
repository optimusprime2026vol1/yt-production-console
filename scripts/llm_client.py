#!/usr/bin/env python3
"""
Shared Claude client - routes to AWS Bedrock if BEDROCK_API_KEY is set,
otherwise falls back to the direct Anthropic API via ANTHROPIC_API_KEY.

Bedrock auth here uses AWS's bearer-token "API key" feature (not full
SigV4/IAM access-key signing) - it only works with that specific Bedrock
API key type, generated from the Bedrock console's "API keys" page.

Required for Bedrock: BEDROCK_API_KEY, BEDROCK_MODEL_ID (the exact Bedrock
model/inference-profile id for Claude in your account and region - copy it
from the AWS Bedrock console; it is NOT the same string as the direct
Anthropic API's model name, and this project doesn't guess it for you).
Optional: AWS_REGION (default us-east-1).

Required for direct API: ANTHROPIC_API_KEY.
"""
import os

import requests

BEDROCK_API_KEY = os.environ.get("BEDROCK_API_KEY")
BEDROCK_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")


def has_llm_credentials():
    return bool(BEDROCK_API_KEY and BEDROCK_MODEL_ID) or bool(ANTHROPIC_API_KEY)


def missing_credentials_message():
    return (
        "No LLM credentials configured. Set either "
        "(BEDROCK_API_KEY + BEDROCK_MODEL_ID) for Bedrock, "
        "or ANTHROPIC_API_KEY for the direct Anthropic API."
    )


def call_claude(prompt, max_tokens=2000):
    if BEDROCK_API_KEY and BEDROCK_MODEL_ID:
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
