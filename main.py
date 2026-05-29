import os
import requests
from datetime import datetime
import pytz

TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
TIMEZONE         = "Europe/Berlin"

POSITIONEN = [
    {"name": "Gold Long",              "typ": "long",    "ticker": "GC=F",   "alert_stop": 4350},
    {"name": "TSMC KO (Strike $391)",  "typ": "ko_long", "ticker": "TSM",    "barriere": 391, "alert_stop": 395},
    {"name": "RKLB Aktie (+70%)",      "typ": "long",    "ticker": "RKLB",   "alert_stop": 125},
    {"name": "Meta Call ($620)",       "typ": "call",    "ticker": "META",   "strike": 620, "alert_stop": 500},
]

TICKER_NAMEN = {
    "^GDAXI": "DAX",     "^GSPC": "S&P 500",   "^IXIC": "Nasdaq",
    "NVDA": "Nvidia",    "IFX.DE": "Infineon",  "RKLB": "Rocket Lab",
    "META": "Meta",      "TSM": "TSMC",         "BZ=F": "Brent Oel",
    "GC=F": "Gold",      "^N225": "Nikkei",     "^KS11": "Kospi",
    "^TWII": "Taiex",    "^HSI": "Hang Seng",   "PLTR": "Palantir",
    "MSFT": "Microsoft",
}

def send_telegram(text):
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": text},
            timeout=15
        )
        print(f"Telegram: {r.status_code}")
        return r.status_code == 200
    except Exception as e:
        print(f"Telegram Fehler: {e}")
        return False

def get_kurs(ticker):
    """Yahoo Finance v8 API - funktioniert auch auf PythonAnywhere"""
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
        }
        params = {"interval": "1d", "range": "5d"}
        r = requests.get(url, headers=headers, params=params, timeout=15)
        
        if r.status_code != 200:
            return None
            
        data = r.json()
        closes = data["chart"]["result"][0]["indicators"]["quote"][0]["close"]
        closes = [c for c in closes if c is not None]
        
        if len(closes) < 2:
            return None
            
        current  = closes[-1]
        previous = closes[-2]
        change   = current - previous
        pct      = (change / previous) * 100
        
        return {
            "ticker":     ticker,
            "price":      round(current, 2),
            "change":     round(change, 2),
            "change_pct": round(pct, 2),
        }
    except Exception as e:
        print(f"Fehler {ticker}: {e}")
        return None

def get_alle_kurse():
    tickers = ["^GDAXI", "^GSPC", "^IXIC", "^N225", "^KS11",
               "TSM", "RKLB", "META", "GC=F", "BZ=F", "PLTR", "MSFT"]
    kurse = {}
    for t in tickers:
        data = get_kurs(t)
        if data:
            kurse[t] = data
        else:
            kurse[t] = {"ticker": t, "price": 0, "change": 0, "change_pct": 0}
    return kurse

def format_kurs(ticker, data):
    name  = TICKER_NAMEN.get(ticker, ticker)
    price = data["price"]
    pct   = data["change_pct"]
    if price == 0:
        return f"{name}: N/A"
    arrow = "+" if pct > 0 else ""
    trend = "▲" if pct > 0 else "▼" if pct < 0 else "▬"
    return f"{trend} {name}: {price} ({arrow}{pct:.1f}%)"

def main():
    tz  = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    
    print(f"AlphaDeskBot startet... {now.strftime('%H:%M MEZ')}")
    
    # Kurse abrufen
    print("Rufe Kurse ab...")
    kurse = get_alle_kurse()
    
    # NACHRICHT 1: Header + Kurse
    msg1  = f"ALPHADESK BRIEFING\n"
    msg1 += f"{now.strftime('%d.%m.%Y %H:%M')} MEZ\n"
    msg1 += "=" * 25 + "\n\n"
    
    # Asien
    msg1 += "ASIEN:\n"
    for t in ["^N225", "^KS11"]:
        msg1 += format_kurs(t, kurse.get(t, {"price":0,"change_pct":0})) + "\n"
    
    # Europa/USA
    msg1 += "\nEUROPA & USA:\n"
    for t in ["^GDAXI", "^GSPC", "^IXIC"]:
        msg1 += format_kurs(t, kurse.get(t, {"price":0,"change_pct":0})) + "\n"
    
    # Rohstoffe
    msg1 += "\nROHSTOFFE:\n"
    for t in ["GC=F", "BZ=F"]:
        msg1 += format_kurs(t, kurse.get(t, {"price":0,"change_pct":0})) + "\n"
    
    send_telegram(msg1)
    
    # NACHRICHT 2: Positionen
    msg2 = "DEINE POSITIONEN:\n\n"
    
    for pos in POSITIONEN:
        ticker    = pos["ticker"]
        kurs_data = kurse.get(ticker, {"price": 0, "change_pct": 0})
        kurs      = kurs_data["price"]
        pct       = kurs_data["change_pct"]
        name      = pos["name"]
        
        if pos["typ"] == "ko_long":
            barriere   = pos.get("barriere", 0)
            puffer     = round(kurs - barriere, 2) if kurs > 0 else "N/A"
            puffer_pct = round((kurs - barriere) / kurs * 100, 1) if kurs > 0 else 0
            status     = "KRITISCH" if puffer_pct < 5 else "WARNUNG" if puffer_pct < 10 else "SICHER"
            msg2 += f"{name}\n"
            msg2 += f"  Kurs: {kurs} ({'+' if pct>0 else ''}{pct:.1f}%)\n"
            msg2 += f"  Barriere: {barriere} | Puffer: {puffer} ({puffer_pct}%) - {status}\n\n"
            
            if kurs > 0 and kurs <= pos.get("alert_stop", 0):
                send_telegram(f"STOP ALERT: {name}\nKurs {kurs} unter Stop {pos['alert_stop']}!")
                
        elif pos["typ"] == "call":
            strike   = pos.get("strike", 0)
            itm      = kurs > strike if kurs > 0 else False
            abstand  = round(kurs - strike, 2) if kurs > 0 else "N/A"
            itm_text = "IM GELD" if itm else "AUS DEM GELD"
            msg2 += f"{name}\n"
            msg2 += f"  Kurs: {kurs} ({'+' if pct>0 else ''}{pct:.1f}%)\n"
            msg2 += f"  Strike: {strike} | {itm_text} ({abstand:+.2f})\n\n"
            
        else:  # long/direktaktie
            msg2 += f"{name}\n"
            msg2 += f"  Kurs: {kurs} ({'+' if pct>0 else ''}{pct:.1f}%)\n\n"
            
            if kurs > 0 and kurs <= pos.get("alert_stop", 0):
                send_telegram(f"STOP ALERT: {name}\nKurs {kurs} unter Stop {pos['alert_stop']}!")
    
    msg2 += "AlphaDeskBot - Keine Anlageberatung."
    send_telegram(msg2)
    
    # NACHRICHT 3: Top Moves (statisch)
    msg3  = "TOP MOVES HEUTE:\n\n"
    msg3 += "1. Gold Long HALTEN - PCE bestaetigt\n"
    msg3 += "2. RKLB: 50% am 4. Juni sichern\n"
    msg3 += "3. TSMC KO: Stop $395 mental\n"
    msg3 += "4. Palantir Call bei $125-130\n"
    msg3 += "5. Nikkei KO Long bei 65.800\n\n"
    msg3 += "Taegliches Update: 15:00 MEZ"
    send_telegram(msg3)
    
    print("Fertig! Alle Nachrichten gesendet.")

if __name__ == "__main__":
    main()
