"""
LLM provider abstraction — swap Anthropic ↔ Ollama via env var.
"""

import asyncio
import os

import httpx
from fastapi import HTTPException

PROVIDER              = os.getenv("LLM_PROVIDER", "anthropic")
ANTHROPIC_KEY         = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL       = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
ANTHROPIC_CHAT_MODEL  = os.getenv("ANTHROPIC_CHAT_MODEL", ANTHROPIC_MODEL)
ANTHROPIC_ANALYZE_MODEL = os.getenv("ANTHROPIC_ANALYZE_MODEL", ANTHROPIC_MODEL)
CHAT_MAX_TOKENS       = int(os.getenv("CHAT_MAX_TOKENS", "360"))
ANALYZE_MAX_TOKENS    = int(os.getenv("ANALYZE_MAX_TOKENS", "520"))
OLLAMA_URL            = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL          = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
OLLAMA_CHAT_MODEL     = os.getenv("OLLAMA_CHAT_MODEL", OLLAMA_MODEL)
OLLAMA_ANALYZE_MODEL  = os.getenv("OLLAMA_ANALYZE_MODEL", OLLAMA_MODEL)
OLLAMA_NUM_CTX        = int(os.getenv("OLLAMA_NUM_CTX", "2048"))
OLLAMA_CHAT_NUM_CTX   = int(os.getenv("OLLAMA_CHAT_NUM_CTX", str(OLLAMA_NUM_CTX)))
OLLAMA_ANALYZE_NUM_CTX = int(os.getenv("OLLAMA_ANALYZE_NUM_CTX", str(OLLAMA_NUM_CTX)))
OLLAMA_READ_TIMEOUT   = float(os.getenv("OLLAMA_READ_TIMEOUT", "420"))
OLLAMA_WRITE_TIMEOUT  = float(os.getenv("OLLAMA_WRITE_TIMEOUT", "60"))
OLLAMA_RETRY_NUM_CTX  = int(os.getenv("OLLAMA_RETRY_NUM_CTX", "1536"))
OLLAMA_RETRY_MAX_TOKENS = int(os.getenv("OLLAMA_RETRY_MAX_TOKENS", "256"))
OLLAMA_KEEP_ALIVE     = os.getenv("OLLAMA_KEEP_ALIVE", "15m").strip()
OLLAMA_NUM_THREAD     = int(os.getenv("OLLAMA_NUM_THREAD", "0"))
OLLAMA_NUM_BATCH      = int(os.getenv("OLLAMA_NUM_BATCH", "0"))

ACTIVE_CHAT_MODEL    = OLLAMA_CHAT_MODEL if PROVIDER == "ollama" else ANTHROPIC_CHAT_MODEL
ACTIVE_ANALYZE_MODEL = OLLAMA_ANALYZE_MODEL if PROVIDER == "ollama" else ANTHROPIC_ANALYZE_MODEL


async def chat(system: str, messages: list[dict], task: str = "chat") -> str:
    """Send a chat request to the configured LLM provider."""
    result = await chat_with_meta(system, messages, task=task)
    return result["content"]


async def chat_with_meta(system: str, messages: list[dict], task: str = "chat") -> dict:
    """Send a chat request and return response text with model metadata."""
    if PROVIDER == "ollama":
        return await _ollama(system, messages, task=task)
    return await _anthropic(system, messages, task=task)


async def warmup() -> None:
    if PROVIDER != "ollama":
        return

    timeout = httpx.Timeout(connect=10.0, read=60.0, write=30.0, pool=10.0)
    body = {
        "model": OLLAMA_CHAT_MODEL,
        "messages": [{"role": "user", "content": "warmup"}],
        "stream": False,
        "keep_alive": OLLAMA_KEEP_ALIVE or None,
        "options": {
            "temperature": 0.0,
            "num_ctx": max(512, min(OLLAMA_CHAT_NUM_CTX, 1024)),
            "num_predict": 1,
        },
    }
    if OLLAMA_NUM_THREAD > 0:
        body["options"]["num_thread"] = OLLAMA_NUM_THREAD
    if OLLAMA_NUM_BATCH > 0:
        body["options"]["num_batch"] = OLLAMA_NUM_BATCH

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            await client.post(f"{OLLAMA_URL}/api/chat", json=body)
    except Exception:
        return


