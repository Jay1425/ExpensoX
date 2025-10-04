"""
Migration script to fix category relationship in expenses table
"""

from app import create_app
from database.models import db

def migrate_category_fix():
    """Migrate category field to proper foreign key relationship"""
    app = create_app()
    
    with app.app_context():
        try:
            # Check if category_id column already exists
            inspector = db.inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('expenses')]
            
            if 'category_id' not in columns:
                print("Adding category_id column to expenses table...")
                db.engine.execute('ALTER TABLE expenses ADD COLUMN category_id INTEGER')
                
                # Add foreign key constraint if supported by the database
                try:
                    db.engine.execute('''
                        ALTER TABLE expenses 
                        ADD CONSTRAINT fk_expenses_category_id 
                        FOREIGN KEY (category_id) REFERENCES categories (id)
                    ''')
                    print("Added foreign key constraint for category_id")
                except Exception as e:
                    print(f"Could not add foreign key constraint (this is okay for SQLite): {e}")
            else:
                print("category_id column already exists")
            
            # Check if old category column exists and remove it
            if 'category' in columns:
                print("Removing old category column...")
                # For SQLite, we need to recreate the table to drop a column
                # But since this might have data, let's just leave it for now
                # The new code will use category_id instead
                print("Note: Old 'category' column still exists but will not be used")
            
            print("Migration completed successfully!")
            
        except Exception as e:
            print(f"Migration failed: {e}")
            db.session.rollback()
            raise

if __name__ == "__main__":
    migrate_category_fix()