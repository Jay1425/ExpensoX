#!/usr/bin/env python3
"""
Migration script to add approval workflow tables and fields.
This script creates the new tables and adds fields to existing tables.
"""

from pathlib import Path

from flask import Flask
from database.models import db, ApprovalFlow, ApprovalRule, ApprovalHistory
from sqlalchemy import text

def create_app():
    """Create Flask app for migration."""
    app = Flask(__name__)
    base_dir = Path(__file__).resolve().parent
    db_path = base_dir / 'instance' / 'expensox.db'
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    db.init_app(app)
    return app

def run_migration():
    """Run the migration to add approval workflow features."""
    app = create_app()
    
    with app.app_context():
        try:
            print("Starting approval workflow migration...")
            
            # Create new tables
            print("Creating new approval workflow tables...")
            db.create_all()
            
            engine = db.engine
            inspector = db.inspect(engine)

            # Add new columns to existing expenses table
            print("Adding approval workflow columns to expenses table...")
            expense_columns = [col['name'] for col in inspector.get_columns('expenses')]
            
            with engine.begin() as connection:
                if 'approval_flow_id' not in expense_columns:
                    connection.execute(text('ALTER TABLE expenses ADD COLUMN approval_flow_id INTEGER'))
                    print("Added approval_flow_id column to expenses")
                
                if 'current_approver_step' not in expense_columns:
                    connection.execute(text('ALTER TABLE expenses ADD COLUMN current_approver_step INTEGER DEFAULT 1'))
                    print("Added current_approver_step column to expenses")

            # Add new columns to users table for approval workflow
            print("Adding approval workflow columns to users table...")
            user_columns = [col['name'] for col in inspector.get_columns('users')]

            with engine.begin() as connection:
                if 'is_manager_approver' not in user_columns:
                    connection.execute(text('ALTER TABLE users ADD COLUMN is_manager_approver BOOLEAN NOT NULL DEFAULT 0'))
                    print("Added is_manager_approver column to users")

                if 'manager_id' not in user_columns:
                    connection.execute(text('ALTER TABLE users ADD COLUMN manager_id INTEGER REFERENCES users(id)'))
                    print("Added manager_id column to users")
            
            # Update ExpenseStatus enum if needed
            print("Updating expense status enum...")
            with engine.begin() as connection:
                connection.execute(text("UPDATE expenses SET status = 'IN_PROGRESS' WHERE status = 'PENDING' AND approval_flow_id IS NOT NULL"))
            
            print("Migration completed successfully!")
            
        except Exception as e:
            print(f"Migration failed: {e}")
            raise

if __name__ == '__main__':
    run_migration()