# ── Providers ─────────────────────────────────────────────────────────────────

async def _anthropic(system: str, messages: list[dict], task: str = "chat") -> dict:
    model = ANTHROPIC_CHAT_MODEL if task == "chat" else ANTHROPIC_ANALYZE_MODEL
    max_tokens = CHAT_MAX_TOKENS if task == "chat" else ANALYZE_MAX_TOKENS
    headers = {
        "x-api-key": ANTHROPIC_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": messages,
    }
    async with httpx.AsyncClient(timeout=60) as client:
        for attempt in range(3):
            res = await client.post("https://api.anthropic.com/v1/messages", headers=headers, json=body)
            data = res.json()
            if data.get("error", {}).get("type") == "overloaded_error":
                await asyncio.sleep(3 * (attempt + 1))
                continue
            if res.status_code != 200:
                raise HTTPException(500, f"Anthropic error: {data.get('error', {}).get('message', str(data))}")
            return {"content": data["content"][0]["text"], "model": model, "provider": "anthropic"}
    raise HTTPException(503, "Anthropic overloaded — retry in 30s")


async def _ollama(system: str, messages: list[dict], task: str = "chat") -> dict:
    model = OLLAMA_CHAT_MODEL if task == "chat" else OLLAMA_ANALYZE_MODEL
    max_tokens = CHAT_MAX_TOKENS if task == "chat" else ANALYZE_MAX_TOKENS
    base_num_ctx = OLLAMA_CHAT_NUM_CTX if task == "chat" else OLLAMA_ANALYZE_NUM_CTX
    timeout = httpx.Timeout(connect=10.0, read=OLLAMA_READ_TIMEOUT, write=OLLAMA_WRITE_TIMEOUT, pool=10.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            return await _ollama_single_model(
                client=client,
                model=model,
                system=system,
                messages=messages,
                base_num_ctx=base_num_ctx,
                max_tokens=max_tokens,
            )
        except httpx.ConnectError:
            raise HTTPException(503, f"Ollama not running at {OLLAMA_URL}. Start with: ollama serve")
        except httpx.ReadTimeout:
            raise HTTPException(504, "Ollama timed out — model is slow, try a shorter prompt")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(500, f"Ollama error: {type(e).__name__}: {e}")


async def _ollama_single_model(
    client: httpx.AsyncClient,
    model: str,
    system: str,
    messages: list[dict],
    base_num_ctx: int,
    max_tokens: int,
) -> dict:
    last_error = None
    profiles = [(base_num_ctx, max_tokens)]
    retry_ctx = min(base_num_ctx, OLLAMA_RETRY_NUM_CTX)
    retry_tokens = min(max_tokens, OLLAMA_RETRY_MAX_TOKENS)
    if (retry_ctx, retry_tokens) != profiles[0]:
        profiles.append((retry_ctx, retry_tokens))

    for num_ctx, num_predict in profiles:
        options = {"temperature": 0.1, "num_ctx": num_ctx, "num_predict": num_predict}
        if OLLAMA_NUM_THREAD > 0:
            options["num_thread"] = OLLAMA_NUM_THREAD
        if OLLAMA_NUM_BATCH > 0:
            options["num_batch"] = OLLAMA_NUM_BATCH
        body = {
            "model": model,
            "messages": [{"role": "system", "content": system}] + messages,
            "stream": False,
            "keep_alive": OLLAMA_KEEP_ALIVE or None,
            "options": options,
        }
        try:
            request = client.post(f"{OLLAMA_URL}/api/chat", json=body)
            res = await request
            if res.status_code >= 400:
                last_error = f"{model}: {res.status_code} {res.text[:300]}"
                break
            data = res.json()
            if "error" in data:
                last_error = f"{model}: {data['error']}"
                break
            return {"content": data["message"]["content"], "model": model, "provider": "ollama"}
        except httpx.ReadTimeout:
            last_error = f"{model}: ReadTimeout"
            continue
        except Exception as e:
            last_error = f"{model}: {type(e).__name__}: {e}"
            break

    raise HTTPException(500, f"Ollama error: {last_error}")
