# telegram/notifier.py
# Telegram bildirimleri

import logging
import requests
from datetime import datetime, timezone
from config.settings import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID

logger = logging.getLogger(__name__)

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"


def _send(text: str) -> bool:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram token veya chat ID eksik!")
        return False
    try:
        r = requests.post(f"{TELEGRAM_API}/sendMessage", json={
            "chat_id"   : TELEGRAM_CHAT_ID,
            "text"      : text,
            "parse_mode": "HTML",
        }, timeout=10)
        if r.status_code == 200:
            return True
        logger.error(f"Telegram hata: {r.text}")
        return False
    except Exception as e:
        logger.error(f"Telegram baglanti hatasi: {e}")
        return False


def send_signal(sig: dict) -> bool:
    """Sinyal bildirimi gonder."""
    now = datetime.now(timezone.utc)
    tarih = now.strftime("%Y-%m-%d")
    saat  = now.strftime("%H:%M UTC")

    msg = (
        f"🟢 <b>YENİ SİNYAL</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>Coin:</b> {sig['coin']}\n"
        f"<b>Tarih:</b> {tarih}\n"
        f"<b>Saat:</b> {saat}\n"
        f"<b>Fiyat:</b> {sig['price']}\n"
        f"<b>ATR:</b> %{sig['atr_pct']}\n"
        f"<b>EMA Gap:</b> %{sig['ema_gap_pct']}\n"
        f"<b>Stoch RSI:</b> {sig['stoch_rsi']}\n"
        f"<b>Trend Gücü:</b> {sig['trend_strength']}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 TP: %2  |  🛑 SL: %1"
    )
    return _send(msg)


def send_target_hit(coin: str, target_pct: float,
                    signal_price: float, elapsed_min: int) -> bool:
    """Hedef bildirimi gonder."""
    saat_str = f"{elapsed_min // 60}s {elapsed_min % 60}dk"
    emoji = "🎯" if target_pct >= 2 else "✅"
    msg = (
        f"{emoji} <b>HEDEF: +%{target_pct}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>Coin:</b> {coin}\n"
        f"<b>Giriş Fiyatı:</b> {signal_price}\n"
        f"<b>Süre:</b> {saat_str}\n"
        f"<b>Hedef:</b> +%{target_pct} ✓"
    )
    return _send(msg)


def send_daily_report(stats: dict) -> bool:
    """Gunluk ozet gonder."""
    msg = (
        f"📊 <b>GÜNLÜK RAPOR</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>Aktif Evren:</b> {stats.get('universe_count', 0)} coin\n"
        f"<b>Toplam Sinyal:</b> {stats.get('total_signals', 0)}\n"
        f"<b>%2 Hedef Oranı:</b> %{stats.get('tp2_rate', 0)}\n"
        f"<b>Win Rate:</b> %{stats.get('win_rate', 0)}\n"
        f"<b>Ort. %2 Süresi:</b> {stats.get('avg_time_2pct', 0)} dk\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"En İyi: {stats.get('best_coin', '—')}\n"
        f"En Kötü: {stats.get('worst_coin', '—')}"
    )
    return _send(msg)


def send_startup() -> bool:
    """Sistem basladiginda bildirim."""
    msg = (
        f"🚀 <b>SİSTEM BAŞLADI</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Kripto Sinyal Sistemi aktif.\n"
        f"Her 5 dakikada bir tarama yapılıyor.\n"
        f"Evren her gün 00:05 UTC'de güncelleniyor."
    )
    return _send(msg)
