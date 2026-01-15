import sqlite3
import os
from datetime import datetime

class UserDatabase:
    def __init__(self, db_path='users.db'):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize database tables."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                language TEXT DEFAULT 'en',
                city TEXT,
                rain_alerts INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Rain alerts log (per evitare duplicati)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS rain_alerts_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                city TEXT,
                alert_time TIMESTAMP,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def get_user(self, user_id):
        """Get user data."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE user_id = ?', (str(user_id),))
        user = cursor.fetchone()
        conn.close()
        
        if user:
            return {
                'user_id': user[0],
                'language': user[1],
                'city': user[2],
                'rain_alerts': bool(user[3]),
                'created_at': user[4],
                'updated_at': user[5]
            }
        return None
    
    def create_or_update_user(self, user_id, language='en', city=None, rain_alerts=False):
        """Create or update user data."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check if user exists
        cursor.execute('SELECT 1 FROM users WHERE user_id = ?', (str(user_id),))
        exists = cursor.fetchone()
        
        if exists:
            # Update existing user
            cursor.execute('''
                UPDATE users 
                SET language = ?, city = ?, rain_alerts = ?, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
            ''', (language, city, 1 if rain_alerts else 0, str(user_id)))
        else:
            # Create new user
            cursor.execute('''
                INSERT INTO users (user_id, language, city, rain_alerts)
                VALUES (?, ?, ?, ?)
            ''', (str(user_id), language, city, 1 if rain_alerts else 0))
        
        conn.commit()
        conn.close()
        return True
    
    def set_user_language(self, user_id, language):
        """Set user language."""
        user = self.get_user(user_id)
        if user:
            return self.create_or_update_user(
                user_id, language, user.get('city'), user.get('rain_alerts', False)
            )
        else:
            return self.create_or_update_user(user_id, language)
    
    def set_user_city(self, user_id, city):
        """Set user city."""
        user = self.get_user(user_id)
        if user:
            return self.create_or_update_user(
                user_id, user.get('language', 'en'), city, user.get('rain_alerts', False)
            )
        else:
            return self.create_or_update_user(user_id, city=city)
    
    def set_rain_alerts(self, user_id, enabled):
        """Enable/disable rain alerts."""
        user = self.get_user(user_id)
        if user:
            return self.create_or_update_user(
                user_id, user.get('language', 'en'), user.get('city'), enabled
            )
        else:
            return self.create_or_update_user(user_id, rain_alerts=enabled)
    
    def log_rain_alert(self, user_id, city):
        """Log a rain alert sent to user."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO rain_alerts_log (user_id, city, alert_time)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        ''', (str(user_id), city))
        conn.commit()
        conn.close()
        return True
    
    def get_recent_rain_alerts(self, user_id, hours=24):
        """Get recent rain alerts for a user."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT city, alert_time, sent_at
            FROM rain_alerts_log 
            WHERE user_id = ? 
            AND datetime(sent_at) > datetime('now', ?)
            ORDER BY sent_at DESC
        ''', (str(user_id), f'-{hours} hours'))
        alerts = cursor.fetchall()
        conn.close()
        
        return [
            {'city': a[0], 'alert_time': a[1], 'sent_at': a[2]}
            for a in alerts
        ]
    
    def should_send_rain_alert(self, user_id, cooldown_hours=6):
        """Check if we should send rain alert (cooldown)."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT sent_at 
            FROM rain_alerts_log 
            WHERE user_id = ? 
            ORDER BY sent_at DESC 
            LIMIT 1
        ''', (str(user_id),))
        last_alert = cursor.fetchone()
        conn.close()
        
        if not last_alert:
            return True
        
        # Calculate hours since last alert
        last_time = datetime.fromisoformat(last_alert[0].replace('Z', '+00:00'))
        hours_since = (datetime.utcnow() - last_time).total_seconds() / 3600
        
        return hours_since >= cooldown_hours
    
    def get_all_users_with_cities(self):
        """Get all users with saved cities."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT user_id, city FROM users WHERE city IS NOT NULL')
        users = cursor.fetchall()
        conn.close()
        
        return {str(user[0]): user[1] for user in users}
    
    def get_all_users_with_rain_alerts(self):
        """Get all users with rain alerts enabled."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT user_id FROM users WHERE rain_alerts = 1 AND city IS NOT NULL')
        users = cursor.fetchall()
        conn.close()
        
        return {str(user[0]): True for user in users}
    
    def get_stats(self):
        """Get database statistics."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM users')
        total_users = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM users WHERE city IS NOT NULL')
        users_with_cities = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM users WHERE rain_alerts = 1')
        users_with_alerts = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM rain_alerts_log')
        total_alerts = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            'total_users': total_users,
            'users_with_cities': users_with_cities,
            'users_with_rain_alerts': users_with_alerts,
            'total_rain_alerts_sent': total_alerts
        }

# Global database instance
db = UserDatabase()