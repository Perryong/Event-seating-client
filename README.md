# Wedding Seat Arrangement System

A production-ready FastAPI backend for managing wedding seating arrangements with Excel integration, QR codes, and real-time guest check-in capabilities.

## Features

- **Admin Dashboard**: Create events, upload Excel seating arrangements, manage guests
- **Excel Integration**: Upload/download seating arrangements with validation
- **QR Code Generation**: Generate QR codes for guest portal access
- **Guest Portal**: Guests can look up their seating information and check in
- **Real-time Updates**: WebSocket-based live updates for check-ins and seating changes
- **Validation**: Comprehensive validation including table capacity limits (max 12 per table)
- **Multi-format Support**: Handle various dietary preferences and special requirements

## Tech Stack

- **Backend**: FastAPI + Uvicorn
- **Database**: SQLAlchemy + SQLite (easily configurable to PostgreSQL)
- **Excel Processing**: pandas + openpyxl
- **QR Codes**: qrcode + Pillow
- **Real-time**: WebSockets
- **File Handling**: python-multipart
- **Validation**: Pydantic

## Quick Start

### Environment Setup

Create a `.env` file with the following variables (Firebase optional):

```env
# Database (optional - defaults to SQLite)
DATABASE_URL=sqlite:///./wedding_seating.db

# Security
ADMIN_TOKEN=your_secure_admin_token_here

# Application
BASE_URL=http://localhost:8000

# Storage selection
USE_FIREBASE=false

# Firebase credentials (choose ONE method)
# 1) Path to service account JSON (recommended locally)
# FIREBASE_CREDENTIALS_FILE=C:\\path\\to\\service-account.json

# 2) Raw JSON string (escape newlines in private_key)
# FIREBASE_CREDENTIALS_JSON={"type":"service_account","project_id":"...","private_key_id":"...","private_key":"-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n","client_email":"...","client_id":"...","token_uri":"https://oauth2.googleapis.com/token"}

# 3) Base64-encoded JSON
# FIREBASE_CREDENTIALS_B64=

# CORS (optional - has sensible defaults)
ALLOW_ORIGINS=["http://localhost:3000", "http://localhost:5000"]
