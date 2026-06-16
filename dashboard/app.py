# dashboard/app.py
# FastAPI web paneli — 8 ekran

import logging
from datetime import datetime, timezone, timedelta
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import json, os

logger = logging.getLogger(__name__)

app = FastAPI(title="Kripto Sinyal Paneli")


def _get_db_data(days: int = 30):
    """Veritabanindan veri cek."""
    try:
        from database.db import get_signals_last_n_days, get_today_universe
        signals  = get_signals_last_n_days(days)
        universe = get_today_universe()
        return signals, universe
    except Exception as e:
        logger.error(f"DB hatasi: {e}")
        return [], []


def _calc_coin_stats(signals: list) -> dict:
    """Coin bazinda istatistik hesapla."""
    stats = {}
    for sig in signals:
        coin = sig["coin"]
        if coin not in stats:
            stats[coin] = {
                "total": 0, "tp1": 0, "tp2": 0, "tp3": 0,
                "times_2pct": [], "pnls": []
            }
        s = stats[coin]
        s["total"] += 1

        targets = sig.get("signal_targets", [])
        if targets:
            t = targets[0]
            if t.get("target_1pct"): s["tp1"] += 1
            if t.get("target_2pct"): s["tp2"] += 1
            if t.get("target_3pct"): s["tp3"] += 1
            if t.get("time_to_2pct"): s["times_2pct"].append(t["time_to_2pct"])
            pnl = 2.0 if t.get("target_2pct") else (-1.0 if not t.get("target_1pct") else 0.5)
            s["pnls"].append(pnl)

    result = {}
    for coin, s in stats.items():
        n = s["total"]
        result[coin] = {
            "total"     : n,
            "tp1_rate"  : round(s["tp1"]/n*100, 1) if n else 0,
            "tp2_rate"  : round(s["tp2"]/n*100, 1) if n else 0,
            "tp3_rate"  : round(s["tp3"]/n*100, 1) if n else 0,
            "avg_2pct"  : round(sum(s["times_2pct"])/len(s["times_2pct"]), 0) if s["times_2pct"] else None,
            "win_rate"  : round(s["tp2"]/n*100, 1) if n else 0,
        }
    return result


HTML_STYLE = """
<style>
  * { margin:0; padding:0; box-sizing:border-box; }
  body { font-family: -apple-system, sans-serif; background:#0f1117; color:#e2e8f0; }
  .header { background:#1a1f2e; padding:16px 24px; border-bottom:1px solid #2d3748;
            display:flex; align-items:center; gap:12px; }
  .header h1 { font-size:20px; font-weight:700; color:#63b3ed; }
  .nav { display:flex; gap:8px; padding:12px 24px; background:#1a1f2e; flex-wrap:wrap; }
  .nav a { padding:6px 14px; border-radius:6px; background:#2d3748; color:#a0aec0;
           text-decoration:none; font-size:13px; transition:all .2s; }
  .nav a:hover { background:#4a5568; color:#fff; }
  .content { padding:24px; max-width:1400px; margin:0 auto; }
  .grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); gap:16px; margin-bottom:24px; }
  .card { background:#1a1f2e; border:1px solid #2d3748; border-radius:10px; padding:20px; }
  .card .label { font-size:12px; color:#718096; margin-bottom:6px; }
  .card .value { font-size:28px; font-weight:700; color:#63b3ed; }
  .card .sub   { font-size:12px; color:#718096; margin-top:4px; }
  table { width:100%; border-collapse:collapse; font-size:13px; }
  th { background:#2d3748; padding:10px 12px; text-align:left; color:#a0aec0; font-weight:600; }
  td { padding:9px 12px; border-bottom:1px solid #2d3748; }
  tr:hover td { background:#1e2535; }
  .badge { padding:2px 8px; border-radius:12px; font-size:11px; font-weight:600; }
  .green  { color:#68d391; } .red { color:#fc8181; } .yellow { color:#f6e05e; }
  .bg-green { background:#1a3a2a; color:#68d391; }
  .bg-red   { background:#3a1a1a; color:#fc8181; }
  .bg-blue  { background:#1a2a3a; color:#63b3ed; }
  .section  { background:#1a1f2e; border:1px solid #2d3748; border-radius:10px;
              padding:20px; margin-bottom:20px; }
  .section h2 { font-size:16px; font-weight:600; margin-bottom:16px; color:#e2e8f0; }
  .pulse { width:8px; height:8px; border-radius:50%; background:#68d391;
           display:inline-block; animation:pulse 2s infinite; }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.3} }
</style>
"""

