# scanner/universe.py
# Her gun 00:05 UTC'de calisir.
# Tum Binance USDT paritelerini tarar, filtreleri uygular.

import logging
import requests
import pandas as pd
import numpy as np
import json, os
from datetime import datetime, timezone
from config.settings import UNIVERSE_FILTER, STABLES

logger = logging.getLogger(__name__)

BINANCE_URL = "https://api.binance.com/api/v3"


def _ema(s: pd.Series, p: int) -> pd.Series:
    return s.ewm(span=p, adjust=False).mean()


def _get_klines(symbol: str, interval: str, limit: int = 200) -> pd.DataFrame:
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
        df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
        return df.iloc[:-1]  # son acik mumu at
    except Exception as e:
        logger.debug(f"Kline hatasi {symbol}: {e}")
        return pd.DataFrame()


def _calc_atr(df: pd.DataFrame, period: int = 14) -> float:
    h, l, pc = df["high"], df["low"], df["close"].shift(1)
    tr = pd.concat([h-l, (h-pc).abs(), (l-pc).abs()], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()
    return float((atr / df["close"] * 100).mean())


def _calc_ema_gap(df: pd.DataFrame) -> float:
    e20 = _ema(df["close"], 20)
    e50 = _ema(df["close"], 50)
    return float(((e20 - e50).abs() / e50 * 100).mean())


def build_universe() -> list:
    """
    1. Tum Binance USDT paritelerini al
    2. Hacim filtresi uygula
    3. ATR ve EMA Gap hesapla
    4. Filtreyi gecenleri dondur
    """
    logger.info("Evren olusturma basladi...")

    # Tum tickerlari al
    try:
        r = requests.get(f"{BINANCE_URL}/ticker/24hr", timeout=15)
        tickers = r.json()
    except Exception as e:
        logger.error(f"Ticker hatasi: {e}")
        return []

    candidates = []
    for t in tickers:
        sym = t["symbol"]
        if not sym.endswith("USDT"):
            continue
        base = sym.replace("USDT", "")
        if base in STABLES:
            continue
        try:
            vol = float(t["quoteVolume"])
            if vol < UNIVERSE_FILTER["vol_min_usd"]:
                continue
            candidates.append({"symbol": sym, "vol": vol})
        except:
            continue

    candidates.sort(key=lambda x: x["vol"], reverse=True)
    logger.info(f"Hacim filtresinden gecen: {len(candidates)} coin")

    passed = []
    for c in candidates:
        sym = c["symbol"]
        df1h = _get_klines(sym, "1h", 200)
        if df1h.empty or len(df1h) < 100:
            continue

        atr = _calc_atr(df1h)
        gap = _calc_ema_gap(df1h)

        if atr >= UNIVERSE_FILTER["atr_min"] and gap >= UNIVERSE_FILTER["ema_gap_min"]:
            passed.append({
                "symbol": sym,
                "atr"   : round(atr, 3),
                "gap"   : round(gap, 3),
                "vol"   : round(c["vol"], 0),
            })
            logger.debug(f"GECTI: {sym} ATR:{atr:.2f}% Gap:{gap:.2f}%")

    logger.info(f"Evren filtresi sonucu: {len(passed)} coin aktif")
    return passed


def save_universe_files(coins: list):
    """CSV ve JSON olarak kaydet."""
    os.makedirs("data", exist_ok=True)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # JSON
    json_path = f"data/universe_{today}.json"
    with open(json_path, "w") as f:
        json.dump({"date": today, "coins": coins}, f, indent=2)

    # CSV
    csv_path = f"data/universe_{today}.csv"
    pd.DataFrame(coins).to_csv(csv_path, index=False)

    # Guncel evren (sabit isim)
    with open("data/universe_latest.json", "w") as f:
        json.dump({"date": today, "coins": coins}, f, indent=2)

    logger.info(f"Evren dosyalari kaydedildi: {json_path}, {csv_path}")
    return coins


def load_latest_universe() -> list:
    """En guncel evren listesini yukle."""
    path = "data/universe_latest.json"
    if not os.path.exists(path):
        logger.warning("Evren dosyasi bulunamadi, yeniden olusturuluyor...")
        coins = build_universe()
        save_universe_files(coins)
        return coins
    with open(path) as f:
        data = json.load(f)
    return [c["symbol"] for c in data.get("coins", [])]


def run_universe_job():
    """Zamanlanmis gorev: evren olustur ve kaydet."""
    from database.db import save_universe
    logger.info("=== EVREN GUNCELLEME BASLADI ===")
    coins = build_universe()
    if coins:
        save_universe_files(coins)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        save_universe(today, coins)
        logger.info(f"=== EVREN TAMAMLANDI: {len(coins)} coin ===")
    else:
        logger.error("Evren bos! Binance API sorunu olabilir.")
    return coins
