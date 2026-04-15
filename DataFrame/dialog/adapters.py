from __future__ import annotations

import asyncio
import json
import logging
import urllib.error
import urllib.request

import aiohttp
from qdrant_client.http import models as qm

from ..rag.config import Settings
from ..rag.embeddings import embed_texts
from ..rag.qdrant_store import search

logger = logging.getLogger(__name__)


def ollama_generate_legacy(settings: Settings, prompt: str) -> str:
    url = settings.ollama_url.rstrip("/") + "/api/generate"
    payload: dict = {"model": settings.llm_model, "prompt": prompt, "stream": False}
    if settings.ollama_think:
        payload["think"] = True
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return (data.get("response") or "").strip()


async def ollama_generate_legacy_async(settings: Settings, prompt: str) -> str:
    url = settings.ollama_url.rstrip("/") + "/api/generate"
    payload: dict = {"model": settings.llm_model, "prompt": prompt, "stream": False}
    if settings.ollama_think:
        payload["think"] = True
    timeout = aiohttp.ClientTimeout(total=60)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(url, json=payload) as resp:
            resp.raise_for_status()
            data = await resp.json(content_type=None)
    return (data.get("response") or "").strip()


def ollama_chat(settings: Settings, system: str, user: str) -> str:
    url = settings.ollama_url.rstrip("/") + "/api/chat"
    payload: dict = {
        "model": settings.llm_model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "stream": False,
        "options": {"num_predict": 500},
    }
    if settings.ollama_think:
        payload["think"] = True
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        msg = data.get("message") or {}
        text = (msg.get("content") or "").strip()
        if text:
            return text
    except urllib.error.HTTPError as e:
        logger.debug("Ollama /api/chat HTTP %s", e.code)
    except urllib.error.URLError as e:
        return f"[LLM недоступен: {e}]"

    combined = f"{system}\n\nПользователь:\n{user}"
    try:
        return ollama_generate_legacy(settings, combined)
    except urllib.error.URLError as e:
        return f"[LLM недоступен: {e}. Ниже — найденные фрагменты.]"


async def ollama_chat_async(settings: Settings, system: str, user: str) -> str:
    url = settings.ollama_url.rstrip("/") + "/api/chat"
    payload: dict = {
        "model": settings.llm_model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "stream": False,
        "options": {"num_predict": 500},
    }
    if settings.ollama_think:
        payload["think"] = True

    timeout = aiohttp.ClientTimeout(total=90)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, json=payload) as resp:
                resp.raise_for_status()
                data = await resp.json(content_type=None)
        msg = data.get("message") or {}
        text = (msg.get("content") or "").strip()
        if text:
            return text
    except aiohttp.ClientResponseError as e:
        logger.debug("Ollama /api/chat HTTP %s", e.status)
    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        return f"[LLM недоступен: {e}]"

    combined = f"{system}\n\nПользователь:\n{user}"
    try:
        return await ollama_generate_legacy_async(settings, combined)
    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        return f"[LLM недоступен: {e}. Ниже — найденные фрагменты.]"


def retrieve_hits(client, settings: Settings, question: str, *, query_filter: qm.Filter | None = None):
    qvec = embed_texts([question], settings, is_query=True)[0]
    return search(client, settings, qvec, limit=settings.retrieve_top_k, query_filter=query_filter)
