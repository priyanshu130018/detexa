"""
app/core/realtime_broadcaster.py
─────────────────────────────────────────────────────────────────────────────
Real-Time Event Broadcaster supporting WebSockets and Server-Sent Events (SSE).
Pushes live transactions, fraud alerts, decision arbitrations, and status changes.
Handles client subscriptions, heartbeat watchdog, and stale connection pruning.
"""

import asyncio
from datetime import datetime, timezone
import json
import logging
from typing import Any, Dict, List, Optional, Set
import uuid

from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

logger = logging.getLogger("detexa.realtime")


class RealtimeBroadcaster:
    """
    Singleton broadcaster managing WebSocket connections and SSE queues.
    Thread-safe and async-safe dispatching.
    """

    _instance: Optional["RealtimeBroadcaster"] = None

    def __init__(self) -> None:
        self.active_websockets: Set[WebSocket] = set()
        self.sse_queues: Set[asyncio.Queue] = set()
        self._lock = asyncio.Lock()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._heartbeat_task: Optional[asyncio.Task] = None

    @classmethod
    def get_instance(cls) -> "RealtimeBroadcaster":
        if cls._instance is None:
            cls._instance = RealtimeBroadcaster()
        return cls._instance

    def set_event_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        if self._heartbeat_task is None or self._heartbeat_task.done():
            try:
                self._heartbeat_task = loop.create_task(self._heartbeat_loop())
            except Exception as e:
                logger.warning(f"Could not start heartbeat task: {e}")

    async def connect_websocket(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self.active_websockets.add(websocket)
        logger.info(f"WebSocket client connected. Total clients: {len(self.active_websockets)}")
        
        # Send initial welcome and state snapshot
        await self.send_personal_ws(
            websocket,
            {
                "event": "connection_established",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "status": "connected",
                "message": "Connected to Detexa Real-Time Stream",
            },
        )

    async def disconnect_websocket(self, websocket: WebSocket) -> None:
        async with self._lock:
            self.active_websockets.discard(websocket)
        logger.info(f"WebSocket client disconnected. Remaining: {len(self.active_websockets)}")

    async def connect_sse(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        async with self._lock:
            self.sse_queues.add(queue)
        logger.info(f"SSE client connected. Total SSE clients: {len(self.sse_queues)}")
        return queue

    async def disconnect_sse(self, queue: asyncio.Queue) -> None:
        async with self._lock:
            self.sse_queues.discard(queue)
        logger.info(f"SSE client disconnected. Remaining SSE: {len(self.sse_queues)}")

    async def send_personal_ws(self, websocket: WebSocket, message: Dict[str, Any]) -> None:
        try:
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.send_text(json.dumps(message))
        except Exception as e:
            logger.debug(f"Error sending personal message: {e}")
            await self.disconnect_websocket(websocket)

    async def broadcast(self, event_type: str, data: Dict[str, Any]) -> None:
        """
        Async broadcast to all active WebSocket and SSE clients.
        """
        message = {
            "event": event_type,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        msg_str = json.dumps(message)

        # 1. Dispatch to WebSockets
        dead_ws: List[WebSocket] = []
        async with self._lock:
            ws_targets = list(self.active_websockets)
            sse_targets = list(self.sse_queues)

        for ws in ws_targets:
            try:
                if ws.client_state == WebSocketState.CONNECTED:
                    await ws.send_text(msg_str)
                else:
                    dead_ws.append(ws)
            except Exception:
                dead_ws.append(ws)

        # Clean up dead sockets
        if dead_ws:
            async with self._lock:
                for ws in dead_ws:
                    self.active_websockets.discard(ws)

        # 2. Dispatch to SSE queues
        dead_queues: List[asyncio.Queue] = []
        for q in sse_targets:
            try:
                if q.full():
                    try:
                        q.get_nowait()  # Drop oldest event if queue is backlogged
                    except asyncio.QueueEmpty:
                        pass
                q.put_nowait(msg_str)
            except Exception:
                dead_queues.append(q)

        if dead_queues:
            async with self._lock:
                for q in dead_queues:
                    self.sse_queues.discard(q)

    def publish_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """
        Thread-safe synchronous publisher that dispatches to the running asyncio loop.
        Can be called from background workers, Kafka consumers, or synchronous API routes.
        """
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self.broadcast(event_type, data), self._loop)
        else:
            # Fallback: create a one-off task if within async context
            try:
                current_loop = asyncio.get_running_loop()
                current_loop.create_task(self.broadcast(event_type, data))
            except RuntimeError:
                pass

    # Convenience Broadcasters
    def push_new_transaction(self, transaction_data: Dict[str, Any]) -> None:
        """Push new transaction stream event."""
        self.publish_event("new_transaction", transaction_data)

    def push_fraud_alert(self, alert_data: Dict[str, Any]) -> None:
        """Push security alert event."""
        self.publish_event("fraud_alert", alert_data)

    def push_decision(self, decision_data: Dict[str, Any]) -> None:
        """Push automated decision arbitration or analyst override."""
        self.publish_event("decision_event", decision_data)

    def push_status_change(self, status_data: Dict[str, Any]) -> None:
        """Push pipeline or system status change."""
        self.publish_event("status_change", status_data)

    async def _heartbeat_loop(self) -> None:
        """Watchdog sending heartbeat ping every 15 seconds to prevent stale connections."""
        while True:
            try:
                await asyncio.sleep(15)
                if self.active_websockets or self.sse_queues:
                    await self.broadcast(
                        "heartbeat",
                        {
                            "status": "healthy",
                            "active_ws_clients": len(self.active_websockets),
                            "active_sse_clients": len(self.sse_queues),
                        },
                    )
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"Heartbeat loop tick exception: {e}")


def get_realtime_broadcaster() -> RealtimeBroadcaster:
    return RealtimeBroadcaster.get_instance()
