import sqlite3
import os
from datetime import datetime

def backup_database():
    """Backup SQLite database to a file that persists on Render's ephemeral storage."""
    source_db = 'users.db'
    backup_dir = 'backups'
    
    # Create backup directory
    os.makedirs(backup_dir, exist_ok=True)
    
    # Create backup filename with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = f'{backup_dir}/users_backup_{timestamp}.db'
    
    # Copy database
    source = sqlite3.connect(source_db)
    backup = sqlite3.connect(backup_file)
    
    source.backup(backup)
    
    source.close()
    backup.close()
    
    print(f"✅ Backup created: {backup_file}")
    
    # Keep only last 7 backups
    backups = sorted([f for f in os.listdir(backup_dir) if f.endswith('.db')])
    if len(backups) > 7:
        for old_backup in backups[:-7]:
            os.remove(os.path.join(backup_dir, old_backup))
            print(f"🗑️  Deleted old backup: {old_backup}")

if __name__ == '__main__':
    backup_database()