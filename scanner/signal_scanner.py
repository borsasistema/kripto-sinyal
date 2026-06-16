# scanner/signal_scanner.py
# Her 5 dakikada bir calisir.
# Aktif evreni tarar, sinyalleri uretir.

import logging
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from config.settings import STRATEGY

logger = logging.getLogger(__name__)

BINANCE_URL = "https://api.binance.com/api/v3"

# Son sinyal zamanlari — ayni coinden spam onlemek icin
_last_signal: dict = {}
SIGNAL_COOLDOWN = 3600  # 1 saat (saniye)


def _ema(s: pd.Series, p: int) -> pd.Series:
    return s.ewm(span=p, adjust=False).mean()


def _get_klines(symbol: str, interval: str, limit: int = 150) -> pd.DataFrame:
    try:
        r = requests.get(f"{BINANCE_URL}/klines", params={
            "symbol": symbol, "interval": interval, "limit": limit
        }, timeout=10)
        data = r.json()
        if not isinstance(data, list) or len(data) < 50:
            return pd.DataFrame()
        cols = ["open_time","open","high","low","close","volume",
                "close_time","quote_vol","trades","tb","tq","ign"]
        df = pd.DataFrame(data, columns=cols)
        for c in ["open","high","low","close","volume","quote_vol"]:
            df[c] = df[c].astype(float)
        df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
        return df.iloc[:-1]  # son acik mumu at — look-ahead bias yok
    except Exception as e:
        logger.debug(f"Kline hatasi {symbol}: {e}")
        return pd.DataFrame()


def _calc_atr(df: pd.DataFrame, period: int = 14) -> float:
    h, l, pc = df["high"], df["low"], df["close"].shift(1)
    tr = pd.concat([h-l, (h-pc).abs(), (l-pc).abs()], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()
    return float((atr / df["close"] * 100).iloc[-1])


def _calc_ema_gap(df: pd.DataFrame) -> float:
    e20 = _ema(df["close"], 20)
    e50 = _ema(df["close"], 50)
    return float(abs(e20.iloc[-1] - e50.iloc[-1]) / e50.iloc[-1] * 100)


def _calc_stoch_rsi(df: pd.DataFrame, period: int = 14,
                    smooth_k: int = 3, smooth_d: int = 3) -> float:
    """Stochastic RSI hesapla."""
    delta = df["close"].diff()
    gain  = delta.clip(lower=0).rolling(period).mean()
    loss  = (-delta.clip(upper=0)).rolling(period).mean()
    rs    = gain / loss.replace(0, np.nan)
    rsi   = 100 - (100 / (1 + rs))

    rsi_min = rsi.rolling(period).min()
    rsi_max = rsi.rolling(period).max()
    stoch_rsi = (rsi - rsi_min) / (rsi_max - rsi_min).replace(0, np.nan) * 100
    k = stoch_rsi.rolling(smooth_k).mean()
    return float(k.iloc[-1]) if not pd.isna(k.iloc[-1]) else 50.0


def _calc_trend_strength(df1h: pd.DataFrame) -> str:
    """Trend gucunu hesapla."""
    e20  = _ema(df1h["close"], 20).iloc[-1]
    e50  = _ema(df1h["close"], 50).iloc[-1]
    e100 = _ema(df1h["close"], 100).iloc[-1]
    close = df1h["close"].iloc[-1]

    if e20 > e50 > e100 and close > e20:
        gap = (e20 - e50) / e50 * 100
        if gap > 3:   return "Cok Guclu"
        elif gap > 1: return "Guclu"
        else:         return "Orta"
    return "Zayif"


def check_signal(symbol: str) -> dict | None:
    """
    Tek coin icin sinyal kontrolu.
    Sadece kapanmis mumlar kullanilir.
    Dondurur: sinyal dict veya None
    """
    # Cooldown kontrolu
    now_ts = datetime.now(timezone.utc).timestamp()
    if symbol in _last_signal:
        if now_ts - _last_signal[symbol] < SIGNAL_COOLDOWN:
            return None

    # Veri cek
    df1h  = _get_klines(symbol, "1h",  150)
    df15m = _get_klines(symbol, "15m", 150)

    if df1h.empty or df15m.empty:
        return None

    f, m, s = STRATEGY["ema_trend"]

    # ── 1. Trend Filtresi (1H) ────────────────────────────────────────
    e20_1h  = _ema(df1h["close"], f)
    e50_1h  = _ema(df1h["close"], m)
    e100_1h = _ema(df1h["close"], s)

    trend_ok = (
        e20_1h.iloc[-1]  > e50_1h.iloc[-1] > e100_1h.iloc[-1] and
        df1h["close"].iloc[-1] > e20_1h.iloc[-1]
    )
    if not trend_ok:
        return None

    # ── 2. Giris Filtresi (15M) ──────────────────────────────────────
    ef, es = STRATEGY["ema_entry"]
    e10_15m = _ema(df15m["close"], ef)
    e20_15m = _ema(df15m["close"], es)

    # EMA10 EMA20'yi yukari kesti mi? (son kapanmis mumda)
    cross_now  = e10_15m.iloc[-1] > e20_15m.iloc[-1]
    cross_prev = e10_15m.iloc[-2] <= e20_15m.iloc[-2]
    crossover  = cross_now and cross_prev

    if not crossover:
        return None

    # ── 3. Stoch RSI < 30 (asiri satim) ─────────────────────────────
    stoch = _calc_stoch_rsi(df15m)
    if stoch >= 30:
        return None

    # ── Sinyal onaylandi ─────────────────────────────────────────────
    price        = df15m["close"].iloc[-1]
    atr_pct      = _calc_atr(df1h)
    ema_gap_pct  = _calc_ema_gap(df1h)
    trend_str    = _calc_trend_strength(df1h)
    signal_time  = datetime.now(timezone.utc)

    # Cooldown guncelle
    _last_signal[symbol] = now_ts

    return {
        "coin"          : symbol,
        "signal_time"   : signal_time,
        "price"         : round(price, 8),
        "atr_pct"       : round(atr_pct, 3),
        "ema_gap_pct"   : round(ema_gap_pct, 3),
        "stoch_rsi"     : round(stoch, 2),
        "trend_strength": trend_str,
    }


def run_scan() -> list:
    """
    Aktif evreni tara, sinyalleri dondur.
    """
    from scanner.universe import load_latest_universe
    from database.db import save_signal
    from telegram.notifier import send_signal

    universe = load_latest_universe()
    if not universe:
        logger.warning("Aktif evren bos, tarama atlandi.")
        return []

    logger.info(f"Tarama basladi: {len(universe)} coin")
    signals_found = []

    for symbol in universe:
        try:
            sig = check_signal(symbol)
            if sig:
                logger.info(f"SİNYAL: {symbol} @ {sig['price']}")

                # Veritabanina kaydet
                signal_id = save_signal(
                    coin           = sig["coin"],
                    signal_time    = sig["signal_time"],
                    price          = sig["price"],
                    atr_pct        = sig["atr_pct"],
                    ema_gap_pct    = sig["ema_gap_pct"],
                    stoch_rsi      = sig["stoch_rsi"],
                    trend_strength = sig["trend_strength"],
                )
                sig["signal_id"] = signal_id

                # Telegram bildirimi
                send_signal(sig)
                signals_found.append(sig)

        except Exception as e:
            logger.error(f"Tarama hatasi {symbol}: {e}")

    logger.info(f"Tarama tamamlandi: {len(signals_found)} sinyal bulundu")
    return signals_found
