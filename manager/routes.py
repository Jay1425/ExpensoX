"""
Manager Blueprint for Expense Approval Workflow
Handles approval dashboard, pending approvals, and approval actions
"""

from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from database.models import db, User, Expense, ApprovalHistory, ApprovalFlow, ExpenseStatus
from sqlalchemy import and_, or_
from datetime import datetime

manager_bp = Blueprint('manager', __name__, url_prefix='/manager')

def manager_required(f):
	"""Decorator to require manager role or manager_approver status."""
	def decorated_function(*args, **kwargs):
		if not (current_user.role == 'Manager' or current_user.is_manager_approver):
			flash('Access denied. Manager privileges required.', 'danger')
			return redirect(url_for('auth.dashboard'))
		return f(*args, **kwargs)
	decorated_function.__name__ = f.__name__
	return decorated_function

@manager_bp.route('/dashboard')
@login_required
@manager_required
def dashboard():
	"""Manager dashboard showing approval statistics and recent activity."""
	company_id = current_user.company_id
	
	# Get pending approvals count
	pending_count = Expense.query.filter(
		and_(
			Expense.company_id == company_id,
			Expense.status.in_([ExpenseStatus.PENDING, ExpenseStatus.IN_PROGRESS])
		)
	).count()
	
	# Get total expenses requiring manager approval
	total_expenses = Expense.query.filter_by(company_id=company_id).count()
	
	# Get recent approval activity for this manager
	recent_approvals = ApprovalHistory.query.filter_by(approver_id=current_user.id)\
		.order_by(ApprovalHistory.action_time.desc()).limit(10).all()
	
	# Get expenses directly managed by this user (their direct reports)
	team_expenses = Expense.query.join(User, Expense.submitted_by_user_id == User.id)\
		.filter(User.manager_id == current_user.id)\
		.order_by(Expense.submitted_at.desc()).limit(10).all()
	
	return render_template('manager/dashboard.html',
	                     pending_count=pending_count,
	                     total_expenses=total_expenses,
	                     recent_approvals=recent_approvals,
	                     team_expenses=team_expenses,
	                     current_user=current_user)

@manager_bp.route('/pending-approvals')
@login_required
@manager_required
def pending_approvals():
	"""List all pending approvals for this manager."""
	company_id = current_user.company_id
	page = request.args.get('page', 1, type=int)
	
	# Get expenses that need approval from this manager
	# This could be based on approval flows or direct manager relationship
	pending_expenses = Expense.query.filter(
		and_(
			Expense.company_id == company_id,
			Expense.status.in_([ExpenseStatus.PENDING, ExpenseStatus.IN_PROGRESS]),
			or_(
				# Expenses from direct reports
				Expense.submitter.has(manager_id=current_user.id),
				# Expenses in approval flow where this manager is the current approver
				Expense.approval_flow.has(
					and_(
						ApprovalFlow.approver_id == current_user.id,
						ApprovalFlow.step_number == Expense.current_approver_step
					)
				)
			)
		)
	).paginate(page=page, per_page=20, error_out=False)
	
	return render_template('manager/pending_approvals.html', 
	                     expenses=pending_expenses, 
	                     current_user=current_user)

@manager_bp.route('/approval/<int:expense_id>')
@login_required
@manager_required
def approval_detail(expense_id):
	"""Show detailed view of an expense for approval."""
	expense = Expense.query.get_or_404(expense_id)
	
	# Check if this manager has permission to approve this expense
	if not (expense.submitter.manager_id == current_user.id or 
	        (expense.approval_flow and expense.approval_flow.approver_id == current_user.id)):
		flash('You do not have permission to approve this expense.', 'danger')
		return redirect(url_for('manager.pending_approvals'))
	
	# Get approval history for this expense
	approval_history = ApprovalHistory.query.filter_by(expense_id=expense_id)\
		.order_by(ApprovalHistory.action_time.desc()).all()
	
	return render_template('manager/approval_detail.html',
	                     expense=expense,
	                     approval_history=approval_history,
	                     current_user=current_user)

