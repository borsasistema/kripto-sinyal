# config/settings.py
import os
from dotenv import load_dotenv

load_dotenv()

# Telegram
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

# Strateji — hic degistirilmedi
STRATEGY = {
    "ema_trend"    : (20, 50, 100),
    "ema_entry"    : (10, 20),
    "pullback_pct" : 0.02,
    "tp_pct"       : 0.02,
    "sl_pct"       : 0.01,
}

# Evren filtreleri
UNIVERSE_FILTER = {
    "atr_min"     : 1.3,
    "ema_gap_min" : 1.0,
    "vol_min_usd" : 5_000_000,
}

# Stablecoinler
STABLES = {
    "USDT","USDC","BUSD","DAI","TUSD","FDUSD",
    "USDP","USDS","FRAX","LUSD","GUSD","SUSD",
    "CRVUSD","PYUSD","EURT","EURS","USDE","USD1",
}

# Hedef seviyeleri (takip icin)
TARGETS = [1.0, 2.0, 3.0]  # %

# Zamanlama
UNIVERSE_CRON  = "0 5 * * *"   # Her gun 00:05 UTC
SCANNER_EVERY  = 300            # 5 dakikada bir (saniye)
TRACKER_EVERY  = 60             # 1 dakikada bir (saniye)
