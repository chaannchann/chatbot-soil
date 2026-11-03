"""Run database migration to add conversation_id column."""

import psycopg2
from config import Config

def run_migration():
    """Execute the migration SQL file."""
    try:
        # Read the migration file
        with open('migration.sql', 'r', encoding='utf-8') as f:
            migration_sql = f.read()
        
        # Connect to database
        conn = psycopg2.connect(
            host=Config.DB_HOST,
            port=Config.DB_PORT,
            dbname=Config.DB_NAME,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD
        )
        conn.autocommit = True
        
        # Execute migration
        with conn.cursor() as cur:
            cur.execute(migration_sql)
        
        print("[OK] Migration completed successfully!")
        print("     - conversation_id column added to chat_logs table")
        print("     - All indexes created")
        
        conn.close()
        
    except Exception as e:
        print(f"[ERROR] Migration failed: {e}")
        return False
    
    return True

if __name__ == '__main__':
    run_migration()