@manager_bp.route('/approve/<int:expense_id>', methods=['POST'])
@login_required
@manager_required
def approve_expense(expense_id):
	"""Approve an expense."""
	expense = Expense.query.get_or_404(expense_id)
	comment = request.form.get('comment', '')
	
	# Check permission
	if not (expense.submitter.manager_id == current_user.id or 
	        (expense.approval_flow and expense.approval_flow.approver_id == current_user.id)):
		flash('You do not have permission to approve this expense.', 'danger')
		return redirect(url_for('manager.pending_approvals'))
	
	try:
		# Create approval history record
		approval = ApprovalHistory(
			expense_id=expense_id,
			approver_id=current_user.id,
			action='Approved',
			comment=comment
		)
		db.session.add(approval)
		
		# Check if this is part of a multi-step approval flow
		if expense.approval_flow_id:
			# Get next step in approval flow
			next_flow = ApprovalFlow.query.filter(
				and_(
					ApprovalFlow.company_id == expense.company_id,
					ApprovalFlow.sequence_order > expense.current_approver_step
				)
			).order_by(ApprovalFlow.sequence_order).first()
			
			if next_flow:
				# Move to next approval step
				expense.current_approver_step = next_flow.step_number
				expense.status = ExpenseStatus.IN_PROGRESS
			else:
				# Final approval
				expense.mark_approved(current_user, comment)
		else:
			# Simple manager approval
			expense.mark_approved(current_user, comment)
		
		db.session.commit()
		flash('Expense approved successfully.', 'success')
		
	except Exception as e:
		db.session.rollback()
		flash(f'Error approving expense: {str(e)}', 'danger')
	
	return redirect(url_for('manager.pending_approvals'))

@manager_bp.route('/reject/<int:expense_id>', methods=['POST'])
@login_required
@manager_required
def reject_expense(expense_id):
	"""Reject an expense."""
	expense = Expense.query.get_or_404(expense_id)
	comment = request.form.get('comment', '')
	
	# Check permission
	if not (expense.submitter.manager_id == current_user.id or 
	        (expense.approval_flow and expense.approval_flow.approver_id == current_user.id)):
		flash('You do not have permission to reject this expense.', 'danger')
		return redirect(url_for('manager.pending_approvals'))
	
	if not comment:
		flash('A comment is required when rejecting an expense.', 'danger')
		return redirect(url_for('manager.approval_detail', expense_id=expense_id))
	
	try:
		# Create approval history record
		approval = ApprovalHistory(
			expense_id=expense_id,
			approver_id=current_user.id,
			action='Rejected',
			comment=comment
		)
		db.session.add(approval)
		
		# Mark expense as rejected
		expense.mark_rejected(current_user, comment)
		
		db.session.commit()
		flash('Expense rejected successfully.', 'success')
		
	except Exception as e:
		db.session.rollback()
		flash(f'Error rejecting expense: {str(e)}', 'danger')
	
	return redirect(url_for('manager.pending_approvals'))

@manager_bp.route('/team-expenses')
@login_required
@manager_required
def team_expenses():
	"""View all expenses from team members."""
	page = request.args.get('page', 1, type=int)
	status_filter = request.args.get('status', '')
	
	# Base query for team expenses
	query = Expense.query.join(User, Expense.submitted_by_user_id == User.id)\
		.filter(User.manager_id == current_user.id)
	
	# Apply status filter if provided
	if status_filter:
		query = query.filter(Expense.status == status_filter)
	
	expenses = query.order_by(Expense.submitted_at.desc())\
		.paginate(page=page, per_page=20, error_out=False)
	
	return render_template('manager/team_expenses.html',
	                     expenses=expenses,
	                     status_filter=status_filter,
	                     current_user=current_user)

@manager_bp.route('/reports')
@login_required
@manager_required
def reports():
	"""Generate approval and team expense reports."""
	# Get team expense statistics
	team_stats = db.session.query(
		ExpenseStatus,
		db.func.count(Expense.id).label('count'),
		db.func.sum(Expense.amount).label('total')
	).join(User, Expense.submitted_by_user_id == User.id)\
	 .filter(User.manager_id == current_user.id)\
	 .group_by(ExpenseStatus).all()
	
	# Get monthly expense trends for the team
	monthly_trends = db.session.query(
		db.func.strftime('%Y-%m', Expense.submitted_at).label('month'),
		db.func.count(Expense.id).label('count'),
		db.func.sum(Expense.amount).label('total')
	).join(User, Expense.submitted_by_user_id == User.id)\
	 .filter(User.manager_id == current_user.id)\
	 .group_by(db.func.strftime('%Y-%m', Expense.submitted_at))\
	 .order_by(db.func.strftime('%Y-%m', Expense.submitted_at).desc())\
	 .limit(12).all()
	
	return render_template('manager/reports.html',
	                     team_stats=team_stats,
	                     monthly_trends=monthly_trends,
	                     current_user=current_user)