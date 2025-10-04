"""Email service for sending OTP verification codes."""
from __future__ import annotations

import logging
from typing import Optional

from flask import current_app, render_template_string
from flask_mail import Mail, Message

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending emails including OTP verification."""
    
    def __init__(self, mail: Optional[Mail] = None):
        self.mail = mail
    
    def send_otp_email(self, email: str, otp_code: str, otp_type: str, user_name: str = None) -> bool:
        """Send OTP verification email."""
        try:
            subject = self._get_otp_subject(otp_type)
            html_body = self._get_otp_html_template(otp_code, otp_type, user_name)
            text_body = self._get_otp_text_template(otp_code, otp_type, user_name)
            
            return self._send_email(
                to_email=email,
                subject=subject,
                html_body=html_body,
                text_body=text_body
            )
        except Exception as e:
            logger.error(f"Failed to send OTP email to {email}: {str(e)}")
            return False
    
    def _send_email(self, to_email: str, subject: str, html_body: str, text_body: str = None) -> bool:
        """Send email using Flask-Mail."""
        try:
            if not self.mail:
                logger.error("Mail service not initialized")
                return False
            
            msg = Message(
                subject=subject,
                sender=current_app.config.get('MAIL_DEFAULT_SENDER'),
                recipients=[to_email]
            )
            
            if html_body:
                msg.html = html_body
            if text_body:
                msg.body = text_body
            
            self.mail.send(msg)
            logger.info(f"Email sent successfully to {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {str(e)}")
            return False
    
    def _get_otp_subject(self, otp_type: str) -> str:
        """Get email subject based on OTP type."""
        subjects = {
            'signup': 'ExpensoX - Verify Your Account',
            'login': 'ExpensoX - Login Verification Code',
            'password_reset': 'ExpensoX - Password Reset Code',
            'two_factor': 'ExpensoX - Two-Factor Authentication Code'
        }
        return subjects.get(otp_type, 'ExpensoX - Verification Code')
    
    def _get_otp_html_template(self, otp_code: str, otp_type: str, user_name: str = None) -> str:
        """Get HTML email template for OTP."""
        name_greeting = f"Hi {user_name}," if user_name else "Hello,"
        
        messages = {
            'signup': 'Welcome to ExpensoX! Please verify your email address to complete your registration.',
            'login': 'We received a login attempt for your ExpensoX account. Please use the verification code below.',
            'password_reset': 'You requested a password reset for your ExpensoX account. Use the code below to proceed.',
            'two_factor': 'Please use the following code to complete your login to ExpensoX.'
        }
        
        message = messages.get(otp_type, 'Please use the following verification code.')
        
        html_template = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>ExpensoX - Verification Code</title>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 0; background-color: #f8f9fa; }}
                .container {{ max-width: 600px; margin: 0 auto; background-color: white; }}
                .header {{ background-color: #0d6efd; color: white; padding: 30px; text-align: center; }}
                .content {{ padding: 40px 30px; }}
                .otp-box {{ background-color: #f8f9fa; border: 2px dashed #0d6efd; border-radius: 8px; padding: 30px; text-align: center; margin: 30px 0; }}
                .otp-code {{ font-size: 36px; font-weight: bold; color: #0d6efd; letter-spacing: 8px; font-family: 'Courier New', monospace; }}
                .footer {{ background-color: #f8f9fa; padding: 20px; text-align: center; color: #6c757d; font-size: 14px; }}
                .button {{ display: inline-block; padding: 12px 24px; background-color: #0d6efd; color: white; text-decoration: none; border-radius: 6px; margin: 20px 0; }}
                .warning {{ background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin: 20px 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🧾 ExpensoX</h1>
                    <p>Expense Management System</p>
                </div>
                
                <div class="content">
                    <h2>Verification Code</h2>
                    <p>{name_greeting}</p>
                    <p>{message}</p>
                    
                    <div class="otp-box">
                        <p style="margin: 0 0 10px 0; font-weight: bold; color: #495057;">Your verification code is:</p>
                        <div class="otp-code">{otp_code}</div>
                        <p style="margin: 10px 0 0 0; color: #6c757d; font-size: 14px;">This code will expire in 10 minutes</p>
                    </div>
                    
                    <div class="warning">
                        <strong>Security Notice:</strong> Never share this code with anyone. ExpensoX will never ask for your verification code via phone or email.
                    </div>
                    
                    <p>If you didn't request this verification code, please ignore this email or contact our support team.</p>
                </div>
                
                <div class="footer">
                    <p>&copy; 2025 ExpensoX. All rights reserved.</p>
                    <p>This is an automated message, please do not reply to this email.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return html_template
    
    def _get_otp_text_template(self, otp_code: str, otp_type: str, user_name: str = None) -> str:
        """Get plain text email template for OTP."""
        name_greeting = f"Hi {user_name}," if user_name else "Hello,"
        
        messages = {
            'signup': 'Welcome to ExpensoX! Please verify your email address to complete your registration.',
            'login': 'We received a login attempt for your ExpensoX account. Please use the verification code below.',
            'password_reset': 'You requested a password reset for your ExpensoX account. Use the code below to proceed.',
            'two_factor': 'Please use the following code to complete your login to ExpensoX.'
        }
        
        message = messages.get(otp_type, 'Please use the following verification code.')
        
        text_template = f"""
ExpensoX - Verification Code

{name_greeting}

{message}

Your verification code is: {otp_code}

This code will expire in 10 minutes.

SECURITY NOTICE: Never share this code with anyone. ExpensoX will never ask for your verification code via phone or email.

If you didn't request this verification code, please ignore this email or contact our support team.

--
ExpensoX Team
© 2025 ExpensoX. All rights reserved.
This is an automated message, please do not reply to this email.
        """
        
        return text_template.strip()


# Global email service instance
email_service = EmailService()


def init_email_service(mail: Mail) -> None:
    """Initialize the email service with Flask-Mail instance."""
    global email_service
    email_service.mail = mail


def send_otp_email(email: str, otp_code: str, otp_type: str, user_name: str = None) -> bool:
    """Convenience function to send OTP email."""
    return email_service.send_otp_email(email, otp_code, otp_type, user_name)