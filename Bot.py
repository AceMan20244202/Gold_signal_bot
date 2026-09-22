import requests
import pandas as pd
import telebot
import json
import os
from datetime import datetime

# ==================== تنظیمات ====================
TELEGRAM_TOKEN = "8384433271:AAHSZRwKRV3LtSNwErubiN9Id2opTh1UDLc"
CHAT_ID = "979480591"
TWELVEDATA_API_KEY = "7194fdf6808542bb8bf6bf61d7e7b5da"

SYMBOL = "XAU/USD"
INTERVAL = "15min"
DB_FILE = "signals_db.json"
# ==================================================

bot = telebot.TeleBot(TELEGRAM_TOKEN)

def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            return json.load(f)
    return {"signals": []}

def save_db(db):
    with open(DB_FILE, "w") as f:
        json.dump(db, f, indent=2)

def get_candles():
    url = "https://api.twelvedata.com/time_series"
    params = {
        "symbol": SYMBOL,
        "interval": INTERVAL,
        "outputsize": 200,
        "apikey": TWELVEDATA_API_KEY,
        "format": "JSON"
    }
    try:
        r = requests.get(url, params=params, timeout=15)
        data = r.json()
        if "values" not in data:
            print("خطا در دریافت داده:", data)
            return None
        df = pd.DataFrame(data["values"])
        df["datetime"] = pd.to_datetime(df["datetime"])
        df = df.sort_values("datetime").reset_index(drop=True)
        for col in ["open", "high", "low", "close"]:
            df[col] = df[col].astype(float)
        return df
    except Exception as e:
        print("خطای شبکه:", e)
        return None

def calculate_osma(df, fast, slow, signal):
    ema_fast = df["close"].ewm(span=fast, adjust=False).mean()
    ema_slow = df["close"].ewm(span=slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    return macd - signal_line

def check_signal():
    df = get_candles()
    if df is None or len(df) < 100:
        print("داده کافی نیست")
        return

    osma_slow = calculate_osma(df, 24, 52, 93)
    osma_fast = calculate_osma(df, 8, 17, 31)

    last_slow = osma_slow.iloc[-1]
    last_fast = osma_fast.iloc[-1]
    prev_slow = osma_slow.iloc[-2]
    prev_fast = osma_fast.iloc[-2]

    price = df["close"].iloc[-1]
    signal = None

    if last_slow < 0 and last_fast < 0 and last_fast > prev_fast and last_slow > prev_slow:
        signal = "BUY"
    if last_slow > 0 and last_fast > 0 and last_fast < prev_fast and last_slow < prev_slow:
        signal = "SELL"

    if signal:
        if signal == "BUY":
            sl = float(df["low"].iloc[-10:].min())
            tp = price + (price - sl) * 1.5
        else:
            sl = float(df["high"].iloc[-10:].max())
            tp = price - (sl - price) * 1.5

        db = load_db()
        db["signals"].append({
            "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "type": signal,
            "entry": round(price, 2),
            "tp": round(tp, 2),
            "sl": round(sl, 2),
            "status": "active"
        })
        save_db(db)

        msg = f"""
🚨 سیگنال جدید {signal} 🚨
📊 جفت ارز: XAUUSD
⏰ تایم فریم: M15
💰 Entry: {price:.2f}
🎯 TP: {tp:.2f}
🛑 SL: {sl:.2f}
🕐 زمان: {datetime.now().strftime('%Y-%m-%d %H:%M')}
"""
        bot.send_message(CHAT_ID, msg)
        print(f"سیگنال {signal} ارسال شد")

def check_results():
    df = get_candles()
    if df is None:
        return
    current_price = df["close"].iloc[-1]
    db = load_db()
    changed = False
    for s in db["signals"]:
        if s["status"] != "active":
            continue
        if s["type"] == "BUY":
            if current_price >= s["tp"]:
                s["status"] = "win"; changed = True
            elif current_price <= s["sl"]:
                s["status"] = "loss"; changed = True
        else:
            if current_price <= s["tp"]:
                s["status"] = "win"; changed = True
            elif current_price >= s["sl"]:
                s["status"] = "loss"; changed = True
    if changed:
        save_db(db)

def daily_report():
    db = load_db()
    today = datetime.now().strftime("%Y-%m-%d")
    today_signals = [s for s in db["signals"] if s["time"].startswith(today)]
    wins = [s for s in today_signals if s["status"] == "win"]
    losses = [s for s in today_signals if s["status"] == "loss"]
    active = [s for s in today_signals if s["status"] == "active"]
    total_closed = len(wins) + len(losses)
    win_rate = (len(wins) / total_closed * 100) if total_closed > 0 else 0

    msg = f"""
📊 گزارش امروز ({today})
━━━━━━━━━━━━━━
🔔 کل سیگنال‌ها: {len(today_signals)}
✅ برد: {len(wins)}
❌ باخت: {len(losses)}
⏳ فعال: {len(active)}
📈 نرخ موفقیت: {win_rate:.1f}%
━━━━━━━━━━━━━━
"""
    bot.send_message(CHAT_ID, msg)

if __name__ == "__main__":
    print("🚀 اجرای بات...")
    bot.send_message(CHAT_ID, "🧪 تست موفق! بات آماده است.")
    check_results()
    check_signal()
    now = datetime.now()
    if now.hour == 23:
        daily_report()
    print("✅ پایان اجرا")
