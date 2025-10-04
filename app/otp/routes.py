"""OTP verification routes."""
from __future__ import annotations

import logging

from flask import Blueprint, request, jsonify, render_template, flash, redirect, url_for, session
from flask_login import current_user, login_required

from app.models import db, User
from app.services.otp_service import otp_service

logger = logging.getLogger(__name__)

# Create OTP blueprint
otp_bp = Blueprint('otp', __name__, url_prefix='/otp')


@otp_bp.route('/verify/<otp_type>')
def verify_page(otp_type: str):
    """Display OTP verification page."""
    # Validate OTP type
    valid_types = ['signup', 'login', 'password_reset', 'two_factor']
    if otp_type not in valid_types:
        flash('Invalid verification type', 'error')
        return redirect(url_for('auth.login'))
    
    # Check if user is in session (for signup/password reset) or logged in
    user_id = session.get('pending_user_id') or (current_user.id if current_user.is_authenticated else None)
    
    if not user_id:
        flash('Session expired. Please start the process again.', 'error')
        return redirect(url_for('auth.login'))
    
    # Get user for display
    user = User.query.get(user_id)
    if not user:
        flash('User not found', 'error')
        return redirect(url_for('auth.login'))
    
    # Get OTP status
    otp_status = otp_service.get_otp_status(user_id, otp_type)
    
    return render_template('otp/verify.html', 
                         otp_type=otp_type, 
                         user=user,
                         otp_status=otp_status)


@otp_bp.route('/send', methods=['POST'])
def send_otp():
    """Send OTP code to user."""
    try:
        data = request.get_json()
        otp_type = data.get('otp_type')
        user_id = data.get('user_id')
        
        # Validate input
        if not otp_type or not user_id:
            return jsonify({
                'success': False,
                'message': 'Missing required parameters'
            }), 400
        
        # Validate OTP type
        valid_types = ['signup', 'login', 'password_reset', 'two_factor']
        if otp_type not in valid_types:
            return jsonify({
                'success': False,
                'message': 'Invalid OTP type'
            }), 400
        
        # Get user
        user = User.query.get(user_id)
        if not user:
            return jsonify({
                'success': False,
                'message': 'User not found'
            }), 404
        
        # Check permissions (user can only request OTP for themselves unless admin)
        if not current_user.is_authenticated or (current_user.id != user_id and current_user.role != 'admin'):
            # Allow for signup/password reset if user_id is in session
            if otp_type in ['signup', 'password_reset'] and session.get('pending_user_id') == user_id:
                pass  # Allow
            else:
                return jsonify({
                    'success': False,
                    'message': 'Unauthorized'
                }), 403
        
        # Generate and send OTP
        success, message = otp_service.generate_and_send_otp(
            user_id=user_id,
            otp_type=otp_type,
            email=user.email,
            user_name=user.first_name
        )
        
        return jsonify({
            'success': success,
            'message': message
        })
        
    except Exception as e:
        logger.error(f"Error in send_otp: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'An error occurred. Please try again.'
        }), 500


@otp_bp.route('/verify', methods=['POST'])
def verify_otp():
    """Verify OTP code."""
    try:
        data = request.get_json()
        otp_type = data.get('otp_type')
        otp_code = data.get('otp_code')
        user_id = data.get('user_id')
        
        # Validate input
        if not all([otp_type, otp_code, user_id]):
            return jsonify({
                'success': False,
                'message': 'Missing required parameters'
            }), 400
        
        # Validate OTP code format (6 digits)
        if not otp_code.isdigit() or len(otp_code) != 6:
            return jsonify({
                'success': False,
                'message': 'Invalid verification code format'
            }), 400
        
        # Check permissions
        if not current_user.is_authenticated or (current_user.id != user_id and current_user.role != 'admin'):
            # Allow for signup/password reset if user_id is in session
            if otp_type in ['signup', 'password_reset'] and session.get('pending_user_id') == user_id:
                pass  # Allow
            else:
                return jsonify({
                    'success': False,
                    'message': 'Unauthorized'
                }), 403
        
        # Verify OTP
        success, message = otp_service.verify_otp(user_id, otp_type, otp_code)
        
        if success:
            # Handle post-verification actions based on OTP type
            if otp_type == 'signup':
                # Mark user as verified
                user = User.query.get(user_id)
                if user:
                    user.is_email_verified = True
                    db.session.commit()
                    session.pop('pending_user_id', None)
            elif otp_type == 'password_reset':
                # Set flag for password reset
                session['password_reset_verified'] = True
                session['password_reset_user_id'] = user_id
        
        return jsonify({
            'success': success,
            'message': message
        })
        
    except Exception as e:
        logger.error(f"Error in verify_otp: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'An error occurred during verification. Please try again.'
        }), 500


@otp_bp.route('/resend', methods=['POST'])
def resend_otp():
    """Resend OTP code."""
    try:
        data = request.get_json()
        otp_type = data.get('otp_type')
        user_id = data.get('user_id')
        
        # Validate input
        if not otp_type or not user_id:
            return jsonify({
                'success': False,
                'message': 'Missing required parameters'
            }), 400
        
        # Check permissions
        if not current_user.is_authenticated or (current_user.id != user_id and current_user.role != 'admin'):
            # Allow for signup/password reset if user_id is in session
            if otp_type in ['signup', 'password_reset'] and session.get('pending_user_id') == user_id:
                pass  # Allow
            else:
                return jsonify({
                    'success': False,
                    'message': 'Unauthorized'
                }), 403
        
        # Resend OTP
        success, message = otp_service.resend_otp(user_id, otp_type)
        
        return jsonify({
            'success': success,
            'message': message
        })
        
    except Exception as e:
        logger.error(f"Error in resend_otp: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'An error occurred. Please try again.'
        }), 500


@otp_bp.route('/status/<int:user_id>/<otp_type>')
def otp_status(user_id: int, otp_type: str):
    """Get OTP status for user."""
    try:
        # Check permissions
        if not current_user.is_authenticated or (current_user.id != user_id and current_user.role != 'admin'):
            # Allow for signup/password reset if user_id is in session
            if otp_type in ['signup', 'password_reset'] and session.get('pending_user_id') == user_id:
                pass  # Allow
            else:
                return jsonify({
                    'success': False,
                    'message': 'Unauthorized'
                }), 403
        
        # Get OTP status
        status = otp_service.get_otp_status(user_id, otp_type)
        
        return jsonify({
            'success': True,
            'status': status
        })
        
    except Exception as e:
        logger.error(f"Error getting OTP status: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'An error occurred. Please try again.'
        }), 500


@otp_bp.route('/cleanup', methods=['POST'])
@login_required
def cleanup_expired():
    """Cleanup expired OTP records (admin only)."""
    if current_user.role != 'admin':
        return jsonify({
            'success': False,
            'message': 'Unauthorized'
        }), 403
    
    try:
        count = otp_service.cleanup_expired_otps()
        return jsonify({
            'success': True,
            'message': f'Cleaned up {count} expired OTP records'
        })
        
    except Exception as e:
        logger.error(f"Error cleaning up OTPs: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'An error occurred during cleanup'
        }), 500