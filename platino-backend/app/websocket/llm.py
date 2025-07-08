from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from ..core.rag_engine import query

router = APIRouter()


@router.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            response = query(data)
            await websocket.send_text(str(response))
    except WebSocketDisconnect:
        pass
