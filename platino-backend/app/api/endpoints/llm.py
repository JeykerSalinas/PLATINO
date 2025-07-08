from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import os
import httpx
import json
from openai import AsyncOpenAI
from pydantic import BaseModel
from app.core.config import settings  
router = APIRouter()

OPENAI_API_KEY = settings.openai_api_key
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/generate")

client = AsyncOpenAI(api_key=settings.openai_api_key)

# 👇 Ahora el usuario puede enviar también el proveedor
class PromptRequest(BaseModel):
    prompt: str
    provider: str  # "openai" o "ollama"

async def stream_openai(prompt: str):
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY not configured")
    print('OpenAI connected')

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
    print('Ollama connected')
    timeout = httpx.Timeout(60.0, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
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
async def chat_stream(data: PromptRequest):
    prompt = data.prompt
    provider = data.provider.lower()

    # Seleccionamos la fuente según lo que elija el usuario
    if provider == "openai":
        generator = stream_openai(prompt)
    elif provider == "ollama":
        generator = stream_ollama(prompt)
    else:
        raise HTTPException(status_code=400, detail="Invalid provider")

    return StreamingResponse(generator, media_type="application/json")
