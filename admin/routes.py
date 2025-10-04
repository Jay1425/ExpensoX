"""
Admin Blueprint for Approval Workflow Management
Handles creation and management of approval flows and rules
"""

from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app
from flask_login import login_required, current_user
from database.models import db, User, Company, ApprovalFlow, ApprovalRule
from sqlalchemy import and_

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

def admin_required(f):
	"""Decorator to require admin role."""
	def decorated_function(*args, **kwargs):
		if current_user.role != 'Admin':
			flash('Access denied. Admin privileges required.', 'danger')
			return redirect(url_for('auth.dashboard'))
		return f(*args, **kwargs)
	decorated_function.__name__ = f.__name__
	return decorated_function

@admin_bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
	"""Admin dashboard showing approval flows and rules overview."""
	company_id = current_user.company_id
	
	# Get approval flows for the company
	approval_flows = ApprovalFlow.query.filter_by(company_id=company_id).order_by(ApprovalFlow.sequence_order).all()
	
	# Get approval rules for the company
	approval_rules = ApprovalRule.query.filter_by(company_id=company_id).all()
	
	# Get all managers in the company for display
	managers = User.query.filter(and_(User.company_id == company_id, User.is_manager_approver == True)).all()
	
	return render_template('admin/dashboard.html', 
	                     approval_flows=approval_flows,
	                     approval_rules=approval_rules,
	                     managers=managers,
	                     current_user=current_user)

@admin_bp.route('/users')
@login_required
@admin_required
def users():
	"""List all users in the company."""
	company_id = current_user.company_id
	page = request.args.get('page', 1, type=int)
	
	users = User.query.filter_by(company_id=company_id).paginate(
		page=page, per_page=20, error_out=False
	)
	
	return render_template('admin/users.html', users=users, current_user=current_user)

