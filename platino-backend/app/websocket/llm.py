from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()

@router.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            # In a real app, call your LLM here
            response = f"Echo: {data}"
            await websocket.send_text(response)
    except WebSocketDisconnect:
        pass
