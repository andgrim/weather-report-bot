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
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading preferences: {e}")
                return {}
        return {}

def save_user_prefs(prefs):
    """Save user preferences to file."""
    with PREFS_LOCK:
        try:
            with open(USER_PREFS_FILE, 'w', encoding='utf-8') as f:
                json.dump(prefs, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving preferences: {e}")

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