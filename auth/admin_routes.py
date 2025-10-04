from flask import Blueprint, request, jsonify, session, redirect, url_for, flash
from database.models import User, db, RoleEnum
from auth.role_utils import role_required

auth_admin_bp = Blueprint('auth_admin', __name__, url_prefix='/auth/admin')

@auth_admin_bp.route('/create_user', methods=['POST'])
@role_required('CFO')
def create_user():
    data = request.get_json() or request.form
    name = data.get('name')
    email = data.get('email')
    raw_password = data.get('password')
    role = data.get('role', 'Employee')
    manager_id = data.get('manager_id')
    company_id = data.get('company_id')

    if not all([name, email, raw_password, role, company_id]):
        return jsonify({'error': 'Missing required fields'}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'Email already exists'}), 400

    user = User(
        name=name,
        email=email,
        role=RoleEnum[role.upper()],
        company_id=company_id,
        manager_id=manager_id,
        is_verified=True
    )
    user.set_password(raw_password)
    
    db.session.add(user)
    db.session.commit()
    return jsonify({'success': True, 'user_id': user.id, 'role': user.role.value})
