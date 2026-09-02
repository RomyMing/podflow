import logging
from typing import Dict, List
from fastapi import WebSocket

logger = logging.getLogger(__name__)

class ConnectionManager:
    """
    Memory-backed WebSocket Connection Manager.
    Separates connections by task_id to allow localized broadcast.
    """
    def __init__(self):
        # Maps task_id string to a list of active websocket connections
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, task_id: str):
        # 注意: 此处不再调用 await websocket.accept()，需在调用者处提前 accept()
        if task_id not in self.active_connections:
            self.active_connections[task_id] = []
        self.active_connections[task_id].append(websocket)
        logger.info(f"WebSocket connected for task {task_id}. Total: {len(self.active_connections[task_id])}")

    def disconnect(self, websocket: WebSocket, task_id: str):
        if task_id in self.active_connections:
            if websocket in self.active_connections[task_id]:
                self.active_connections[task_id].remove(websocket)
            if not self.active_connections[task_id]:
                del self.active_connections[task_id]
        logger.info(f"WebSocket disconnected for task {task_id}.")

    async def broadcast_task_progress(self, task_id: str, stage: str, progress: int, status: str = "processing"):
        if task_id in self.active_connections:
            message = {
                "task_id": task_id,
                "stage": stage,
                "progress_percent": progress,
                "status": status
            }
            for connection in self.active_connections[task_id]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.error(f"Error sending ws message to task {task_id}: {str(e)}")

ws_manager = ConnectionManager()
