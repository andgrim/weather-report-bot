"""
Bot Meteo Telegram - Versione Locale
Esegue tutto localmente: bot + cron jobs
"""

import logging
import schedule
import time
import threading
from datetime import datetime
import pytz

from bot_core import main as bot_main
from check_rain_alerts import check_and_send_rain_alerts
from send_morning_report import send_morning_reports
from backup_database import backup_database

# Configura logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Fuso orario italiano
ROME_TZ = pytz.timezone('Europe/Rome')

def run_bot():
    """Avvia il bot in modalità polling."""
    logger.info("🤖 Avvio del bot in modalità polling...")
    bot_main()

def run_rain_check():
    """Controlla le piogge in arrivo."""
    logger.info("🌧️ Esecuzione controllo piogge...")
    try:
        check_and_send_rain_alerts()
    except Exception as e:
        logger.error(f"Errore nel controllo piogge: {e}")

def run_morning_reports():
    """Invia i report mattutini."""
    current_time = datetime.now(ROME_TZ)
    logger.info(f"🌅 Esecuzione report mattutini alle {current_time.strftime('%H:%M')}...")
    try:
        send_morning_reports()
    except Exception as e:
        logger.error(f"Errore nei report mattutini: {e}")

def run_backup():
    """Esegue backup del database."""
    logger.info("💾 Esecuzione backup database...")
    try:
        backup_database()
    except Exception as e:
        logger.error(f"Errore nel backup: {e}")

def schedule_jobs():
    """Configura i lavori schedulati."""
    
    # Controllo piogge ogni 30 minuti
    schedule.every(30).minutes.do(run_rain_check)
    
    # Report mattutini ogni giorno alle 8:00
    schedule.every().day.at("08:00").do(run_morning_reports)
    
    # Backup giornaliero a mezzanotte
    schedule.every().day.at("00:00").do(run_backup)
    
    logger.info("⏰ Scheduler configurato:")
    logger.info("  • Controllo piogge: ogni 30 minuti")
    logger.info("  • Report mattutini: ogni giorno alle 8:00")
    logger.info("  • Backup DB: ogni giorno a mezzanotte")
    
    # Esegui subito un controllo iniziale
    logger.info("🔄 Esecuzione controllo iniziale...")
    run_rain_check()
    run_backup()
    
    # Loop dello scheduler
    while True:
        schedule.run_pending()
        time.sleep(60)  # Controlla ogni minuto

def main():
    """Funzione principale."""
    print("=" * 50)
    print("🌤️  BOT METEO TELEGRAM - VERSIONE LOCALE")
    print("=" * 50)
    print("Questo script eseguirà:")
    print("1. 🤖 Il bot Telegram in polling mode")
    print("2. ⏰ Scheduler per:")
    print("   • Controllo piogge (ogni 30 min)")
    print("   • Report mattutini (08:00 ogni giorno)")
    print("   • Backup DB (00:00 ogni giorno)")
    print("=" * 50)
    
    # Avvia lo scheduler in un thread separato
    scheduler_thread = threading.Thread(target=schedule_jobs, daemon=True)
    scheduler_thread.start()
    
    logger.info("✅ Scheduler avviato in background")
    
    # Avvia il bot (bloccante)
    try:
        run_bot()
    except KeyboardInterrupt:
        logger.info("🛑 Bot interrotto dall'utente")
    except Exception as e:
        logger.error(f"❌ Errore critico nel bot: {e}")
    finally:
        logger.info("👋 Script terminato")

if __name__ == '__main__':
    main()