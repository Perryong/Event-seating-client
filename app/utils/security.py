"""
Security utilities and authentication
"""

from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Dict
import time
from collections import defaultdict

from app.core.config import settings

# Simple in-memory rate limiter
rate_limiter = defaultdict(list)

security = HTTPBearer()

def verify_admin_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify admin authentication token"""
    if credentials.credentials != settings.ADMIN_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin token"
        )
    return credentials.credentials

def rate_limit_check(client_ip: str, limit: int = None) -> bool:
    """Simple rate limiting by IP address"""
    if limit is None:
        limit = settings.RATE_LIMIT_PER_MINUTE
    
    current_time = time.time()
    minute_ago = current_time - 60
    
    # Clean old requests
    rate_limiter[client_ip] = [
        req_time for req_time in rate_limiter[client_ip] 
        if req_time > minute_ago
    ]
    
    # Check limit
    if len(rate_limiter[client_ip]) >= limit:
        return False
    
    # Add current request
    rate_limiter[client_ip].append(current_time)
    return True

def get_client_ip(request) -> str:
    """Extract client IP from request"""
    # Check for forwarded IP first (for reverse proxy setups)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    
    # Check for real IP header
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    
    # Fall back to direct client IP
    return request.client.host