NAV = """
<div class="nav">
  <a href="/">🏠 Ana Sayfa</a>
  <a href="/universe">🌐 Aktif Evren</a>
  <a href="/signals">📡 Son Sinyaller</a>
  <a href="/best">🏆 En Başarılı</a>
  <a href="/speed">⚡ En Hızlı %2</a>
  <a href="/stats">📊 Coin İstatistik</a>
  <a href="/performance">📈 30 Gün Performans</a>
  <a href="/winrate">🎯 Win Rate Tablosu</a>
</div>
"""

def page(title: str, body: str) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return f"""<!DOCTYPE html><html><head>
<title>{title} — Kripto Sinyal</title>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
{HTML_STYLE}</head><body>
<div class="header">
  <span class="pulse"></span>
  <h1>🔍 Kripto Sinyal Sistemi</h1>
  <span style="margin-left:auto;font-size:12px;color:#718096">{now}</span>
</div>
{NAV}
<div class="content">{body}</div>
</body></html>"""


@app.get("/", response_class=HTMLResponse)
def home():
    signals, universe = _get_db_data(30)
    coin_stats = _calc_coin_stats(signals)

    total_sigs  = len(signals)
    tp2_count   = sum(1 for s in signals if s.get("signal_targets") and s["signal_targets"][0].get("target_2pct"))
    tp2_rate    = round(tp2_count/total_sigs*100, 1) if total_sigs else 0
    univ_count  = len(universe)
    times_2pct  = [s["signal_targets"][0]["time_to_2pct"] for s in signals
                   if s.get("signal_targets") and s["signal_targets"][0].get("time_to_2pct")]
    avg_2pct    = round(sum(times_2pct)/len(times_2pct), 0) if times_2pct else "—"

    body = f"""
    <div class="grid">
      <div class="card"><div class="label">Aktif Evren</div>
        <div class="value">{univ_count}</div><div class="sub">coin taranıyor</div></div>
      <div class="card"><div class="label">Son 30 Gün Sinyal</div>
        <div class="value">{total_sigs}</div><div class="sub">toplam sinyal</div></div>
      <div class="card"><div class="label">%2 Hedef Oranı</div>
        <div class="value green">%{tp2_rate}</div><div class="sub">win rate</div></div>
      <div class="card"><div class="label">Ort. %2 Süresi</div>
        <div class="value">{avg_2pct}</div><div class="sub">dakika</div></div>
    </div>

    <div class="section">
      <h2>📡 Son 10 Sinyal</h2>
      <table>
        <tr><th>Coin</th><th>Tarih</th><th>Fiyat</th><th>ATR%</th>
            <th>EMA Gap%</th><th>Trend</th><th>%1</th><th>%2</th><th>%3</th></tr>
        {"".join(f'''<tr>
          <td><b>{s["coin"]}</b></td>
          <td>{str(s["signal_time"])[:16]}</td>
          <td>{s["price"]}</td>
          <td>%{s.get("atr_pct","—")}</td>
          <td>%{s.get("ema_gap_pct","—")}</td>
          <td>{s.get("trend_strength","—")}</td>
          <td>{"<span class='badge bg-green'>✓</span>" if s.get("signal_targets") and s["signal_targets"][0].get("target_1pct") else "—"}</td>
          <td>{"<span class='badge bg-green'>✓</span>" if s.get("signal_targets") and s["signal_targets"][0].get("target_2pct") else "—"}</td>
          <td>{"<span class='badge bg-green'>✓</span>" if s.get("signal_targets") and s["signal_targets"][0].get("target_3pct") else "—"}</td>
        </tr>''' for s in signals[:10])}
      </table>
    </div>"""
    return page("Ana Sayfa", body)


