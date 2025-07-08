from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import os
import httpx
import json
from openai import AsyncOpenAI

router = APIRouter()

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/generate")

async def stream_openai(prompt: str):
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY not configured")
    client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    stream = await client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        stream=True,
    )
    async for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield json.dumps({"response": delta}) + "\n"

async def stream_ollama(prompt: str):
    async with httpx.AsyncClient() as client:
        async with client.stream(
            "POST",
            OLLAMA_URL,
            json={"model": "llama3", "prompt": prompt, "stream": True},
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if line.strip():
                    yield line + "\n"

@router.post("/chat/stream")
async def chat_stream(prompt: str):
    async def generator():
        try:
            async for chunk in stream_openai(prompt):
                yield chunk
        except Exception:
            async for chunk in stream_ollama(prompt):
                yield chunk
    return StreamingResponse(generator(), media_type="application/json")
