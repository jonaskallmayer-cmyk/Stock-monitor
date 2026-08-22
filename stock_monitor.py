"""
Aktie-overvågningsscript
=========================
Overvåger en liste af aktier og genererer et HTML-dashboard med alerts
baseret på en kombination af:
  - Dagens prisbevægelse (%)
  - Volumen ift. 20-dages gennemsnit
  - RSI (Relative Strength Index)

Kør scriptet manuelt, eller sæt det op til at køre automatisk (se bund af filen
for instruktioner til cron / Task Scheduler / GitHub Actions).

Installation:
    pip install yfinance pandas
"""

import yfinance as yf
import pandas as pd
from datetime import datetime
import webbrowser
import os

# -----------------------------
# KONFIGURATION - ret her
# -----------------------------

TICKERS = [
    "TSLA",   # Tesla
    "NVDA",   # Nvidia
    "AMD",    # AMD
    "PLTR",   # Palantir
    "COIN",   # Coinbase
    "MSTR",   # MicroStrategy
    "SMCI",   # Super Micro Computer
]

# Tærskler for alerts
PRICE_CHANGE_THRESHOLD = 3.0     # % ændring på en dag der udløser alert
VOLUME_SPIKE_MULTIPLIER = 1.5    # volumen skal være X gange 20-dages snit
RSI_OVERBOUGHT = 70              # RSI over dette = overkøbt
RSI_OVERSOLD = 30                # RSI under dette = oversolgt

OUTPUT_DIR = "public"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "index.html")

# -----------------------------
# BEREGNINGER
# -----------------------------

def calculate_rsi(prices, period=14):
    """Beregner RSI (Relative Strength Index) for en prisserie."""
    delta = prices.diff()
    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss = -delta.where(delta < 0, 0).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def analyze_ticker(ticker):
    """Henter data og beregner signaler for én aktie."""
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="3mo")

        if hist.empty or len(hist) < 20:
            return {"ticker": ticker, "error": "Ikke nok data"}

        latest = hist.iloc[-1]
        prev = hist.iloc[-2]

        price = latest["Close"]
        price_change_pct = ((price - prev["Close"]) / prev["Close"]) * 100

        avg_volume_20d = hist["Volume"].iloc[-21:-1].mean()
        volume_ratio = latest["Volume"] / avg_volume_20d if avg_volume_20d > 0 else 0

        rsi_series = calculate_rsi(hist["Close"])
        rsi = rsi_series.iloc[-1]

        # --- Alert-logik: kombination af signaler ---
        signals = []
        if abs(price_change_pct) >= PRICE_CHANGE_THRESHOLD:
            direction = "op" if price_change_pct > 0 else "ned"
            signals.append(f"Pris {direction} {abs(price_change_pct):.1f}%")

        if volume_ratio >= VOLUME_SPIKE_MULTIPLIER:
            signals.append(f"Volumen {volume_ratio:.1f}x normalt")

        if rsi >= RSI_OVERBOUGHT:
            signals.append(f"RSI overkøbt ({rsi:.0f})")
        elif rsi <= RSI_OVERSOLD:
            signals.append(f"RSI oversolgt ({rsi:.0f})")

        # Alert udløses hvis mindst 2 signaler rammer samtidig
        alert_level = "high" if len(signals) >= 2 else ("medium" if len(signals) == 1 else "none")

        return {
            "ticker": ticker,
            "price": price,
            "price_change_pct": price_change_pct,
            "volume_ratio": volume_ratio,
            "rsi": rsi,
            "signals": signals,
            "alert_level": alert_level,
            "error": None,
        }

    except Exception as e:
        return {"ticker": ticker, "error": str(e)}


# -----------------------------
# DASHBOARD (HTML)
# -----------------------------

