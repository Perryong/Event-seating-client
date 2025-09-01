"""
QR code generation service
"""

import io
from typing import Union
import qrcode
from PIL import Image

from app.core.config import settings

class QRService:
    """Service for generating QR codes"""
    
    @staticmethod
    def generate_event_qr(public_code: str, format: str = 'PNG') -> bytes:
        """Generate QR code for event guest portal"""
        url = f"{settings.BASE_URL}/guest/portal?event={public_code}"
        
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(url)
        qr.make(fit=True)
        
        # Create QR code image
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to bytes
        buffer = io.BytesIO()
        img.save(buffer, format=format)
        
        return buffer.getvalue()
    
    @staticmethod
    def save_qr_image(public_code: str, file_path: str = None) -> str:
        """Save QR code image to file"""
        if not file_path:
            file_path = f"static/qr_{public_code}.png"
        
        qr_bytes = QRService.generate_event_qr(public_code)
        
        with open(file_path, 'wb') as f:
            f.write(qr_bytes)
        
        return file_path
    
    @staticmethod
    def get_qr_url(public_code: str) -> str:
        """Get the URL that the QR code will redirect to"""
        return f"{settings.BASE_URL}/guest/portal?event={public_code}"