@admin_bp.route('/users/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_user():
	"""Create a new user."""
	if request.method == 'POST':
		name = request.form.get('name')
		email = request.form.get('email')
		role = request.form.get('role', 'Employee')
		is_manager = request.form.get('is_manager') == 'on'
		manager_id = request.form.get('manager_id')
		
		# Basic validation
		if not name or not email:
			flash('Name and email are required.', 'danger')
			return redirect(url_for('admin.create_user'))
		
		# Check if email already exists
		if User.query.filter_by(email=email).first():
			flash('Email already exists.', 'danger')
			return redirect(url_for('admin.create_user'))
		
		# Create new user
		user = User(
			name=name,
			email=email,
			role=role,
			company_id=current_user.company_id,
			is_manager_approver=is_manager,
			manager_id=int(manager_id) if manager_id else None,
			is_verified=True  # Admin-created users are auto-verified
		)
		
		# Set default password (user will need to reset)
		user.set_password('TempPassword123!')
		
		try:
			db.session.add(user)
			db.session.commit()
			flash(f'User {name} created successfully. Default password: TempPassword123!', 'success')
			return redirect(url_for('admin.users'))
		except Exception as e:
			db.session.rollback()
			flash(f'Error creating user: {str(e)}', 'danger')
			return redirect(url_for('admin.create_user'))
	
	# Get all managers for the dropdown
	managers = User.query.filter(and_(
		User.company_id == current_user.company_id,
		User.is_manager_approver == True
	)).all()
	
	return render_template('admin/create_user.html', managers=managers, current_user=current_user)

@admin_bp.route('/approval-flows')
@login_required
@admin_required
def approval_flows():
	"""List all approval flows for the company."""
	company_id = current_user.company_id
	flows = ApprovalFlow.query.filter_by(company_id=company_id).order_by(ApprovalFlow.sequence_order).all()
	
	return render_template('admin/approval_flows.html', flows=flows, current_user=current_user)

@admin_bp.route('/approval-flows/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_approval_flow():
	"""Create a new approval flow."""
	if request.method == 'POST':
		step_number = request.form.get('step_number', type=int)
		approver_role = request.form.get('approver_role')
		approver_id = request.form.get('approver_id')
		sequence_order = request.form.get('sequence_order', type=int)
		
		# Basic validation
		if not step_number or not sequence_order:
			flash('Step number and sequence order are required.', 'danger')
			return redirect(url_for('admin.create_approval_flow'))
		
		# Validate that either role or specific approver is provided
		if not approver_role and not approver_id:
			flash('Either approver role or specific approver must be selected.', 'danger')
			return redirect(url_for('admin.create_approval_flow'))
		
		# Create approval flow
		flow = ApprovalFlow(
			company_id=current_user.company_id,
			step_number=step_number,
			approver_role=approver_role if approver_role else None,
			approver_id=int(approver_id) if approver_id else None,
			sequence_order=sequence_order
		)
		
		try:
			db.session.add(flow)
			db.session.commit()
			flash('Approval flow created successfully.', 'success')
			return redirect(url_for('admin.approval_flows'))
		except Exception as e:
			db.session.rollback()
			flash(f'Error creating approval flow: {str(e)}', 'danger')
			return redirect(url_for('admin.create_approval_flow'))
	
	# Get all managers for the dropdown
	managers = User.query.filter(and_(
		User.company_id == current_user.company_id,
		User.is_manager_approver == True
	)).all()
	
	return render_template('admin/create_approval_flow.html', managers=managers, current_user=current_user)

@admin_bp.route('/approval-rules')
@login_required
@admin_required
def approval_rules():
	"""List all approval rules for the company."""
	company_id = current_user.company_id
	rules = ApprovalRule.query.filter_by(company_id=company_id).all()
	
	return render_template('admin/approval_rules.html', rules=rules, current_user=current_user)

@admin_bp.route('/approval-rules/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_approval_rule():
	"""Create a new approval rule."""
	if request.method == 'POST':
		rule_type = request.form.get('rule_type')
		threshold_percent = request.form.get('threshold_percent', type=float)
		specific_approver_id = request.form.get('specific_approver_id')
		hybrid_logic = request.form.get('hybrid_logic')
		
		# Basic validation
		if not rule_type:
			flash('Rule type is required.', 'danger')
			return redirect(url_for('admin.create_approval_rule'))
		
		# Validate based on rule type
		if rule_type == 'percentage' and not threshold_percent:
			flash('Threshold percentage is required for percentage-based rules.', 'danger')
			return redirect(url_for('admin.create_approval_rule'))
		
		if rule_type == 'specific' and not specific_approver_id:
			flash('Specific approver is required for specific approver rules.', 'danger')
			return redirect(url_for('admin.create_approval_rule'))
		
		if rule_type == 'hybrid' and not hybrid_logic:
			flash('Hybrid logic is required for hybrid rules.', 'danger')
			return redirect(url_for('admin.create_approval_rule'))
		
		# Create approval rule
		rule = ApprovalRule(
			company_id=current_user.company_id,
			rule_type=rule_type,
			threshold_percent=threshold_percent if rule_type in ['percentage', 'hybrid'] else None,
			specific_approver_id=int(specific_approver_id) if specific_approver_id else None,
			hybrid_logic=hybrid_logic if rule_type == 'hybrid' else None
		)
		
		try:
			db.session.add(rule)
			db.session.commit()
			flash('Approval rule created successfully.', 'success')
			return redirect(url_for('admin.approval_rules'))
		except Exception as e:
			db.session.rollback()
			flash(f'Error creating approval rule: {str(e)}', 'danger')
			return redirect(url_for('admin.create_approval_rule'))
	
	# Get all managers for the dropdown
	managers = User.query.filter(and_(
		User.company_id == current_user.company_id,
		User.is_manager_approver == True
	)).all()
	
	return render_template('admin/create_approval_rule.html', managers=managers, current_user=current_user)