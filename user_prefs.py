"""
Centralized user preferences module with file locking
Prevents race conditions between bot, morning reports, and rain alerts
"""

import json
import os
import atexit
from threading import Lock
import logging

logger = logging.getLogger(__name__)

USER_PREFS_FILE = 'user_preferences.json'
PREFS_LOCK = Lock()

def load_user_prefs():
    """Load user preferences from file with locking."""
    with PREFS_LOCK:
        if os.path.exists(USER_PREFS_FILE):
            try:
                with open(USER_PREFS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Error loading preferences: {e}")
                return {}
        return {}

def save_user_prefs(prefs):
    """Save user preferences to file with atomic write."""
    with PREFS_LOCK:
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(USER_PREFS_FILE), exist_ok=True)
            
            # Write to temporary file first (atomic operation)
            temp_file = USER_PREFS_FILE + '.tmp'
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(prefs, f, ensure_ascii=False, indent=2)
            
            # Atomically replace the old file
            if os.name == 'nt':  # Windows
                os.replace(temp_file, USER_PREFS_FILE)
            else:  # Unix/Linux/Mac
                os.rename(temp_file, USER_PREFS_FILE)
                
            logger.debug(f"Preferences saved successfully")
            
        except Exception as e:
            logger.error(f"Error saving preferences: {e}")
            # Clean up temp file if it exists
            if os.path.exists(temp_file):
                os.remove(temp_file)
            raise

def get_user_language(user_id):
    """Get user's preferred language."""
    prefs = load_user_prefs()
    return prefs.get(str(user_id), 'en')

def get_user_city(user_id):
    """Get user's saved city."""
    prefs = load_user_prefs()
    return prefs.get('cities', {}).get(str(user_id))

def save_user_city(user_id, city):
    """Save user's city preference."""
    prefs = load_user_prefs()
    
    if 'cities' not in prefs:
        prefs['cities'] = {}
    
    prefs['cities'][str(user_id)] = city
    save_user_prefs(prefs)

def get_rain_alerts_status(user_id):
    """Get user's rain alerts status."""
    prefs = load_user_prefs()
    return prefs.get('rain_alerts', {}).get(str(user_id), False)

def set_rain_alerts_status(user_id, status):
    """Set user's rain alerts status."""
    prefs = load_user_prefs()
    
    if 'rain_alerts' not in prefs:
        prefs['rain_alerts'] = {}
    
    prefs['rain_alerts'][str(user_id)] = status
    save_user_prefs(prefs)

def get_all_users_with_cities():
    """Get all users with saved cities."""
    prefs = load_user_prefs()
    return prefs.get('cities', {})

def get_all_users_with_rain_alerts():
    """Get all users with rain alerts enabled."""
    prefs = load_user_prefs()
    return {
        user_id: status 
        for user_id, status in prefs.get('rain_alerts', {}).items() 
        if status and user_id in prefs.get('cities', {})
    }

# Cleanup function
def cleanup():
    """Release any resources on exit."""
    pass

atexit.register(cleanup)