def generate_html(results):
    timestamp = datetime.now().strftime("%d-%m-%Y %H:%M:%S")

    rows_html = ""
    # Sorter så høj-alerts vises øverst
    order = {"high": 0, "medium": 1, "none": 2}
    results_sorted = sorted(results, key=lambda r: order.get(r.get("alert_level", "none"), 3))

    for r in results_sorted:
        if r.get("error"):
            rows_html += f"""
            <tr class="error-row">
                <td>{r['ticker']}</td>
                <td colspan="5">Fejl: {r['error']}</td>
            </tr>"""
            continue

        alert_class = {
            "high": "alert-high",
            "medium": "alert-medium",
            "none": "alert-none",
        }[r["alert_level"]]

        change_class = "positive" if r["price_change_pct"] >= 0 else "negative"
        signals_text = ", ".join(r["signals"]) if r["signals"] else "—"

        rows_html += f"""
        <tr class="{alert_class}">
            <td class="ticker">{r['ticker']}</td>
            <td>${r['price']:.2f}</td>
            <td class="{change_class}">{r['price_change_pct']:+.2f}%</td>
            <td>{r['volume_ratio']:.1f}x</td>
            <td>{r['rsi']:.0f}</td>
            <td class="signals">{signals_text}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="da">
<head>
<meta charset="UTF-8">
<title>Aktie-overvågning</title>
<style>
    body {{
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        background: #0f1117;
        color: #e5e7eb;
        max-width: 900px;
        margin: 40px auto;
        padding: 0 20px;
    }}
    h1 {{ font-size: 22px; margin-bottom: 4px; }}
    .timestamp {{ color: #9ca3af; font-size: 13px; margin-bottom: 24px; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th {{
        text-align: left;
        padding: 10px 12px;
        border-bottom: 2px solid #374151;
        color: #9ca3af;
        font-size: 12px;
        text-transform: uppercase;
    }}
    td {{ padding: 12px; border-bottom: 1px solid #1f2937; font-size: 14px; }}
    .ticker {{ font-weight: 600; }}
    .positive {{ color: #34d399; }}
    .negative {{ color: #f87171; }}
    .signals {{ font-size: 13px; color: #d1d5db; }}
    .alert-high {{ background: rgba(248, 113, 113, 0.08); border-left: 3px solid #f87171; }}
    .alert-medium {{ background: rgba(251, 191, 36, 0.06); border-left: 3px solid #fbbf24; }}
    .alert-none {{ border-left: 3px solid transparent; }}
    .error-row {{ color: #6b7280; font-style: italic; }}
    .legend {{ margin-top: 20px; font-size: 12px; color: #6b7280; }}
</style>
</head>
<body>
    <h1>📊 Aktie-overvågning</h1>
    <div class="timestamp">Sidst opdateret: {timestamp}</div>
    <table>
        <tr>
            <th>Ticker</th>
            <th>Pris</th>
            <th>Ændring</th>
            <th>Volumen</th>
            <th>RSI</th>
            <th>Signaler</th>
        </tr>
        {rows_html}
    </table>
    <div class="legend">
        🔴 Høj alert (2+ signaler) · 🟡 Medium (1 signal) · Ingen kant = intet signal<br>
        Tærskler: prisændring ≥ {PRICE_CHANGE_THRESHOLD}% · volumen ≥ {VOLUME_SPIKE_MULTIPLIER}x snit · RSI ≥ {RSI_OVERBOUGHT} eller ≤ {RSI_OVERSOLD}
    </div>
</body>
</html>"""

    return html


def main():
    print(f"Henter data for {len(TICKERS)} aktier...")
    results = [analyze_ticker(t) for t in TICKERS]

    html = generate_html(results)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Dashboard genereret: {os.path.abspath(OUTPUT_FILE)}")

    # Print også et hurtigt resumé i terminalen
    for r in results:
        if r.get("error"):
            print(f"  {r['ticker']}: FEJL - {r['error']}")
        elif r["alert_level"] != "none":
            print(f"  ⚠️  {r['ticker']}: {', '.join(r['signals'])}")


if __name__ == "__main__":
    main()


# -----------------------------------------------------------
# SÅDAN KØRER DU DET AUTOMATISK
# -----------------------------------------------------------
#
# OPTION A — Din egen computer (Mac/Linux), kør hver 30. minut i handelstiden:
#   1. Åbn terminal, kør: crontab -e
#   2. Tilføj linjen (juster sti):
#      */30 9-22 * * 1-5 /usr/bin/python3 /sti/til/stock_monitor.py
#
# OPTION B — Windows: brug Task Scheduler til at køre scriptet med samme interval.
#
# OPTION C — Gratis cloud-løsning (anbefalet hvis du vil slippe for din egen PC):
#   Brug GitHub Actions til at køre scriptet automatisk og publicere
#   dashboardet som en gratis hjemmeside via GitHub Pages.
#   Sig til, så sætter jeg det op for dig.
