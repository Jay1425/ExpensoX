"""OTP (One-Time Password) verification model for secure authentication."""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import Column, DateTime, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship

from app.models import db


class OTPVerification(db.Model):
    """Model for storing OTP verification codes."""
    
    __tablename__ = 'otp_verifications'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    otp_code = Column(String(6), nullable=False)
    otp_type = Column(String(20), nullable=False)  # 'signup', 'login', 'password_reset'
    email = Column(String(255), nullable=False)
    is_used = Column(Boolean, default=False, nullable=False)
    attempts = Column(Integer, default=0, nullable=False)
    max_attempts = Column(Integer, default=5, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    verified_at = Column(DateTime)
    
    # Relationships
    user = relationship("User", backref="otp_verifications")
    
    def __init__(self, user_id: int, otp_type: str, email: str, validity_minutes: int = 10):
        """Initialize OTP verification record."""
        self.user_id = user_id
        self.otp_type = otp_type
        self.email = email
        self.otp_code = self.generate_otp()
        self.expires_at = datetime.utcnow() + timedelta(minutes=validity_minutes)
    
    @staticmethod
    def generate_otp() -> str:
        """Generate a secure 6-digit OTP code."""
        return str(secrets.randbelow(900000) + 100000)
    
    def is_valid(self) -> bool:
        """Check if OTP is still valid (not expired, not used, attempts not exceeded)."""
        return (
            not self.is_used and
            self.attempts < self.max_attempts and
            datetime.utcnow() <= self.expires_at
        )
    
    def verify_code(self, provided_code: str) -> bool:
        """Verify the provided OTP code."""
        self.attempts += 1
        
        if not self.is_valid():
            return False
        
        if self.otp_code == provided_code:
            self.is_used = True
            self.verified_at = datetime.utcnow()
            db.session.commit()
            return True
        
        db.session.commit()
        return False
    
    def is_expired(self) -> bool:
        """Check if OTP has expired."""
        return datetime.utcnow() > self.expires_at
    
    def time_remaining(self) -> Optional[int]:
        """Get remaining time in seconds, None if expired."""
        if self.is_expired():
            return None
        return int((self.expires_at - datetime.utcnow()).total_seconds())
    
    @classmethod
    def cleanup_expired(cls) -> int:
        """Remove expired OTP records. Returns count of deleted records."""
        expired = cls.query.filter(cls.expires_at < datetime.utcnow()).all()
        count = len(expired)
        for otp in expired:
            db.session.delete(otp)
        db.session.commit()
        return count
    
    @classmethod
    def get_active_otp(cls, user_id: int, otp_type: str) -> Optional['OTPVerification']:
        """Get active (valid) OTP for user and type."""
        return cls.query.filter_by(
            user_id=user_id,
            otp_type=otp_type,
            is_used=False
        ).filter(
            cls.expires_at > datetime.utcnow(),
            cls.attempts < cls.max_attempts
        ).first()
    
    @classmethod
    def create_otp(cls, user_id: int, otp_type: str, email: str, validity_minutes: int = 10) -> 'OTPVerification':
        """Create new OTP, invalidating any existing ones for same user/type."""
        # Invalidate existing OTPs for this user and type
        existing = cls.query.filter_by(
            user_id=user_id,
            otp_type=otp_type,
            is_used=False
        ).all()
        
        for otp in existing:
            otp.is_used = True
        
        # Create new OTP
        new_otp = cls(user_id=user_id, otp_type=otp_type, email=email, validity_minutes=validity_minutes)
        db.session.add(new_otp)
        db.session.commit()
        
        return new_otp
    
    def __repr__(self):
        return f'<OTPVerification {self.id}: {self.otp_type} for user {self.user_id}>'