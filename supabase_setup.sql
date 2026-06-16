-- ============================================================
-- Kripto Sinyal Sistemi — Supabase Veritabani Kurulumu
-- Bu dosyayi Supabase Dashboard > SQL Editor'a yapistirin
-- ve "Run" butonuna basin.
-- ============================================================

-- 1. Gunluk aktif evren tablosu
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

-- 2. Sinyaller tablosu
CREATE TABLE IF NOT EXISTS signals (
    id              BIGSERIAL PRIMARY KEY,
    coin            TEXT NOT NULL,
    signal_time     TIMESTAMPTZ NOT NULL,
    price           NUMERIC(20,8) NOT NULL,
    atr_pct         NUMERIC(8,4),
    ema_gap_pct     NUMERIC(8,4),
    stoch_rsi       NUMERIC(8,4),
    trend_strength  TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Hedef takip tablosu
CREATE TABLE IF NOT EXISTS signal_targets (
    id            BIGSERIAL PRIMARY KEY,
    signal_id     BIGINT REFERENCES signals(id) ON DELETE CASCADE,
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

-- 4. Indexler (performans icin)
CREATE INDEX IF NOT EXISTS idx_signals_coin   ON signals(coin);
CREATE INDEX IF NOT EXISTS idx_signals_time   ON signals(signal_time DESC);
CREATE INDEX IF NOT EXISTS idx_universe_date  ON universe(date DESC);
CREATE INDEX IF NOT EXISTS idx_targets_signal ON signal_targets(signal_id);
CREATE INDEX IF NOT EXISTS idx_targets_closed ON signal_targets(is_closed);
CREATE INDEX IF NOT EXISTS idx_targets_coin   ON signal_targets(coin);

-- 5. RLS (Row Level Security) — herkese okuma izni
ALTER TABLE signals        ENABLE ROW LEVEL SECURITY;
ALTER TABLE signal_targets ENABLE ROW LEVEL SECURITY;
ALTER TABLE universe       ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Herkes okuyabilir — signals"
    ON signals FOR SELECT USING (true);

CREATE POLICY "Herkes okuyabilir — targets"
    ON signal_targets FOR SELECT USING (true);

CREATE POLICY "Herkes okuyabilir — universe"
    ON universe FOR SELECT USING (true);

CREATE POLICY "Servis yazabilir — signals"
    ON signals FOR INSERT WITH CHECK (true);

CREATE POLICY "Servis yazabilir — targets"
    ON signal_targets FOR ALL USING (true);

CREATE POLICY "Servis yazabilir — universe"
    ON universe FOR INSERT WITH CHECK (true);

-- Kurulum tamamlandi!
SELECT 'Tablolar basariyla olusturuldu!' as durum;
