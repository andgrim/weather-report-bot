import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN is required in .env file")
    
    PORT = int(os.environ.get('PORT', 10000))
    RENDER_EXTERNAL_URL = os.environ.get('RENDER_EXTERNAL_URL', '')
    
    IS_RENDER = os.environ.get('RENDER', '').lower() == 'true'
    WEBHOOK_MODE = IS_RENDER and bool(RENDER_EXTERNAL_URL)
    WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET', '')
    
    CRON_SECRET = os.getenv('CRON_SECRET')
    ADMIN_USER_ID = os.getenv('ADMIN_USER_ID')
    
    @classmethod
    def validate(cls):
        if not cls.BOT_TOKEN:
            raise ValueError("BOT_TOKEN is required")
        
        if cls.WEBHOOK_MODE and not cls.RENDER_EXTERNAL_URL:
            raise ValueError("RENDER_EXTERNAL_URL is required for webhook mode")
        
        if not cls.WEBHOOK_SECRET:
            print("⚠️ WARNING: WEBHOOK_SECRET is not set")
        
        if not cls.CRON_SECRET:
            print("⚠️ WARNING: CRON_SECRET is not set")
        
        return True