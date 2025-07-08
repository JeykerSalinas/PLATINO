from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import os
import httpx
from openai import AsyncOpenAI

router = APIRouter()

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/generate")


async def call_openai(prompt: str) -> str:
    """Send a prompt to OpenAI ChatGPT."""
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY not configured")

    client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    response = await client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content.strip()


async def call_ollama(prompt: str) -> str:
    """Send a prompt to a local Ollama instance."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(OLLAMA_URL, json={"model": "llama3", "prompt": prompt})
        resp.raise_for_status()
        data = resp.json()
        return data.get("response", "")


@router.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()

            try:
                response = await call_openai(data)
            except Exception:
                response = await call_ollama(data)

            await websocket.send_text(response)
    except WebSocketDisconnect:
        pass
