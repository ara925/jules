from fastapi import WebSocket
from typing import Dict, List
import json

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, conversation_id: str):
        await websocket.accept()
        if conversation_id not in self.active_connections:
            self.active_connections[conversation_id] = []
        self.active_connections[conversation_id].append(websocket)

    def disconnect(self, websocket: WebSocket, conversation_id: str):
        if conversation_id in self.active_connections and websocket in self.active_connections[conversation_id]:
            self.active_connections[conversation_id].remove(websocket)
            if not self.active_connections[conversation_id]: # If list is empty
                del self.active_connections[conversation_id]

    async def broadcast_to_conversation(self, message_payload: dict, conversation_id: str):
        if conversation_id in self.active_connections:
            message_str = json.dumps(message_payload)
            # Create a list of connections to iterate over, in case of modification during iteration
            connections_to_send = list(self.active_connections[conversation_id])
            for connection in connections_to_send:
                try:
                    await connection.send_text(message_str)
                except Exception as e:
                    # Handle potential errors like connection already closed, etc.
                    print(f"Error sending to websocket in conv {conversation_id}: {e}")
                    # Optionally remove problematic connection here or let disconnect handle it
                    # self.active_connections[conversation_id].remove(connection)
                    pass

    async def send_personal_message(self, message_payload: dict, websocket: WebSocket):
        try:
            await websocket.send_text(json.dumps(message_payload))
        except Exception as e:
            print(f"Error sending personal message: {e}")

manager = ConnectionManager()
