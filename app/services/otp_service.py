"""OTP service for handling verification logic."""
from __future__ import annotations

import logging
from typing import Optional, Tuple

from app.models import db, OTPVerification, User
from app.services.email_service import send_otp_email

logger = logging.getLogger(__name__)


class OTPService:
    """Service for managing OTP verification workflows."""
    
    @staticmethod
    def generate_and_send_otp(user_id: int, otp_type: str, email: str, user_name: str = None) -> Tuple[bool, str]:
        """
        Generate and send OTP to user.
        
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            # Create new OTP (this automatically invalidates existing ones)
            otp = OTPVerification.create_otp(
                user_id=user_id,
                otp_type=otp_type,
                email=email,
                validity_minutes=10
            )
            
            # Send email
            email_sent = send_otp_email(
                email=email,
                otp_code=otp.otp_code,
                otp_type=otp_type,
                user_name=user_name
            )
            
            if email_sent:
                logger.info(f"OTP generated and sent for user {user_id}, type: {otp_type}")
                return True, "Verification code sent successfully"
            else:
                logger.error(f"Failed to send OTP email for user {user_id}")
                return False, "Failed to send verification code. Please try again."
                
        except Exception as e:
            logger.error(f"Error generating OTP for user {user_id}: {str(e)}")
            return False, "An error occurred. Please try again."
    
    @staticmethod
    def verify_otp(user_id: int, otp_type: str, provided_code: str) -> Tuple[bool, str]:
        """
        Verify OTP code.
        
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            # Get active OTP
            otp = OTPVerification.get_active_otp(user_id, otp_type)
            
            if not otp:
                return False, "No valid verification code found. Please request a new one."
            
            if otp.is_expired():
                return False, "Verification code has expired. Please request a new one."
            
            if otp.attempts >= otp.max_attempts:
                return False, "Maximum verification attempts exceeded. Please request a new code."
            
            # Verify the code
            if otp.verify_code(provided_code):
                logger.info(f"OTP verified successfully for user {user_id}, type: {otp_type}")
                return True, "Verification successful"
            else:
                remaining_attempts = otp.max_attempts - otp.attempts
                if remaining_attempts > 0:
                    return False, f"Invalid verification code. {remaining_attempts} attempts remaining."
                else:
                    return False, "Invalid verification code. Maximum attempts exceeded."
                    
        except Exception as e:
            logger.error(f"Error verifying OTP for user {user_id}: {str(e)}")
            return False, "An error occurred during verification. Please try again."
    
    @staticmethod
    def resend_otp(user_id: int, otp_type: str) -> Tuple[bool, str]:
        """
        Resend OTP to user.
        
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            # Get user
            user = User.query.get(user_id)
            if not user:
                return False, "User not found"
            
            # Check if we can resend (not too frequent)
            existing_otp = OTPVerification.get_active_otp(user_id, otp_type)
            if existing_otp and existing_otp.time_remaining() and existing_otp.time_remaining() > 480:  # 8 minutes remaining
                return False, "Please wait before requesting a new code"
            
            # Generate and send new OTP
            return OTPService.generate_and_send_otp(
                user_id=user_id,
                otp_type=otp_type,
                email=user.email,
                user_name=user.first_name
            )
            
        except Exception as e:
            logger.error(f"Error resending OTP for user {user_id}: {str(e)}")
            return False, "An error occurred. Please try again."
    
    @staticmethod
    def get_otp_status(user_id: int, otp_type: str) -> dict:
        """Get OTP status information."""
        try:
            otp = OTPVerification.get_active_otp(user_id, otp_type)
            
            if not otp:
                return {
                    'exists': False,
                    'is_valid': False,
                    'time_remaining': None,
                    'attempts_remaining': 0
                }
            
            return {
                'exists': True,
                'is_valid': otp.is_valid(),
                'time_remaining': otp.time_remaining(),
                'attempts_remaining': max(0, otp.max_attempts - otp.attempts),
                'is_expired': otp.is_expired()
            }
            
        except Exception as e:
            logger.error(f"Error getting OTP status for user {user_id}: {str(e)}")
            return {
                'exists': False,
                'is_valid': False,
                'time_remaining': None,
                'attempts_remaining': 0
            }
    
    @staticmethod
    def cleanup_expired_otps() -> int:
        """Clean up expired OTP records."""
        try:
            count = OTPVerification.cleanup_expired()
            logger.info(f"Cleaned up {count} expired OTP records")
            return count
        except Exception as e:
            logger.error(f"Error cleaning up expired OTPs: {str(e)}")
            return 0


# Global OTP service instance
otp_service = OTPService()