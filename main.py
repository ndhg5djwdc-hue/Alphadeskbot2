import os
import schedule
import time
from datetime import datetime
import pytz

from market_data import MarketData
from claude_analyst import ClaudeAnalyst
from telegram_bot import TelegramBot
from portfolio import Portfolio

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
TELEGRAM_TOKEN    = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID  = os.getenv("TELEGRAM_CHAT_ID", "")
TIMEZONE          = "Europe/Berlin"

POSITIONEN = [
    {"name": "Infineon Call",  "typ": "call",    "ticker": "IFX.DE", "strike": 76,    "laufzeit": "2026-12-18", "alert_stop": 62.0},
    {"name": "DAX Long KO",    "typ": "ko_long", "ticker": "^GDAXI", "barriere": 23500, "alert_stop": 24500.0},
    {"name": "RKLB Call",      "typ": "call",    "ticker": "RKLB",   "strike": 125,   "laufzeit": "2026-08-15", "alert_stop": 115.0},
    {"name": "Nvidia Call",    "typ": "call",    "ticker": "NVDA",   "strike": 230,   "laufzeit": "2026-06-20", "alert_stop": 215.0},
    {"name": "Meta Call",      "typ": "call",    "ticker": "META",   "strike": 620,   "laufzeit": "2026-12-18", "alert_stop": 500.0},
    {"name": "TSMC KO Long",   "typ": "ko_long", "ticker": "TSM",    "barriere": 372, "alert_stop": 380.0},
]

ALERT_THRESHOLDS = {
    "^GDAXI": {"up": 25600, "down": 24500},
    "NVDA":   {"up": 235,   "down": 215},
    "IFX.DE": {"up": 78,    "down": 62},
    "RKLB":   {"up": 145,   "down": 115},
    "META":   {"up": 600,   "down": 500},
    "TSM":    {"up": 420,   "down": 380},
}

def main():
    print("AlphaDeskBot startet...")

    market    = MarketData()
    analyst   = ClaudeAnalyst(ANTHROPIC_API_KEY)
    bot       = TelegramBot(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)
    portfolio = Portfolio(POSITIONEN)

    bot.send("AlphaDeskBot ist online!\n\nTaegliches Briefing: 15:00 Uhr MEZ\nEchtzeit-Alerts: aktiv\nPositionen ueberwacht: " + str(len(POSITIONEN)))

    def daily_briefing():
        tz  = pytz.timezone(TIMEZONE)
        now = datetime.now(tz)
        print(f"[{now.strftime('%H:%M')}] Starte Briefing...")
        try:
            kurse = market.get_all_prices([
                "^GDAXI", "^GSPC", "^IXIC",
                "NVDA", "IFX.DE", "RKLB", "META", "TSM",
                "BZ=F", "GC=F",
            ])
            portfolio_status = portfolio.get_status(kurse)
            news             = market.get_news()
            briefing         = analyst.create_briefing(kurse, portfolio_status, news)
            bot.send_briefing(briefing, kurse, portfolio_status)
            print("Briefing gesendet.")
        except Exception as e:
            print(f"Fehler Briefing: {e}")
            bot.send(f"Fehler beim Briefing: {str(e)}")

    def check_alerts():
        try:
            tickers = list(ALERT_THRESHOLDS.keys())
            kurse   = market.get_all_prices(tickers)
            for ticker, thresholds in ALERT_THRESHOLDS.items():
                if ticker not in kurse:
                    continue
                kurs = kurse[ticker]["price"]
                if kurs == 0:
                    continue
                if kurs >= thresholds["up"]:
                    bot.send(f"UPSIDE ALERT: {ticker}\nKurs: {kurs} erreicht Ziel {thresholds['up']}\nGewinne sichern!")
                    ALERT_THRESHOLDS[ticker]["up"] *= 1.05
                if kurs <= thresholds["down"]:
                    bot.send(f"STOP ALERT: {ticker}\nKurs: {kurs} unter Stop {thresholds['down']}\nPosition pruefen!")
                    ALERT_THRESHOLDS[ticker]["down"] *= 0.97
        except Exception as e:
            print(f"Alert Fehler: {e}")

    schedule.every().day.at("09:00").do(lambda: bot.send("Guten Morgen! AlphaDeskBot aktiv. Briefing folgt um 15:00 Uhr."))
    schedule.every().day.at("15:00").do(daily_briefing)
    schedule.every(5).minutes.do(check_alerts)

    print("Scheduler aktiv: Briefing 15:00 Uhr, Alerts alle 5 Min")
    daily_briefing()

    while True:
        schedule.run_pending()
        time.sleep(30)

if __name__ == "__main__":
    main()
