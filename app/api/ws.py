"""
WebSocket manager for real-time updates
"""

import json
import logging
from typing import Dict, List
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models import Event

logger = logging.getLogger(__name__)

class WebSocketManager:
    """Manages WebSocket connections for real-time updates"""
    
    def __init__(self):
        # event_code -> list of websockets
        self.active_connections: Dict[str, List[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, event_code: str):
        """Accept WebSocket connection and add to event room"""
        await websocket.accept()
        
        if event_code not in self.active_connections:
            self.active_connections[event_code] = []
        
        self.active_connections[event_code].append(websocket)
        logger.info(f"WebSocket connected to event {event_code}. Total connections: {len(self.active_connections[event_code])}")
    
    def disconnect(self, websocket: WebSocket, event_code: str):
        """Remove WebSocket connection from event room"""
        if event_code in self.active_connections:
            try:
                self.active_connections[event_code].remove(websocket)
                logger.info(f"WebSocket disconnected from event {event_code}. Remaining connections: {len(self.active_connections[event_code])}")
                
                # Clean up empty rooms
                if not self.active_connections[event_code]:
                    del self.active_connections[event_code]
            except ValueError:
                # WebSocket was not in the list
                pass
    
    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """Send message to specific WebSocket"""
        try:
            await websocket.send_text(json.dumps(message))
        except Exception as e:
            logger.error(f"Error sending personal message: {e}")
    
    async def broadcast_to_event(self, event_code: str, message: dict):
        """Broadcast message to all WebSockets connected to an event"""
        if event_code not in self.active_connections:
            logger.warning(f"No active connections for event {event_code}")
            return
        
        # Create list copy to avoid modification during iteration
        connections = self.active_connections[event_code].copy()
        
        disconnected = []
        for websocket in connections:
            try:
                await websocket.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Error broadcasting to websocket: {e}")
                disconnected.append(websocket)
        
        # Clean up disconnected websockets
        for websocket in disconnected:
            self.disconnect(websocket, event_code)
    
    def get_connection_count(self, event_code: str) -> int:
        """Get number of active connections for an event"""
        return len(self.active_connections.get(event_code, []))
    
    def get_all_connection_counts(self) -> Dict[str, int]:
        """Get connection counts for all events"""
        return {
            event_code: len(connections)
            for event_code, connections in self.active_connections.items()
        }

# Global WebSocket manager instance
websocket_manager = WebSocketManager()

# Router for WebSocket endpoints
router = APIRouter()

@router.websocket("/events/{event_code}")
async def websocket_endpoint(
    websocket: WebSocket,
    event_code: str,
    db: Session = Depends(get_db)
):
    """WebSocket endpoint for real-time event updates"""
    
    # Verify event exists
    event = db.query(Event).filter(Event.public_code == event_code).first()
    if not event:
        await websocket.close(code=4004, reason="Event not found")
        return
    
    # Connect to WebSocket
    await websocket_manager.connect(websocket, event_code)
    
    try:
        # Send welcome message
        welcome_message = {
            "type": "connection",
            "message": f"Connected to event: {event.name}",
            "event_code": event_code,
            "connection_count": websocket_manager.get_connection_count(event_code)
        }
        await websocket_manager.send_personal_message(welcome_message, websocket)
        
        # Keep connection alive and handle incoming messages
        while True:
            try:
                # Wait for messages from client (heartbeat, etc.)
                data = await websocket.receive_text()
                
                # Parse and handle client messages if needed
                try:
                    client_message = json.loads(data)
                    
                    # Handle heartbeat/ping
                    if client_message.get("type") == "ping":
                        pong_message = {
                            "type": "pong",
                            "timestamp": client_message.get("timestamp")
                        }
                        await websocket_manager.send_personal_message(pong_message, websocket)
                
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON received from WebSocket: {data}")
                    
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Error in WebSocket loop: {e}")
                break
    
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        websocket_manager.disconnect(websocket, event_code)

@router.get("/stats")
async def websocket_stats():
    """Get WebSocket connection statistics (for debugging)"""
    return {
        "total_events_with_connections": len(websocket_manager.active_connections),
        "connection_counts": websocket_manager.get_all_connection_counts(),
        "total_connections": sum(websocket_manager.get_all_connection_counts().values())
    }