@app.get("/universe", response_class=HTMLResponse)
def universe_page():
    _, universe = _get_db_data()
    rows = "".join(f"""<tr>
      <td><b>{u["coin"]}</b></td>
      <td>%{u.get("atr_pct","—")}</td>
      <td>%{u.get("ema_gap_pct","—")}</td>
      <td>${u.get("vol_usd",0):,.0f}</td>
    </tr>""" for u in universe)

    body = f"""<div class="section">
      <h2>🌐 Bugünkü Aktif Evren — {len(universe)} coin</h2>
      <table>
        <tr><th>Coin</th><th>ATR(14)</th><th>EMA20-50 Gap</th><th>24s Hacim</th></tr>
        {rows}
      </table>
    </div>"""
    return page("Aktif Evren", body)


@app.get("/signals", response_class=HTMLResponse)
def signals_page():
    signals, _ = _get_db_data(30)
    rows = "".join(f"""<tr>
      <td><b>{s["coin"]}</b></td>
      <td>{str(s["signal_time"])[:16]}</td>
      <td>{s["price"]}</td>
      <td>%{s.get("atr_pct","—")}</td>
      <td>%{s.get("ema_gap_pct","—")}</td>
      <td>{s.get("stoch_rsi","—")}</td>
      <td>{s.get("trend_strength","—")}</td>
      <td>{"✓" if s.get("signal_targets") and s["signal_targets"][0].get("target_1pct") else "—"}</td>
      <td>{"✓" if s.get("signal_targets") and s["signal_targets"][0].get("target_2pct") else "—"}</td>
      <td>{"✓" if s.get("signal_targets") and s["signal_targets"][0].get("target_3pct") else "—"}</td>
      <td>{s.get("signal_targets",[{}])[0].get("time_to_2pct","—") if s.get("signal_targets") else "—"} dk</td>
    </tr>""" for s in signals)

    body = f"""<div class="section">
      <h2>📡 Son 30 Gün Sinyaller — {len(signals)} adet</h2>
      <table>
        <tr><th>Coin</th><th>Tarih</th><th>Fiyat</th><th>ATR%</th>
            <th>EMAGap%</th><th>StochRSI</th><th>Trend</th>
            <th>+%1</th><th>+%2</th><th>+%3</th><th>%2 Süresi</th></tr>
        {rows}
      </table>
    </div>"""
    return page("Son Sinyaller", body)


@app.get("/best", response_class=HTMLResponse)
def best_page():
    signals, _ = _get_db_data(30)
    coin_stats = _calc_coin_stats(signals)
    sorted_coins = sorted(coin_stats.items(), key=lambda x: x[1]["tp2_rate"], reverse=True)

    rows = "".join(f"""<tr>
      <td><b>{coin}</b></td>
      <td>{s["total"]}</td>
      <td class="{'green' if s['tp2_rate']>=50 else 'yellow' if s['tp2_rate']>=30 else 'red'}">%{s["tp2_rate"]}</td>
      <td>%{s["tp1_rate"]}</td>
      <td>%{s["tp3_rate"]}</td>
      <td>{s["avg_2pct"] or "—"} dk</td>
    </tr>""" for coin,s in sorted_coins)

    body = f"""<div class="section">
      <h2>🏆 En Başarılı Coinler (Son 30 Gün)</h2>
      <table>
        <tr><th>Coin</th><th>Sinyal</th><th>%2 Oran</th>
            <th>%1 Oran</th><th>%3 Oran</th><th>Ort. %2 Süresi</th></tr>
        {rows}
      </table>
    </div>"""
    return page("En Başarılı", body)


@app.get("/speed", response_class=HTMLResponse)
def speed_page():
    signals, _ = _get_db_data(30)
    coin_stats = _calc_coin_stats(signals)
    with_time = [(c,s) for c,s in coin_stats.items() if s["avg_2pct"]]
    sorted_by_speed = sorted(with_time, key=lambda x: x[1]["avg_2pct"])

    rows = "".join(f"""<tr>
      <td><b>{coin}</b></td>
      <td>{s["avg_2pct"]} dk</td>
      <td>{round(s["avg_2pct"]/60,1)} saat</td>
      <td>%{s["tp2_rate"]}</td>
      <td>{s["total"]}</td>
    </tr>""" for coin,s in sorted_by_speed)

    body = f"""<div class="section">
      <h2>⚡ En Hızlı %2 Veren Coinler</h2>
      <table>
        <tr><th>Coin</th><th>Ort. Süre (dk)</th><th>Ort. Süre (saat)</th>
            <th>%2 Başarı</th><th>Sinyal Sayısı</th></tr>
        {rows}
      </table>
    </div>"""
    return page("En Hızlı %2", body)


