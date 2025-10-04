from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from functools import wraps
import os
import sys
import requests
from datetime import datetime, date
from decimal import Decimal

# Add the parent directory to the path to import models
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    from database.models import User, Company, RoleEnum as UserRole, db, Expense, Category, ExpenseStatus
except ImportError:
    # Fallback for different import paths
    from app import User, Company, UserRole, db, Expense, Category, ExpenseStatus

employee_bp = Blueprint('employee', __name__, url_prefix='/employee')

def employee_required(f):
    """Decorator to ensure only Employee users can access employee routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = session.get("user_id")
        if not user_id:
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('auth.login'))
        
        user = User.query.get(user_id)
        if not user or user.role != UserRole.EMPLOYEE:
            flash('Access denied. Employee privileges required.', 'error')
            return redirect(url_for('auth.dashboard'))
        
        return f(*args, **kwargs)
    return decorated_function

def get_current_user():
    """Get the current user from session"""
    user_id = session.get("user_id")
    if user_id:
        return User.query.get(user_id)
    return None

def fetch_currencies():
    """Fetch currencies from REST Countries API"""
    try:
        response = requests.get('https://restcountries.com/v3.1/all?fields=name,currencies', timeout=10)
        if response.status_code == 200:
            countries = response.json()
            currencies = {}
            
            for country in countries:
                if 'currencies' in country and country['currencies']:
                    for currency_code, currency_data in country['currencies'].items():
                        if currency_code not in currencies and len(currency_code) == 3:
                            currencies[currency_code] = {
                                'code': currency_code,
                                'name': currency_data.get('name', currency_code)
                            }
            
            # Sort currencies by code
            return sorted(currencies.values(), key=lambda x: x['code'])
        else:
            # Fallback currencies if API fails
            return get_fallback_currencies()
    except Exception as e:
        print(f"Error fetching currencies: {e}")
        return get_fallback_currencies()

def get_fallback_currencies():
    """Fallback currency list"""
    return [
        {'code': 'USD', 'name': 'US Dollar'},
        {'code': 'EUR', 'name': 'Euro'},
        {'code': 'GBP', 'name': 'British Pound'},
        {'code': 'JPY', 'name': 'Japanese Yen'},
        {'code': 'CAD', 'name': 'Canadian Dollar'},
        {'code': 'AUD', 'name': 'Australian Dollar'},
        {'code': 'CHF', 'name': 'Swiss Franc'},
        {'code': 'CNY', 'name': 'Chinese Yuan'},
        {'code': 'INR', 'name': 'Indian Rupee'},
    ]

def convert_currency(amount, from_currency, to_currency):
    """Convert currency using exchange rate API"""
    if from_currency == to_currency:
        return amount
    
    try:
        response = requests.get(f'https://api.exchangerate-api.com/v4/latest/{from_currency}', timeout=10)
        if response.status_code == 200:
            data = response.json()
            if to_currency in data['rates']:
                rate = data['rates'][to_currency]
                return round(float(amount) * rate, 2)
    except Exception as e:
        print(f"Error converting currency: {e}")
    
    # If conversion fails, return original amount
    return amount

@employee_bp.route('/submit_expense', methods=['GET', 'POST'])
@employee_required
def submit_expense():
    """Submit expense form"""
    current_user = get_current_user()
    if not current_user:
        return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        try:
            # Get form data
            amount = request.form.get('amount')
            currency = request.form.get('currency')
            category_id = request.form.get('category_id')
            description = request.form.get('description')
            expense_date = request.form.get('date')
            
            # Validation
            if not all([amount, currency, category_id, description, expense_date]):
                flash('All fields are required.', 'error')
                return redirect(url_for('employee.submit_expense'))
            
            try:
                amount = float(amount)
                category_id = int(category_id)
                expense_date = datetime.strptime(expense_date, '%Y-%m-%d').date()
            except ValueError:
                flash('Invalid data format.', 'error')
                return redirect(url_for('employee.submit_expense'))
            
            # Get company currency for conversion
            company = current_user.company
            if not company:
                flash('Company information not found.', 'error')
                return redirect(url_for('employee.submit_expense'))
            
            # Convert to company currency
            converted_amount = convert_currency(amount, currency, company.currency)
            
            # Create expense
            expense = Expense(
                employee_id=current_user.id,
                company_id=company.id,
                amount=amount,
                currency=currency,
                converted_amount=converted_amount,
                description=description,
                category_id=category_id,
                date=expense_date,
                status='PENDING',
                current_approver_id=current_user.manager_id if current_user.manager_id else None
            )
            
            db.session.add(expense)
            db.session.commit()
            
            flash('Expense submitted successfully!', 'success')
            return redirect(url_for('employee.expense_history'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error submitting expense: {str(e)}', 'error')
            return redirect(url_for('employee.submit_expense'))
    
    # GET request - show form
    try:
        # Get categories for the company
        categories = Category.query.filter_by(company_id=current_user.company_id).all()
        
        # Get currencies
        currencies = fetch_currencies()
        
        # Get company currency as default
        company_currency = current_user.company.currency if current_user.company else 'USD'
        
        return render_template('employee/submit_expense.html',
                             categories=categories,
                             currencies=currencies,
                             company_currency=company_currency,
                             current_user=current_user,
                             current_page='submit_expense')
    except Exception as e:
        flash(f'Error loading form: {str(e)}', 'error')
        return redirect(url_for('auth.dashboard'))

@employee_bp.route('/expense_history')
@employee_required
def expense_history():
    """View expense history"""
    current_user = get_current_user()
    if not current_user:
        return redirect(url_for('auth.login'))
    
    try:
        # Get all expenses for the current user
        expenses = Expense.query.filter_by(employee_id=current_user.id).order_by(Expense.created_at.desc()).all()
        
        return render_template('employee/expense_history.html',
                             expenses=expenses,
                             current_user=current_user,
                             current_page='expense_history')
    except Exception as e:
        flash(f'Error loading expense history: {str(e)}', 'error')
        return redirect(url_for('auth.dashboard'))

@employee_bp.route('/dashboard')
@employee_required
def dashboard():
    """Employee dashboard"""
    current_user = get_current_user()
    if not current_user:
        return redirect(url_for('auth.login'))
    
    try:
        # Get expense statistics
        total_expenses = Expense.query.filter_by(employee_id=current_user.id).count()
        pending_expenses = Expense.query.filter_by(employee_id=current_user.id, status='PENDING').count()
        approved_expenses = Expense.query.filter_by(employee_id=current_user.id, status='APPROVED').count()
        rejected_expenses = Expense.query.filter_by(employee_id=current_user.id, status='REJECTED').count()
        
        # Get recent expenses
        recent_expenses = Expense.query.filter_by(employee_id=current_user.id).order_by(Expense.created_at.desc()).limit(5).all()
        
        stats = {
            'total_expenses': total_expenses,
            'pending_expenses': pending_expenses,
            'approved_expenses': approved_expenses,
            'rejected_expenses': rejected_expenses,
            'recent_expenses': recent_expenses
        }
        
        return render_template('employee/dashboard.html',
                             stats=stats,
                             current_user=current_user,
                             company=current_user.company,
                             current_page='dashboard')
    except Exception as e:
        flash(f'Error loading dashboard: {str(e)}', 'error')
        return redirect(url_for('auth.dashboard'))

# API endpoint for fetching currencies (for frontend)
@employee_bp.route('/api/currencies')
@employee_required
def api_currencies():
    """API endpoint to fetch currencies"""
    currencies = fetch_currencies()
    return jsonify(currencies)

# API endpoint for currency conversion preview
@employee_bp.route('/api/convert', methods=['POST'])
@employee_required
def api_convert():
    """API endpoint to convert currency"""
    data = request.get_json()
    amount = data.get('amount')
    from_currency = data.get('from_currency')
    to_currency = data.get('to_currency')
    
    if not all([amount, from_currency, to_currency]):
        return jsonify({'error': 'Missing required parameters'}), 400
    
    try:
        converted_amount = convert_currency(float(amount), from_currency, to_currency)
        return jsonify({
            'converted_amount': converted_amount,
            'rate': converted_amount / float(amount) if float(amount) > 0 else 0
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500