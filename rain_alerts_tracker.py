"""
Rain Alerts Tracker
"""

import json
import os
from datetime import datetime, timedelta
from threading import Lock

TRACKER_FILE = 'rain_alerts_sent.json'
TRACKER_LOCK = Lock()

def load_tracker():
    """Load sent alerts tracker."""
    if os.path.exists(TRACKER_FILE):
        try:
            with open(TRACKER_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_tracker(tracker):
    """Save sent alerts tracker."""
    with TRACKER_LOCK:
        try:
            with open(TRACKER_FILE, 'w', encoding='utf-8') as f:
                json.dump(tracker, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"Error saving tracker: {e}")
            return False

def has_alert_been_sent_recently(user_id, city, rain_time_str, cooldown_hours=6):
    """
    Check if we've sent an alert for this user/city/rain_time recently.
    
    Args:
        user_id: Telegram user ID
        city: City name
        rain_time_str: String representation of rain start time (e.g., "14:30")
        cooldown_hours: How many hours to wait before sending another alert for same rain event
    
    Returns:
        bool: True if alert was sent recently, False otherwise
    """
    tracker = load_tracker()
    
    # Create a unique key for this rain event
    event_key = f"{user_id}_{city}_{rain_time_str}"
    
    if event_key in tracker:
        last_sent_str = tracker[event_key]
        try:
            last_sent = datetime.fromisoformat(last_sent_str)
            hours_since_last = (datetime.now() - last_sent).total_seconds() / 3600
            
            # If sent within cooldown period, don't send again
            if hours_since_last < cooldown_hours:
                return True
        except:
            # If timestamp is invalid, remove the entry
            del tracker[event_key]
            save_tracker(tracker)
    
    return False

def mark_alert_as_sent(user_id, city, rain_time_str):
    """Mark an alert as sent for this user/city/rain_time."""
    tracker = load_tracker()
    
    # Create unique key
    event_key = f"{user_id}_{city}_{rain_time_str}"
    
    # Store current time
    tracker[event_key] = datetime.now().isoformat()
    
    # Clean old entries (older than 24 hours)
    to_delete = []
    for key, timestamp_str in tracker.items():
        try:
            timestamp = datetime.fromisoformat(timestamp_str)
            if (datetime.now() - timestamp).total_seconds() > 24 * 3600:  # 24 hours
                to_delete.append(key)
        except:
            to_delete.append(key)
    
    for key in to_delete:
        del tracker[key]
    
    save_tracker(tracker)
    return True

def get_user_recent_alerts(user_id, hours=24):
    """Get recent alerts sent to a user."""
    tracker = load_tracker()
    user_alerts = []
    
    for key, timestamp_str in tracker.items():
        if key.startswith(f"{user_id}_"):
            try:
                timestamp = datetime.fromisoformat(timestamp_str)
                if (datetime.now() - timestamp).total_seconds() <= hours * 3600:
                    # Extract city and rain time from key
                    parts = key.split('_')
                    if len(parts) >= 3:
                        city = parts[1]
                        rain_time = parts[2] if len(parts) > 2 else "unknown"
                        user_alerts.append({
                            'city': city,
                            'rain_time': rain_time,
                            'sent_at': timestamp_str
                        })
            except:
                continue
    
    return user_alerts