@app.get("/stats", response_class=HTMLResponse)
def stats_page():
    signals, _ = _get_db_data(30)
    coin_stats = _calc_coin_stats(signals)

    rows = "".join(f"""<tr>
      <td><b>{coin}</b></td>
      <td>{s["total"]}</td>
      <td>%{s["tp1_rate"]}</td>
      <td>%{s["tp2_rate"]}</td>
      <td>%{s["tp3_rate"]}</td>
      <td>{s["avg_2pct"] or "—"} dk</td>
      <td class="{'green' if s['win_rate']>=50 else 'yellow' if s['win_rate']>=30 else 'red'}">%{s["win_rate"]}</td>
    </tr>""" for coin,s in sorted(coin_stats.items(), key=lambda x: x[1]["total"], reverse=True))

    body = f"""<div class="section">
      <h2>📊 Coin Bazında İstatistikler</h2>
      <table>
        <tr><th>Coin</th><th>Toplam Sinyal</th><th>%1 Oran</th>
            <th>%2 Oran</th><th>%3 Oran</th><th>Ort. %2 Süresi</th><th>Win Rate</th></tr>
        {rows}
      </table>
    </div>"""
    return page("Coin İstatistik", body)


@app.get("/performance", response_class=HTMLResponse)
def performance_page():
    signals, _ = _get_db_data(30)

    # Gunluk gruplama
    from collections import defaultdict
    daily = defaultdict(lambda: {"total":0,"tp2":0})
    for s in signals:
        day = str(s["signal_time"])[:10]
        daily[day]["total"] += 1
        if s.get("signal_targets") and s["signal_targets"][0].get("target_2pct"):
            daily[day]["tp2"] += 1

    rows = "".join(f"""<tr>
      <td>{day}</td>
      <td>{v["total"]}</td>
      <td>{v["tp2"]}</td>
      <td class="{'green' if v['total']>0 and v['tp2']/v['total']>=0.5 else 'yellow'}">
        %{round(v["tp2"]/v["total"]*100,1) if v["total"] else 0}</td>
    </tr>""" for day,v in sorted(daily.items(), reverse=True))

    body = f"""<div class="section">
      <h2>📈 Son 30 Gün Günlük Performans</h2>
      <table>
        <tr><th>Tarih</th><th>Sinyal</th><th>%2 Hedef</th><th>Günlük Win Rate</th></tr>
        {rows}
      </table>
    </div>"""
    return page("30 Gün Performans", body)


@app.get("/winrate", response_class=HTMLResponse)
def winrate_page():
    signals, _ = _get_db_data(30)
    coin_stats = _calc_coin_stats(signals)
    sorted_wr  = sorted(coin_stats.items(), key=lambda x: x[1]["win_rate"], reverse=True)

    rows = "".join(f"""<tr>
      <td><b>{coin}</b></td>
      <td>{s["total"]}</td>
      <td style="background:{'#1a3a2a' if s['win_rate']>=50 else '#2a2a1a' if s['win_rate']>=30 else '#3a1a1a'}">
        %{s["win_rate"]}</td>
      <td>%{s["tp1_rate"]}</td>
      <td>%{s["tp3_rate"]}</td>
    </tr>""" for coin,s in sorted_wr)

    body = f"""<div class="section">
      <h2>🎯 Win Rate Tablosu (Son 30 Gün)</h2>
      <table>
        <tr><th>Coin</th><th>Sinyal</th><th>Win Rate (%2)</th>
            <th>%1 Oran</th><th>%3 Oran</th></tr>
        {rows}
      </table>
    </div>"""
    return page("Win Rate", body)


@app.get("/health")
def health():
    return {"status": "ok", "time": datetime.now(timezone.utc).isoformat()}
