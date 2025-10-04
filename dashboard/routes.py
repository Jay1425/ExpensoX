from flask import Blueprint, render_template, session, redirect, url_for, flash, request, jsonify
from database.models import User, Company, db, RoleEnum
from auth.role_utils import role_required

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')

@dashboard_bp.route('/admin')
@role_required('CFO')
def admin_dashboard():
    user_id = session.get("user_id")
    user = User.query.get(user_id)
    company = user.company
    
    # Get all company users for management
    company_users = User.query.filter_by(company_id=company.id).all()
    
    context = {
        'user': user,
        'company': company,
        'users': company_users,
        'total_users': len(company_users),
        'roles': [role.value for role in RoleEnum]
    }
    
    return render_template('dashboard/admin_dashboard.html', **context)

@dashboard_bp.route('/director')
@role_required('DIRECTOR')
def director_dashboard():
    user_id = session.get("user_id")
    user = User.query.get(user_id)
    company = user.company
    
    context = {
        'user': user,
        'company': company
    }
    
    return render_template('dashboard/director_dashboard.html', **context)

@dashboard_bp.route('/manager')
@role_required('MANAGER')
def manager_dashboard():
    user_id = session.get("user_id")
    user = User.query.get(user_id)
    company = user.company
    
    # Get managed users
    managed_users = User.query.filter_by(manager_id=user.id).all()
    
    context = {
        'user': user,
        'company': company,
        'managed_users': managed_users
    }
    
    return render_template('dashboard/manager_dashboard.html', **context)

@dashboard_bp.route('/finance')
@role_required('FINANCE')
def finance_dashboard():
    user_id = session.get("user_id")
    user = User.query.get(user_id)
    company = user.company
    
    context = {
        'user': user,
        'company': company
    }
    
    return render_template('dashboard/finance_dashboard.html', **context)

@dashboard_bp.route('/employee')
@role_required('EMPLOYEE')
def employee_dashboard():
    user_id = session.get("user_id")
    user = User.query.get(user_id)
    company = user.company
    
    context = {
        'user': user,
        'company': company
    }
    
    return render_template('dashboard/employee_dashboard.html', **context)

# CFO User Management Endpoints
@dashboard_bp.route('/create_user', methods=['POST'])
@role_required('CFO')
def create_user():
    user_id = session.get("user_id")
    current_user = User.query.get(user_id)
    
    data = request.get_json() or request.form
    name = data.get('name')
    email = data.get('email')
    raw_password = data.get('password', 'TempPassword123!')
    role = data.get('role', 'Employee')
    manager_id = data.get('manager_id')

    if not all([name, email, role]):
        return jsonify({'error': 'Missing required fields'}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'Email already exists'}), 400

    try:
        user = User(
            name=name,
            email=email,
            role=RoleEnum[role.upper()],
            company_id=current_user.company_id,
            manager_id=int(manager_id) if manager_id else None,
            is_verified=True,
            is_admin_created=True  # Mark as created by admin
        )
        user.set_password(raw_password)
        
        db.session.add(user)
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'user_id': user.id, 
            'role': user.role.value,
            'message': f'User {name} created successfully'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@dashboard_bp.route('/update_user_role', methods=['POST'])
@role_required('CFO')
def update_user_role():
    data = request.get_json() or request.form
    user_id = data.get('user_id')
    new_role = data.get('role')
    
    if not all([user_id, new_role]):
        return jsonify({'error': 'Missing required fields'}), 400
    
    try:
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
            
        user.role = RoleEnum[new_role.upper()]
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'User role updated to {new_role}'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@dashboard_bp.route('/get_users')
@role_required('CFO')
def get_users():
    user_id = session.get("user_id")
    current_user = User.query.get(user_id)
    
    users = User.query.filter_by(company_id=current_user.company_id).all()
    users_data = []
    
    for user in users:
        users_data.append({
            'id': user.id,
            'name': user.name,
            'email': user.email,
            'role': user.role.value,
            'manager_name': user.manager.name if user.manager else None,
            'is_verified': user.is_verified,
            'created_at': user.created_at.strftime('%Y-%m-%d')
        })
    
    return jsonify({'users': users_data})