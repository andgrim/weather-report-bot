"""
Database utilities for weather bot.
All modules should use these functions to access the database.
This ensures consistent database access across webhook and cron jobs.
"""

import sqlite3
import logging

logger = logging.getLogger(__name__)

def get_all_users_with_cities():
    """Get all users with saved cities from SQLite database."""
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute('SELECT user_id, city FROM users WHERE city IS NOT NULL AND city != ""')
        users = cursor.fetchall()
        conn.close()
        
        return {str(user[0]): user[1] for user in users}
    except Exception as e:
        logger.error(f"Error getting users from database: {e}")
        return {}

def get_all_users_with_rain_alerts():
    """Get all users with rain alerts enabled."""
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute('SELECT user_id FROM users WHERE rain_alerts = 1 AND city IS NOT NULL')
        users = cursor.fetchall()
        conn.close()
        
        return {str(user[0]): True for user in users}
    except Exception as e:
        logger.error(f"Error getting users with rain alerts: {e}")
        return {}

def get_user_language(user_id):
    """Get user language."""
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute('SELECT language FROM users WHERE user_id = ?', (str(user_id),))
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result else 'en'
    except Exception as e:
        logger.error(f"Error getting user language: {e}")
        return 'en'

def get_user_city(user_id):
    """Get user city."""
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute('SELECT city FROM users WHERE user_id = ?', (str(user_id),))
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result else None
    except Exception as e:
        logger.error(f"Error getting user city: {e}")
        return None

def get_database_stats():
    """Get database statistics."""
    try:
        conn = sqlite3.connect('users.db')
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
    except Exception as e:
        logger.error(f"Error getting database stats: {e}")
        return {}