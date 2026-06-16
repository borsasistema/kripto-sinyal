# database/db.py
# Supabase baglantisi ve tum veritabani islemleri

import logging
from datetime import datetime, timezone
from supabase import create_client, Client
from config.settings import SUPABASE_URL, SUPABASE_KEY

logger = logging.getLogger(__name__)

_client: Client = None

def get_client() -> Client:
    global _client
    if _client is None:
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _client


def init_tables():
    """
    Supabase'de tablolari olusturur.
    Bu fonksiyonu ilk kurulumda bir kez calistir.
    SQL Supabase Dashboard > SQL Editor'dan da calistirabilirsin.
    """
    sql = """
    -- Gunluk aktif evren tablosu
    CREATE TABLE IF NOT EXISTS universe (
        id          BIGSERIAL PRIMARY KEY,
        date        DATE NOT NULL,
        coin        TEXT NOT NULL,
        atr_pct     NUMERIC(8,4),
        ema_gap_pct NUMERIC(8,4),
        vol_usd     NUMERIC(20,2),
        created_at  TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE(date, coin)
    );

    -- Sinyaller tablosu
    CREATE TABLE IF NOT EXISTS signals (
        id           BIGSERIAL PRIMARY KEY,
        coin         TEXT NOT NULL,
        signal_time  TIMESTAMPTZ NOT NULL,
        price        NUMERIC(20,8) NOT NULL,
        atr_pct      NUMERIC(8,4),
        ema_gap_pct  NUMERIC(8,4),
        stoch_rsi    NUMERIC(8,4),
        trend_strength TEXT,
        created_at   TIMESTAMPTZ DEFAULT NOW()
    );

    -- Hedef takip tablosu
    CREATE TABLE IF NOT EXISTS signal_targets (
        id            BIGSERIAL PRIMARY KEY,
        signal_id     BIGINT REFERENCES signals(id),
        coin          TEXT NOT NULL,
        signal_price  NUMERIC(20,8),
        signal_time   TIMESTAMPTZ,
        target_1pct   BOOLEAN DEFAULT FALSE,
        target_2pct   BOOLEAN DEFAULT FALSE,
        target_3pct   BOOLEAN DEFAULT FALSE,
        time_to_1pct  INTEGER,
        time_to_2pct  INTEGER,
        time_to_3pct  INTEGER,
        first_target  TEXT,
        max_gain_pct  NUMERIC(8,4),
        max_loss_pct  NUMERIC(8,4),
        is_closed     BOOLEAN DEFAULT FALSE,
        closed_at     TIMESTAMPTZ,
        created_at    TIMESTAMPTZ DEFAULT NOW()
    );

    -- Indexler
    CREATE INDEX IF NOT EXISTS idx_signals_coin ON signals(coin);
    CREATE INDEX IF NOT EXISTS idx_signals_time ON signals(signal_time DESC);
    CREATE INDEX IF NOT EXISTS idx_targets_signal ON signal_targets(signal_id);
    CREATE INDEX IF NOT EXISTS idx_targets_closed ON signal_targets(is_closed);
    """
    logger.info("Tablolar olusturuluyor... (Supabase SQL Editor'dan calistirin)")
    print("="*60)
    print("Asagidaki SQL'i Supabase Dashboard > SQL Editor'a yapistirin:")
    print("="*60)
    print(sql)
    print("="*60)


def save_universe(date_str: str, coins: list):
    """Gunluk evren listesini kaydet."""
    client = get_client()
    rows = [
        {
            "date"       : date_str,
            "coin"       : c["symbol"],
            "atr_pct"    : c["atr"],
            "ema_gap_pct": c["gap"],
            "vol_usd"    : c["vol"],
        }
        for c in coins
    ]
    try:
        client.table("universe").upsert(rows, on_conflict="date,coin").execute()
        logger.info(f"Evren kaydedildi: {len(rows)} coin — {date_str}")
    except Exception as e:
        logger.error(f"Evren kayit hatasi: {e}")


def save_signal(coin: str, signal_time: datetime, price: float,
                atr_pct: float, ema_gap_pct: float,
                stoch_rsi: float, trend_strength: str) -> int | None:
    """Sinyal kaydet, id dondur."""
    client = get_client()
    try:
        res = client.table("signals").insert({
            "coin"          : coin,
            "signal_time"   : signal_time.isoformat(),
            "price"         : price,
            "atr_pct"       : round(atr_pct, 4),
            "ema_gap_pct"   : round(ema_gap_pct, 4),
            "stoch_rsi"     : round(stoch_rsi, 4) if stoch_rsi else None,
            "trend_strength": trend_strength,
        }).execute()
        signal_id = res.data[0]["id"]
        logger.info(f"Sinyal kaydedildi: {coin} id={signal_id}")

        # Hedef takip satiri olustur
        client.table("signal_targets").insert({
            "signal_id"   : signal_id,
            "coin"        : coin,
            "signal_price": price,
            "signal_time" : signal_time.isoformat(),
        }).execute()

        return signal_id
    except Exception as e:
        logger.error(f"Sinyal kayit hatasi {coin}: {e}")
        return None


def get_open_targets():
    """Kapanmamis hedef takiplerini getir."""
    client = get_client()
    try:
        res = client.table("signal_targets")\
            .select("*")\
            .eq("is_closed", False)\
            .execute()
        return res.data
    except Exception as e:
        logger.error(f"Acik hedef sorgu hatasi: {e}")
        return []


def update_target(target_id: int, updates: dict):
    """Hedef takip satirini guncelle."""
    client = get_client()
    try:
        client.table("signal_targets")\
            .update(updates)\
            .eq("id", target_id)\
            .execute()
    except Exception as e:
        logger.error(f"Hedef guncelleme hatasi id={target_id}: {e}")


def get_signals_last_n_days(days: int = 30):
    """Son N gundeki sinyalleri getir."""
    client = get_client()
    from datetime import timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    try:
        res = client.table("signals")\
            .select("*, signal_targets(*)")\
            .gte("signal_time", cutoff)\
            .order("signal_time", desc=True)\
            .execute()
        return res.data
    except Exception as e:
        logger.error(f"Sinyal sorgu hatasi: {e}")
        return []


def get_today_universe():
    """Bugunku aktif evreni getir."""
    client = get_client()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        res = client.table("universe")\
            .select("*")\
            .eq("date", today)\
            .execute()
        return res.data
    except Exception as e:
        logger.error(f"Evren sorgu hatasi: {e}")
        return []


def get_coin_stats(coin: str, days: int = 30):
    """Coin bazinda istatistik hesapla."""
    client = get_client()
    from datetime import timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    try:
        res = client.table("signals")\
            .select("*, signal_targets(*)")\
            .eq("coin", coin)\
            .gte("signal_time", cutoff)\
            .execute()
        return res.data
    except Exception as e:
        logger.error(f"Coin stat hatasi {coin}: {e}")
        return []
