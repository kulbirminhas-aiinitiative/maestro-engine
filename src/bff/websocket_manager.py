#!/usr/bin/env python3
"""
WebSocket Manager for Unified BFF
Manages WebSocket connections and broadcasts state updates
Single connection per session for both Chat and Preview
"""

import asyncio
import json
from datetime import datetime
from typing import Any, Dict, Optional, Set

from fastapi import WebSocket, WebSocketDisconnect


class WebSocketManager:
    """
    Centralized WebSocket connection management
    Handles broadcasting to both Chat and Preview panels via single connection
    """

    def __init__(self):
        # session_id -> WebSocket connection
        self.active_connections: Dict[str, WebSocket] = {}

        # Connection metadata
        self.connection_metadata: Dict[str, Dict[str, Any]] = {}

        # Heartbeat tracking
        self.last_ping: Dict[str, float] = {}

        print("✅ WebSocket Manager initialized")

    async def connect(self, session_id: str, websocket: WebSocket):
        """
        Accept and register WebSocket connection
        """
        await websocket.accept()

        self.active_connections[session_id] = websocket
        self.connection_metadata[session_id] = {
            "connected_at": datetime.now().isoformat(),
            "last_message": datetime.now().isoformat(),
            "message_count": 0,
        }
        self.last_ping[session_id] = asyncio.get_event_loop().time()

        print(f"✅ WebSocket connected: {session_id}")
        print(f"   Active connections: {len(self.active_connections)}")

    async def disconnect(self, session_id: str):
        """
        Remove WebSocket connection
        """
        if session_id in self.active_connections:
            del self.active_connections[session_id]

        if session_id in self.connection_metadata:
            del self.connection_metadata[session_id]

        if session_id in self.last_ping:
            del self.last_ping[session_id]

        print(f"✅ WebSocket disconnected: {session_id}")
        print(f"   Active connections: {len(self.active_connections)}")

    def is_connected(self, session_id: str) -> bool:
        """Check if session has active WebSocket"""
        return session_id in self.active_connections

    async def send_message(self, session_id: str, message: Dict[str, Any]) -> bool:
        """
        Send message to specific session
        Returns True if sent successfully, False otherwise

        Connection state check: Automatically validates WebSocket is connected
        before attempting to send message. Prevents "Need to call accept first" errors.
        """
        # Connection state check - ensures WebSocket is active before sending
        if session_id not in self.active_connections:
            return False

        try:
            websocket = self.active_connections[session_id]
            await websocket.send_json(message)

            # Update metadata
            if session_id in self.connection_metadata:
                self.connection_metadata[session_id]["last_message"] = datetime.now().isoformat()
                self.connection_metadata[session_id]["message_count"] += 1

            return True

        except Exception as e:
            print(f"❌ Error sending message to {session_id}: {e}")
            await self.disconnect(session_id)
            return False

    async def broadcast_state_change(self, session_id: str, state_update: Dict[str, Any]):
        """
        Broadcast unified state update to Chat + Preview
        Single message updates BOTH panels simultaneously
        """
        message = {"type": "state_change", "timestamp": datetime.now().isoformat(), **state_update}

        await self.send_message(session_id, message)

    async def send_chat_message(
        self, session_id: str, role: str, content: str, metadata: Optional[Dict[str, Any]] = None
    ):
        """Send chat message update"""
        message = {
            "type": "chat_message",
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {},
        }

        await self.send_message(session_id, message)

    async def send_preview_update(self, session_id: str, preview_data: Dict[str, Any]):
        """Send preview content update"""
        message = {
            "type": "preview_update",
            "preview": preview_data,
            "timestamp": datetime.now().isoformat(),
        }

        await self.send_message(session_id, message)

    async def send_generation_progress(
        self, session_id: str, stage: str, progress: int, message: str
    ):
        """
        Send generation progress update
        Updates both Chat (status) and Preview (loading state)
        """
        progress_msg = {
            "type": "generation_progress",
            "stage": stage,
            "progress": progress,
            "message": message,
            "timestamp": datetime.now().isoformat(),
        }

        await self.send_message(session_id, progress_msg)

    async def send_error(
        self, session_id: str, error_message: str, error_code: Optional[str] = None
    ):
        """Send error notification"""
        error_msg = {
            "type": "error",
            "error": error_message,
            "error_code": error_code,
            "timestamp": datetime.now().isoformat(),
        }

        await self.send_message(session_id, error_msg)

    async def send_workflow_state_change(self, session_id: str, old_state: str, new_state: str):
        """Send workflow state transition"""
        message = {
            "type": "workflow_state_change",
            "old_state": old_state,
            "new_state": new_state,
            "timestamp": datetime.now().isoformat(),
        }

        await self.send_message(session_id, message)

    async def send_file_generated(self, session_id: str, file_info: Dict[str, Any]):
        """Notify that a file was generated"""
        message = {
            "type": "file_generated",
            "file": file_info,
            "timestamp": datetime.now().isoformat(),
        }

        await self.send_message(session_id, message)

    # Heartbeat / Keep-Alive

    async def send_ping(self, session_id: str):
        """Send ping to check connection health"""
        message = {"type": "ping", "timestamp": datetime.now().isoformat()}

        success = await self.send_message(session_id, message)
        if success:
            self.last_ping[session_id] = asyncio.get_event_loop().time()

        return success

    async def handle_pong(self, session_id: str):
        """Handle pong response from client"""
        self.last_ping[session_id] = asyncio.get_event_loop().time()

    async def check_stale_connections(self, timeout: int = 300):
        """
        Check for stale connections (no ping in timeout seconds)
        Default: 5 minutes
        """
        current_time = asyncio.get_event_loop().time()
        stale_sessions = []

        for session_id, last_ping_time in self.last_ping.items():
            if current_time - last_ping_time > timeout:
                stale_sessions.append(session_id)

        for session_id in stale_sessions:
            print(f"⚠️  Disconnecting stale connection: {session_id}")
            await self.disconnect(session_id)

    # Connection Management

    async def broadcast_to_all(self, message: Dict[str, Any]):
        """Broadcast message to all active connections"""
        disconnected = []

        for session_id in list(self.active_connections.keys()):
            success = await self.send_message(session_id, message)
            if not success:
                disconnected.append(session_id)

        # Cleanup failed connections
        for session_id in disconnected:
            await self.disconnect(session_id)

    def get_active_sessions(self) -> list[str]:
        """Get list of active session IDs"""
        return list(self.active_connections.keys())

    def get_connection_count(self) -> int:
        """Get count of active connections"""
        return len(self.active_connections)

    def get_connection_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get connection metadata"""
        return self.connection_metadata.get(session_id)

    def get_all_connection_stats(self) -> Dict[str, Any]:
        """Get statistics for all connections"""
        return {
            "total_connections": self.get_connection_count(),
            "active_sessions": self.get_active_sessions(),
            "connections": {
                session_id: {**metadata, "is_connected": self.is_connected(session_id)}
                for session_id, metadata in self.connection_metadata.items()
            },
        }

    # Background Tasks

    async def start_heartbeat_monitor(self, interval: int = 30):
        """
        Start background task to monitor connection health
        Sends ping every interval seconds
        """
        while True:
            await asyncio.sleep(interval)

            # Send ping to all connections
            for session_id in list(self.active_connections.keys()):
                await self.send_ping(session_id)

            # Check for stale connections
            await self.check_stale_connections()

            print(f"💓 Heartbeat check: {self.get_connection_count()} active connections")


# Singleton instance
_websocket_manager: Optional[WebSocketManager] = None


def get_websocket_manager() -> WebSocketManager:
    """Get or create singleton WebSocket Manager"""
    global _websocket_manager
    if _websocket_manager is None:
        _websocket_manager = WebSocketManager()
    return _websocket_manager


# Example Usage
if __name__ == "__main__":
    import asyncio

    import uvicorn
    from fastapi import FastAPI, WebSocket

    app = FastAPI()
    ws_manager = WebSocketManager()

    @app.websocket("/ws/{session_id}")
    async def websocket_endpoint(websocket: WebSocket, session_id: str):
        await ws_manager.connect(session_id, websocket)

        try:
            # Send initial state
            await ws_manager.send_message(
                session_id, {"type": "connected", "message": f"Connected to session {session_id}"}
            )

            # Listen for messages
            while True:
                data = await websocket.receive_json()

                if data.get("type") == "pong":
                    await ws_manager.handle_pong(session_id)

                elif data.get("type") == "chat_message":
                    # Echo back for demo
                    await ws_manager.send_chat_message(
                        session_id, role="assistant", content=f"Received: {data.get('content')}"
                    )

        except WebSocketDisconnect:
            await ws_manager.disconnect(session_id)

    @app.get("/stats")
    async def get_stats():
        return ws_manager.get_all_connection_stats()

    @app.on_event("startup")
    async def startup():
        # Start heartbeat monitor
        asyncio.create_task(ws_manager.start_heartbeat_monitor())

    # Run test server: python3 websocket_manager.py
    # Test with: wscat -c ws://localhost:8001/ws/test_session
    uvicorn.run(app, host="0.0.0.0", port=8001)
