"""
app/api/v1/endpoints/realtime.py
─────────────────────────────────────────────────────────────────────────────
Real-time WebSocket and Server-Sent Events (SSE) endpoints.
Pushes new transactions, fraud alerts, decision arbitrations, and status changes.
"""

import asyncio
from datetime import datetime, timezone
import json
from typing import Any, Dict, Optional
import uuid

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.core.realtime_broadcaster import get_realtime_broadcaster, RealtimeBroadcaster
from app.core.security import decode_token

router = APIRouter(tags=["Real-Time Event Stream"])


@router.websocket("/ws/events")
async def websocket_events_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None, description="Optional JWT authentication token"),
):
    """
    Bi-directional real-time WebSocket connection.
    Pushes:
      - new_transaction
      - fraud_alert
      - decision_event
      - status_change
      - heartbeat
    """
    # ── WebSocket Authentication ───────────────────────────────────────────────
    auth_token = token
    if not auth_token:
        auth_header = websocket.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            auth_token = auth_header.split(" ", 1)[1]
        elif not auth_token:
            protocols = websocket.headers.get("sec-websocket-protocol", "").split(",")
            for p in protocols:
                p = p.strip()
                if p.lower().startswith("bearer."):
                    auth_token = p.split(".", 1)[1]
                    break

    if auth_token:
        payload = decode_token(auth_token)
        if not payload:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid authentication token")
            return

    broadcaster = get_realtime_broadcaster()
    # Set event loop reference on connect
    try:
        broadcaster.set_event_loop(asyncio.get_running_loop())
    except RuntimeError:
        pass

    await broadcaster.connect_websocket(websocket)

    try:
        while True:
            # Listen for client ping, subscriptions, or in-band auth
            raw_text = await websocket.receive_text()
            try:
                msg = json.loads(raw_text)
                action = msg.get("action")
                if action == "ping":
                    await broadcaster.send_personal_ws(
                        websocket,
                        {
                            "event": "pong",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        },
                    )
                elif action == "subscribe":
                    channel = msg.get("channel", "all")
                    await broadcaster.send_personal_ws(
                        websocket,
                        {
                            "event": "subscribed",
                            "channel": channel,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        },
                    )
                elif action in ("auth", "authenticate"):
                    msg_token = msg.get("token") or msg.get("access_token")
                    if msg_token and decode_token(msg_token):
                        await broadcaster.send_personal_ws(
                            websocket,
                            {
                                "event": "authenticated",
                                "status": "success",
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                            },
                        )
                    else:
                        await broadcaster.send_personal_ws(
                            websocket,
                            {
                                "event": "auth_error",
                                "status": "failed",
                                "message": "Invalid authentication token",
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                            },
                        )
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        await broadcaster.disconnect_websocket(websocket)
    except Exception:
        await broadcaster.disconnect_websocket(websocket)


@router.get(
    "/events/stream",
    summary="Server-Sent Events (SSE) Stream",
    description="HTTP Server-Sent Events stream delivering real-time transactions, alerts, and decisions.",
    response_class=StreamingResponse,
)
async def sse_events_endpoint():
    """
    Server-Sent Events endpoint (fallback if WebSocket is blocked by proxy).
    """
    broadcaster = get_realtime_broadcaster()
    try:
        broadcaster.set_event_loop(asyncio.get_running_loop())
    except RuntimeError:
        pass

    queue = await broadcaster.connect_sse()

    async def event_generator():
        try:
            # Send initial connected event
            init_msg = json.dumps({
                "event": "connection_established",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "status": "connected",
            })
            yield f"data: {init_msg}\n\n"

            while True:
                data = await queue.get()
                yield f"data: {data}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            await broadcaster.disconnect_sse(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


class SimulateEventRequest(BaseModel):
    event_type: str = Field("new_transaction", description="Event type: new_transaction, fraud_alert, decision_event, status_change")
    payload: Optional[Dict[str, Any]] = None


@router.post(
    "/realtime/simulate",
    summary="Simulate Real-Time Push Event",
    description="Emits a simulated real-time event to all connected WebSocket and SSE clients.",
    status_code=status.HTTP_200_OK,
)
async def simulate_realtime_event(body: SimulateEventRequest):
    broadcaster = get_realtime_broadcaster()
    
    event_data = body.payload or {}
    if body.event_type == "new_transaction":
        if "transaction_ref" not in event_data:
            ref_num = uuid.uuid4().hex[:8].upper()
            event_data = {
                "id": str(uuid.uuid4()),
                "transaction_ref": f"TXN-SIM-{ref_num}",
                "amount": round(50.0 + (uuid.uuid4().int % 95000) / 100, 2),
                "merchant": "Apex Global Online",
                "category": "Retail",
                "country": "US",
                "currency": "USD",
                "fraud_score": round((uuid.uuid4().int % 1000) / 1000, 4),
                "risk_level": "High" if (uuid.uuid4().int % 10) > 7 else "Low",
                "decision": "BLOCK" if (uuid.uuid4().int % 10) > 7 else "ALLOW",
                "is_fraud": (uuid.uuid4().int % 10) > 7,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        broadcaster.push_new_transaction(event_data)
    elif body.event_type == "fraud_alert":
        if "description" not in event_data:
            event_data = {
                "id": str(uuid.uuid4()),
                "alert_type": "credit_fraud",
                "risk_level": "High",
                "score": 0.942,
                "description": "Suspicious burst velocity and proxy collision detected",
                "status": "open",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        broadcaster.push_fraud_alert(event_data)
    elif body.event_type == "decision_event":
        if "decision" not in event_data:
            event_data = {
                "decision_id": str(uuid.uuid4()),
                "decision": "BLOCK",
                "rule_name": "RULE_VELOCITY",
                "fraud_score": 0.915,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        broadcaster.push_decision(event_data)
    elif body.event_type == "status_change":
        if "status" not in event_data:
            event_data = {
                "service": "Flink Stream Engine",
                "status": "OPTIMAL",
                "processed_events_per_sec": 4200,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        broadcaster.push_status_change(event_data)
    else:
        broadcaster.publish_event(body.event_type, event_data)

    return {
        "status": "dispatched",
        "event_type": body.event_type,
        "active_ws_clients": len(broadcaster.active_websockets),
        "active_sse_clients": len(broadcaster.sse_queues),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
