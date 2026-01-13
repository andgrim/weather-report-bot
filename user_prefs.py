import json
import os
import logging
from threading import Lock

logger = logging.getLogger(__name__)

USER_PREFS_FILE = 'user_preferences.json'
PREFS_LOCK = Lock()

def load_user_prefs():
    """Load user preferences from file."""
    with PREFS_LOCK:
        if os.path.exists(USER_PREFS_FILE):
            try:
                with open(USER_PREFS_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except Exception as e:
                logger.error(f"Error loading preferences: {e}")
                data = {}
        else:
            data = {}
    
    # GARANTISCI che queste chiavi esistano sempre
    if 'cities' not in data:
        data['cities'] = {}
    if 'rain_alerts' not in data:
        data['rain_alerts'] = {}
    
    return data

def save_user_prefs(prefs):
    """Save user preferences to file."""
    with PREFS_LOCK:
        try:
            with open(USER_PREFS_FILE, 'w', encoding='utf-8') as f:
                json.dump(prefs, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving preferences: {e}")

def get_user_language(user_id):
    """Get user's language preference."""
    prefs = load_user_prefs()
    return prefs.get(str(user_id), 'en')

def set_user_language(user_id, lang):
    """Set user's language preference."""
    prefs = load_user_prefs()
    prefs[str(user_id)] = lang
    save_user_prefs(prefs)
    return True

def get_user_city(user_id):
    """Get user's saved city."""
    prefs = load_user_prefs()
    return prefs.get('cities', {}).get(str(user_id))

def save_user_city(user_id, city):
    """Save user's city."""
    prefs = load_user_prefs()
    
    if 'cities' not in prefs:
        prefs['cities'] = {}
    
    prefs['cities'][str(user_id)] = city
    save_user_prefs(prefs)
    return True

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
    return True

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