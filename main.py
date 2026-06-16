# main.py
# Ana giris noktasi.
# APScheduler ile tum gorevleri zamanlayarak calistirir.
# Ayni zamanda FastAPI web panelini de ayaga kaldirir.

import logging
import os
import threading
import time
from datetime import datetime, timezone

import uvicorn
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

# Logging ayarla
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def job_universe():
    """Her gun 00:05 UTC — evren guncelle."""
    logger.info("=== EVREN GOREVI BASLIYOR ===")
    try:
        from scanner.universe import run_universe_job
        run_universe_job()
    except Exception as e:
        logger.error(f"Evren gorevi hatasi: {e}")


def job_scan():
    """Her 5 dakikada bir — sinyal tara."""
    logger.info("--- Tarama basladi ---")
    try:
        from scanner.signal_scanner import run_scan
        run_scan()
    except Exception as e:
        logger.error(f"Tarama gorevi hatasi: {e}")


def job_track():
    """Her 1 dakikada bir — hedef takip."""
    try:
        from signals.tracker import track_targets
        track_targets()
    except Exception as e:
        logger.error(f"Takip gorevi hatasi: {e}")


def start_scheduler():
    scheduler = BackgroundScheduler(timezone="UTC")

    # Evren guncelleme — her gun 00:05 UTC
    scheduler.add_job(
        job_universe,
        CronTrigger(hour=0, minute=5, timezone="UTC"),
        id="universe_job",
        name="Evren Guncelleme",
        replace_existing=True,
    )

    # Sinyal tarama — her 5 dakika
    scheduler.add_job(
        job_scan,
        IntervalTrigger(seconds=300),
        id="scan_job",
        name="Sinyal Tarama",
        replace_existing=True,
    )

    # Hedef takip — her 1 dakika
    scheduler.add_job(
        job_track,
        IntervalTrigger(seconds=60),
        id="track_job",
        name="Hedef Takip",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("Zamanlayici basladi.")
    return scheduler


def main():
    logger.info("="*50)
    logger.info("  KRİPTO SİNYAL SİSTEMİ BAŞLIYOR")
    logger.info("="*50)

    # Telegram bildirim
    try:
        from telegram.notifier import send_startup
        send_startup()
    except Exception as e:
        logger.warning(f"Telegram baslangic bildirimi: {e}")

    # Evren dosyasi yoksa hemen olustur
    if not os.path.exists("data/universe_latest.json"):
        logger.info("Ilk evren olusturuluyor...")
        job_universe()

    # Zamanlayiciyi baslat
    scheduler = start_scheduler()

    # Ilk taramayi hemen calistir
    logger.info("Ilk tarama baslıyor...")
    job_scan()

    # Web paneli baslat (ayri thread'de)
    from dashboard.app import app

    port = int(os.getenv("PORT", 8000))
    logger.info(f"Web paneli: http://0.0.0.0:{port}")

    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")


if __name__ == "__main__":
    main()
