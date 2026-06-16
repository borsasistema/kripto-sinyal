# signals/tracker.py
# Her 1 dakikada bir calisir.
# Acik sinyallerin hedeflere ulasip ulasmadığını kontrol eder.

import logging
import requests
import pandas as pd
from datetime import datetime, timezone
from config.settings import TARGETS

logger = logging.getLogger(__name__)

BINANCE_URL = "https://api.binance.com/api/v3"


def _get_current_price(symbol: str) -> float | None:
    try:
        r = requests.get(f"{BINANCE_URL}/ticker/price",
                         params={"symbol": symbol}, timeout=5)
        return float(r.json()["price"])
    except:
        return None


def _get_high_low_since(symbol: str, since_minutes: int) -> tuple:
    """Sinyal zamanindan bu yana max yuksek ve min dusuk fiyat."""
    try:
        limit = max(1, since_minutes // 5 + 2)
        r = requests.get(f"{BINANCE_URL}/klines", params={
            "symbol": symbol, "interval": "5m", "limit": min(limit, 200)
        }, timeout=10)
        data = r.json()
        if not isinstance(data, list) or not data:
            return None, None
        highs = [float(c[2]) for c in data]
        lows  = [float(c[3]) for c in data]
        return max(highs), min(lows)
    except:
        return None, None


def track_targets():
    """
    Acik sinyalleri kontrol et, hedef guncellemelerini yap.
    """
    from database.db import get_open_targets, update_target

    open_targets = get_open_targets()
    if not open_targets:
        return

    logger.info(f"Hedef takip: {len(open_targets)} acik sinyal")
    now = datetime.now(timezone.utc)

    for target in open_targets:
        try:
            coin         = target["coin"]
            signal_price = float(target["signal_price"])
            signal_time  = pd.Timestamp(target["signal_time"])

            # Sinyal zamanindan gecen sure (dakika)
            elapsed_min = int((now.timestamp() - signal_time.timestamp()) / 60)

            # Max 24 saat bekle
            if elapsed_min > 1440:
                update_target(target["id"], {
                    "is_closed": True,
                    "closed_at": now.isoformat(),
                })
                continue

            # Guncel fiyat
            current = _get_current_price(coin)
            if not current:
                continue

            # Sinyal zamanindan bu yana high/low
            high, low = _get_high_low_since(coin, elapsed_min)
            if not high or not low:
                high = current; low = current

            # Kazanc/kayip hesapla
            gain_pct = (high - signal_price) / signal_price * 100
            loss_pct = (low  - signal_price) / signal_price * 100

            updates = {
                "max_gain_pct": round(gain_pct, 4),
                "max_loss_pct": round(loss_pct, 4),
            }

            # Hedef kontrolleri
            first_target = target.get("first_target")

            for tgt in TARGETS:
                tgt_price = signal_price * (1 + tgt / 100)
                col_hit   = f"target_{int(tgt)}pct" if tgt == int(tgt) else f"target_{tgt}pct"
                col_time  = f"time_to_{int(tgt)}pct" if tgt == int(tgt) else f"time_to_{tgt}pct"

                # Duzeltilmis kolon isimleri
                col_hit  = {1.0:"target_1pct", 2.0:"target_2pct", 3.0:"target_3pct"}.get(tgt)
                col_time = {1.0:"time_to_1pct",2.0:"time_to_2pct",3.0:"time_to_3pct"}.get(tgt)

                if not col_hit:
                    continue

                if not target.get(col_hit) and high >= tgt_price:
                    updates[col_hit]  = True
                    updates[col_time] = elapsed_min
                    if not first_target:
                        first_target = f"+{tgt}%"
                        updates["first_target"] = first_target
                    logger.info(f"{coin} +{tgt}% hedefine ulasti! {elapsed_min} dk")

            # %2 hedefe ulasildiysa veya %1 stop'a geldiyse kapat
            sl_price = signal_price * (1 - 0.01)
            if target.get("target_2pct") or low <= sl_price:
                updates["is_closed"] = True
                updates["closed_at"] = now.isoformat()

            update_target(target["id"], updates)

        except Exception as e:
            logger.error(f"Hedef takip hatasi {target.get('coin')}: {e}")
