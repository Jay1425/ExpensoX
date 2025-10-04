"""
Migration script to add is_admin_created field to users table
"""

from app import create_app
from database.models import db
from sqlalchemy import text

def migrate_admin_created_field():
    """Add is_admin_created field to users table"""
    app = create_app()
    
    with app.app_context():
        try:
            print("Adding is_admin_created field to users table...")
            
            # Check if field already exists
            inspector = db.inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('users')]
            
            if 'is_admin_created' not in columns:
                # Add the new column
                with db.engine.connect() as conn:
                    conn.execute(text('ALTER TABLE users ADD COLUMN is_admin_created BOOLEAN DEFAULT FALSE'))
                    
                    # Set all CFO users as not admin-created (they signed up themselves)
                    # Set all non-CFO users as admin-created (they were created by CFOs)
                    conn.execute(text("""
                        UPDATE users 
                        SET is_admin_created = CASE 
                            WHEN role = 'CFO' THEN FALSE 
                            ELSE TRUE 
                        END
                    """))
                    
                    conn.commit()
                
                print("Successfully added is_admin_created field and updated existing data")
                
                # Show current status
                with db.engine.connect() as conn:
                    result = conn.execute(text("""
                        SELECT role, is_admin_created, COUNT(*) as count 
                        FROM users 
                        GROUP BY role, is_admin_created
                    """))
                    
                    print("\nCurrent user status:")
                    for row in result:
                        admin_status = "Admin-created" if row[1] else "Self-signup"
                        print(f"  {row[0]}: {row[2]} users ({admin_status})")
                    
            else:
                print("is_admin_created field already exists")
            
        except Exception as e:
            print(f"Migration failed: {e}")
            db.session.rollback()
            raise

if __name__ == "__main__":
    migrate_admin_created_field()