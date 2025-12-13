from __future__ import annotations
import json
import os
import urllib.request
from stockreco.config.settings import settings

# Minimal OpenAI Responses API call (no extra dependency).
# If OPENAI_API_KEY is missing, caller should bypass LLM stages.
def openai_json(prompt: str, schema: dict) -> dict:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY not set")

    body = {
        "model": settings.openai_model,
        "input": [
            {"role":"system","content":[{"type":"text","text":"You are a careful financial research assistant. Output must be valid JSON only."}]},
            {"role":"user","content":[{"type":"text","text":prompt}]},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "stockreco_schema",
                "schema": schema,
                "strict": True
            }
        }
    }
    req = urllib.request.Request(
        url="https://api.openai.com/v1/responses",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type":"application/json",
            "Authorization": f"Bearer {settings.openai_api_key}",
        },
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        out = json.loads(resp.read().decode("utf-8"))
    # Responses API returns output in structured arrays; extract text JSON.
    # We support common shapes.
    # Find first output_text
    txt = None
    for item in out.get("output", []):
        for c in item.get("content", []):
            if c.get("type") in ("output_text","text"):
                txt = c.get("text")
                break
        if txt:
            break
    if not txt:
        raise RuntimeError(f"Could not parse response: keys={list(out.keys())}")
    return json.loads(txt)
