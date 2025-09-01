"""
Firebase initialization and helpers
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any
import base64
import os

import firebase_admin
from firebase_admin import credentials, firestore

from app.core.config import settings


@lru_cache(maxsize=1)
def get_firestore_client():
    """Initialize and return a cached Firestore client if Firebase is enabled.

    Expects credentials via one of: FIREBASE_CREDENTIALS_JSON, FIREBASE_CREDENTIALS_B64, FIREBASE_CREDENTIALS_FILE.
    """
    if not settings.USE_FIREBASE:
        return None

    if not firebase_admin._apps:
        info: dict[str, Any] | None = None
        if settings.FIREBASE_CREDENTIALS_JSON:
            info = json.loads(settings.FIREBASE_CREDENTIALS_JSON)
        elif getattr(settings, "FIREBASE_CREDENTIALS_B64", None):
            decoded = base64.b64decode(settings.FIREBASE_CREDENTIALS_B64).decode("utf-8")
            info = json.loads(decoded)
        elif getattr(settings, "FIREBASE_CREDENTIALS_FILE", None) and os.path.exists(settings.FIREBASE_CREDENTIALS_FILE):
            with open(settings.FIREBASE_CREDENTIALS_FILE, "r", encoding="utf-8") as f:
                info = json.load(f)

        if not info:
            raise RuntimeError("Firebase credentials not provided. Set FIREBASE_CREDENTIALS_FILE, FIREBASE_CREDENTIALS_JSON, or FIREBASE_CREDENTIALS_B64")

        cred = credentials.Certificate(info)
        firebase_admin.initialize_app(cred)

    return firestore.client()


