from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from functools import wraps
import os
import sys

# Add the parent directory to the path to import models
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    from database.models import User, Company, RoleEnum as UserRole, db
except ImportError:
    # Fallback for different import paths
    from app import User, Company, UserRole, db

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

def admin_required(f):
    """Decorator to ensure only CFO/Admin users can access admin routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = session.get("user_id")
        if not user_id:
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('auth.login'))
        
        user = User.query.get(user_id)
        if not user or user.role != UserRole.CFO:
            flash('Access denied. Admin privileges required.', 'error')
            return redirect(url_for('auth.dashboard'))
        
        return f(*args, **kwargs)
    return decorated_function

def get_current_user():
    """Get the current user from session"""
    user_id = session.get("user_id")
    if user_id:
        return User.query.get(user_id)
    return None

@admin_bp.route('/dashboard')
@admin_required
def dashboard():
    """Admin dashboard with overview statistics"""
    try:
        current_user = get_current_user()
        if not current_user:
            return redirect(url_for('auth.login'))
            
        # Get company info
        company = Company.query.first()
        
        # Get user statistics
        total_users = User.query.count()
        cfo_count = User.query.filter_by(role=UserRole.CFO).count()
        director_count = User.query.filter_by(role=UserRole.DIRECTOR).count()
        manager_count = User.query.filter_by(role=UserRole.MANAGER).count()
        finance_count = User.query.filter_by(role=UserRole.FINANCE).count()
        employee_count = User.query.filter_by(role=UserRole.EMPLOYEE).count()
        
        # Get recent users
        recent_users = User.query.order_by(User.id.desc()).limit(5).all()
        
        stats = {
            'total_users': total_users,
            'cfo_count': cfo_count,
            'director_count': director_count,
            'manager_count': manager_count,
            'finance_count': finance_count,
            'employee_count': employee_count,
            'recent_users': recent_users
        }
        
        return render_template('admin/dashboard.html', 
                             company=company, 
                             stats=stats,
                             current_user=current_user,
                             current_page='dashboard')
    except Exception as e:
        flash(f'Error loading dashboard: {str(e)}', 'error')
        return redirect(url_for('auth.dashboard'))

@admin_bp.route('/users')
@admin_required
def users():
    """Manage users page"""
    try:
        current_user = get_current_user()
        if not current_user:
            return redirect(url_for('auth.login'))
            
        # Scope view to current company where possible
        user_query = User.query
        manager_query = User.query

        if current_user.company_id:
            user_query = user_query.filter(User.company_id == current_user.company_id)
            manager_query = manager_query.filter(User.company_id == current_user.company_id)

        # Get all users except the current admin for listing
        users = (user_query
                 .filter(User.id != current_user.id)
                 .order_by(User.name.asc())
                 .all())

        # Collect all potential managers including the CFO/admin
        manager_options = (manager_query
                           .filter(User.role.in_([UserRole.CFO, UserRole.DIRECTOR, UserRole.MANAGER]))
                           .order_by(User.name.asc())
                           .all())

        company = Company.query.first()
        
        return render_template('admin/users.html', 
                             users=users, 
                             manager_options=manager_options,
                             company=company,
                             current_user=current_user,
                             current_page='users')
    except Exception as e:
        flash(f'Error loading users: {str(e)}', 'error')
        return redirect(url_for('admin.dashboard'))

@admin_bp.route('/create-user', methods=['GET', 'POST'])
@admin_required
def create_user():
    """Create new user"""
    current_user = get_current_user()
    if not current_user:
        return redirect(url_for('auth.login'))
        
    if request.method == 'POST':
        try:
            name = request.form.get('name')
            email = request.form.get('email')
            role = request.form.get('role')
            manager_id = request.form.get('manager_id')
            
            if not all([name, email, role]):
                flash('All fields are required.', 'error')
                return redirect(url_for('admin.users'))
            
            # Check if user already exists
            if User.query.filter_by(email=email).first():
                flash('User with this email already exists.', 'error')
                return redirect(url_for('admin.users'))
            
            # Create new user
            new_user = User(
                name=name,
                email=email,
                role=UserRole(role),
                is_admin_created=True,
                company_id=current_user.company_id
            )
            
            # Set manager if provided
            if manager_id and manager_id != '':
                new_user.manager_id = int(manager_id)
            
            # Set default password (user will need to reset)
            new_user.set_password('TempPass123!')
            
            db.session.add(new_user)
            db.session.commit()
            
            flash(f'User {name} created successfully! Default password: TempPass123!', 'success')
            return redirect(url_for('admin.users'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating user: {str(e)}', 'error')
            return redirect(url_for('admin.users'))
    
    return redirect(url_for('admin.users'))

@admin_bp.route('/company')
@admin_required
def company():
    """Company management page"""
    try:
        current_user = get_current_user()
        if not current_user:
            return redirect(url_for('auth.login'))
            
        company = Company.query.first()
        return render_template('admin/company.html', 
                             company=company,
                             current_user=current_user,
                             current_page='company')
    except Exception as e:
        flash(f'Error loading company: {str(e)}', 'error')
        return redirect(url_for('admin.dashboard'))

@admin_bp.route('/approvals')
@admin_required
def approvals():
    """Approval settings page"""
    try:
        current_user = get_current_user()
        if not current_user:
            return redirect(url_for('auth.login'))
            
        company = Company.query.first()
        return render_template('admin/approvals.html', 
                             company=company,
                             current_user=current_user,
                             current_page='approvals')
    except Exception as e:
        flash(f'Error loading approvals: {str(e)}', 'error')
        return redirect(url_for('admin.dashboard'))

@admin_bp.route('/expenses')
@admin_required
def expenses():
    """Expense overview page"""
    try:
        current_user = get_current_user()
        if not current_user:
            return redirect(url_for('auth.login'))
            
        company = Company.query.first()
        return render_template('admin/expenses.html', 
                             company=company,
                             current_user=current_user,
                             current_page='expenses')
    except Exception as e:
        flash(f'Error loading expenses: {str(e)}', 'error')
        return redirect(url_for('admin.dashboard'))

@admin_bp.route('/reports')
@admin_required
def reports():
    """Reports page"""
    try:
        current_user = get_current_user()
        if not current_user:
            return redirect(url_for('auth.login'))
            
        company = Company.query.first()
        return render_template('admin/reports.html', 
                             company=company,
                             current_user=current_user,
                             current_page='reports')
    except Exception as e:
        flash(f'Error loading reports: {str(e)}', 'error')
        return redirect(url_for('admin.dashboard'))

@admin_bp.route('/notifications')
@admin_required
def notifications():
    """Notifications page"""
    try:
        current_user = get_current_user()
        if not current_user:
            return redirect(url_for('auth.login'))
            
        company = Company.query.first()
        return render_template('admin/notifications.html', 
                             company=company,
                             current_user=current_user,
                             current_page='notifications')
    except Exception as e:
        flash(f'Error loading notifications: {str(e)}', 'error')
        return redirect(url_for('admin.dashboard'))
        return redirect(url_for('admin.dashboard'))

@admin_bp.route('/profile')
@admin_required
def profile():
    """Profile and settings page"""
    try:
        current_user = get_current_user()
        if not current_user:
            return redirect(url_for('auth.login'))
            
        company = Company.query.first()
        return render_template('admin/profile.html', 
                             company=company,
                             user=current_user,
                             current_user=current_user,
                             current_page='profile')
    except Exception as e:
        flash(f'Error loading profile: {str(e)}', 'error')
        return redirect(url_for('admin.dashboard'))

@admin_bp.route('/delete-user/<int:user_id>', methods=['POST'])
@admin_required
def delete_user(user_id):
    """Delete a user"""
    try:
        current_user = get_current_user()
        if not current_user:
            return redirect(url_for('auth.login'))
            
        user = User.query.get_or_404(user_id)
        
        # Prevent deletion of the current admin
        if user.id == current_user.id:
            flash('Cannot delete your own account.', 'error')
            return redirect(url_for('admin.users'))
        
        # Prevent deletion of other CFOs
        if user.role == UserRole.CFO:
            flash('Cannot delete other CFO accounts.', 'error')
            return redirect(url_for('admin.users'))
        
        db.session.delete(user)
        db.session.commit()
        
        flash(f'User {user.name} deleted successfully.', 'success')
        return redirect(url_for('admin.users'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting user: {str(e)}', 'error')
        return redirect(url_for('admin.users'))