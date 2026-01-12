import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    # Render assegna automaticamente una porta, la leggiamo qui
    PORT = int(os.environ.get('PORT', 10000))
    # Su Render, l'URL del servizio è in RENDER_EXTERNAL_URL
    RENDER_EXTERNAL_URL = os.environ.get('RENDER_EXTERNAL_URL', '')
    WEBHOOK_MODE = os.environ.get('RENDER', '').lower() == 'true'