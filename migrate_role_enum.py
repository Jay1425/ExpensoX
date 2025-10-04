"""
Migration script to update role enum values in the database
"""

from app import create_app
from database.models import db, User
from sqlalchemy import text

def migrate_role_enum():
    """Update role enum values to match new format"""
    app = create_app()
    
    with app.app_context():
        try:
            print("Updating role enum values...")
            
            # Map old values to new values
            role_mapping = {
                'Director': 'DIRECTOR',
                'Manager': 'MANAGER', 
                'Finance': 'FINANCE',
                'Employee': 'EMPLOYEE'
                # CFO stays the same
            }
            
            # Update all users with old role values
            for old_role, new_role in role_mapping.items():
                result = db.session.execute(
                    text("UPDATE users SET role = :new_role WHERE role = :old_role"), 
                    {"new_role": new_role, "old_role": old_role}
                )
                users_updated = result.rowcount
                if users_updated > 0:
                    print(f"Updated {users_updated} user(s) from role '{old_role}' to '{new_role}'")
            
            db.session.commit()
            print("Role enum migration completed successfully!")
            
            # Show current role distribution
            print("\nCurrent role distribution:")
            for role_val in ['CFO', 'DIRECTOR', 'MANAGER', 'FINANCE', 'EMPLOYEE']:
                result = db.session.execute(
                    text("SELECT COUNT(*) FROM users WHERE role = :role"), {"role": role_val}
                )
                count = result.scalar()
                if count > 0:
                    print(f"  {role_val}: {count} user(s)")
            
        except Exception as e:
            print(f"Migration failed: {e}")
            db.session.rollback()
            raise

if __name__ == "__main__":
    migrate_role_enum()