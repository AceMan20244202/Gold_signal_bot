import requests
import pandas as pd
import telebot
import json
import os
from datetime import datetime, timedelta

# ==================== تنظیمات ====================
TELEGRAM_TOKEN = "8384433271:AAHSZRwKRV3LtSNwErubiN9Id2opTh1UDLc"
CHAT_ID = "979480591"
TWELVEDATA_API_KEY = "7194fdf6808542bb8bf6bf61d7e7b5da"

# ۱۰ جفت فارکس برتر
FOREX_SYMBOLS = [
    "EUR/USD", "GBP/USD", "USD/JPY", "AUD/USD", "USD/CAD",
    "NZD/USD", "EUR/GBP", "EUR/JPY", "GBP/JPY", "XAU/USD"
]

# ۱۰ ارز کریپتو برتر
CRYPTO_SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
    "ADAUSDT", "DOGEUSDT", "DOTUSDT", "MATICUSDT", "LINKUSDT"
]

# تایم فریم ۱۵ دقیقه
FOREX_INTERVALS = ["15min"]
CRYPTO_INTERVALS = ["15m"]

DB_FILE = "signals_db.json"

# پیپ هر نماد
PIP_SIZE = {
    "EUR/USD": 0.0001, "GBP/USD": 0.0001, "AUD/USD": 0.0001,
    "NZD/USD": 0.0001, "USD/CAD": 0.0001, "EUR/GBP": 0.0001,
    "USD/JPY": 0.01, "EUR/JPY": 0.01, "GBP/JPY": 0.01,
    "XAU/USD": 0.1,
    "BTCUSDT": 1.0, "ETHUSDT": 0.1, "BNBUSDT": 0.1,
    "SOLUSDT": 0.01, "XRPUSDT": 0.0001, "ADAUSDT": 0.0001,
    "DOGEUSDT": 0.00001, "DOTUSDT": 0.001, "MATICUSDT": 0.0001,
    "LINKUSDT": 0.001
}
# ==================================================

bot = telebot.TeleBot(TELEGRAM_TOKEN)

# ---------- دیتابیس ----------
def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            return json.load(f)
    return {"signals": []}

def save_db(db):
    with open(DB_FILE, "w") as f:
        json.dump(db, f, indent=2)

# ---------- دریافت کندل فارکس ----------
def get_forex_candles(symbol, interval):
    url = "https://api.twelvedata.com/time_series"
    params = {
        "symbol": symbol, "interval": interval,
        "outputsize": 200, "apikey": TWELVEDATA_API_KEY, "format": "JSON"
    }
    try:
        r = requests.get(url, params=params, timeout=15)
        data = r.json()
        if "values" not in data:
            print(f"⚠️ {symbol}: {data.get('message', 'داده نامعتبر')}")
            return None
        df = pd.DataFrame(data["values"])
        df["datetime"] = pd.to_datetime(df["datetime"])
        df = df.sort_values("datetime").reset_index(drop=True)
        for col in ["open", "high", "low", "close"]:
            df[col] = df[col].astype(float)
        return df
    except Exception as e:
        print(f"خطا در {symbol}: {e}")
        return None

# ---------- دریافت کندل کریپتو ----------
def get_crypto_candles(symbol, interval):
    url = "https://api.binance.com/api/v3/klines"
    params = {"symbol": symbol, "interval": interval, "limit": 200}
    try:
        r = requests.get(url, params=params, timeout=15)
        data = r.json()
        if not isinstance(data, list) or len(data) == 0:
            return None
        df = pd.DataFrame(data, columns=[
            "time", "open", "high", "low", "close", "volume",
            "close_time", "qav", "trades", "tbb", "tbq", "ignore"
        ])
        df["datetime"] = pd.to_datetime(df["time"], unit="ms")
        for col in ["open", "high", "low", "close"]:
            df[col] = df[col].astype(float)
        return df
    except Exception as e:
        print(f"خطا در {symbol}: {e}")
        return None

# ---------- محاسبه OsMA ----------
def calculate_osma(df, fast, slow, signal):
    ema_fast = df["close"].ewm(span=fast, adjust=False).mean()
    ema_slow = df["close"].ewm(span=slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    return macd - signal_line

# ---------- بررسی سیگنال ----------
def check_signal(symbol, df, interval, market):
    if df is None or len(df) < 100:
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
        pip = PIP_SIZE.get(symbol, 0.0001)
        if signal == "BUY":
            sl = float(df["low"].iloc[-10:].min())
            tp = price + (price - sl) * 1.5
        else:
            sl = float(df["high"].iloc[-10:].max())
            tp = price - (sl - price) * 1.5

        pip_tp = abs(tp - price) / pip
        pip_sl = abs(price - sl) / pip

        db = load_db()
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M")
        existing = [s for s in db["signals"]
                    if s["symbol"] == symbol
                    and s["interval"] == interval
                    and s["time"] == current_time]
        if existing:
            return

        signal_data = {
            "time": current_time,
            "expire_time": (datetime.now() + timedelta(hours=2)).strftime("%Y-%m-%d %H:%M"),
            "symbol": symbol,
            "market": market,
            "interval": interval,
            "type": signal,
            "entry": round(price, 5),
            "tp": round(tp, 5),
            "sl": round(sl, 5),
            "pip_tp": round(pip_tp, 1),
            "pip_sl": round(pip_sl, 1),
            "status": "active"
        }
        db["signals"].append(signal_data)
        save_db(db)

        market_emoji = "💱" if market == "FOREX" else "🪙"
        msg = f"""
🚨 سیگنال جدید {signal} 🚨
━━━━━━━━━━━━━━
{market_emoji} نماد: {symbol}
🏦 بازار: {market}
⏰ تایم فریم: {interval}
💰 Entry: {price:.5f}
🎯 TP: {tp:.5f} ({pip_tp:.1f} پیپ)
🛑 SL: {sl:.5f} ({pip_sl:.1f} پیپ)
⏳ انقضا: ۲ ساعت
🕐 زمان: {current_time}
━━━━━━━━━━━━━━
"""
        try:
            bot.send_message(CHAT_ID, msg)
            print(f"✅ {signal} - {symbol} - {interval}")
        except Exception as e:
            print(f"خطا در ارسال: {e}")

# ---------- بررسی نتایج ----------
def check_results():
    db = load_db()
    changed = False
    now = datetime.now()

    for s in db["signals"]:
        if s["status"] != "active":
            continue

        if "expire_time" in s:
            try:
                expire = datetime.strptime(s["expire_time"], "%Y-%m-%d %H:%M")
                if now > expire:
                    s["status"] = "expired"
                    changed = True
                    bot.send_message(CHAT_ID,
                        f"⏰ سیگنال منقضی شد\n📊 {s['symbol']} ({s['interval']})\n"
                        f"نوع: {s['type']} | Entry: {s['entry']}")
                    continue
            except:
                pass

        if s["market"] == "FOREX":
            df = get_forex_candles(s["symbol"], s["interval"])
        else:
            df = get_crypto_candles(s["symbol"], s["interval"])

        if df is None or len(df) == 0:
            continue

        current_price = df["close"].iloc[-1]

        if s["type"] == "BUY":
            if current_price >= s["tp"]:
                s["status"] = "win"; changed = True
                bot.send_message(CHAT_ID,
                    f"✅ TP خورد! سود +{s['pip_tp']} پیپ\n"
                    f"📊 {s['symbol']} ({s['interval']})")
            elif current_price <= s["sl"]:
                s["status"] = "loss"; changed = True
                bot.send_message(CHAT_ID,
                    f"❌ SL خورد! ضرر -{s['pip_sl']} پیپ\n"
                    f"📊 {s['symbol']} ({s['interval']})")
        else:
            if current_price <= s["tp"]:
                s["status"] = "win"; changed = True
                bot.send_message(CHAT_ID,
                    f"✅ TP خورد! سود +{s['pip_tp']} پیپ\n"
                    f"📊 {s['symbol']} ({s['interval']})")
            elif current_price >= s["sl"]:
                s["status"] = "loss"; changed = True
                bot.send_message(CHAT_ID,
                    f"❌ SL خورد! ضرر -{s['pip_sl']} پیپ\n"
                    f"📊 {s['symbol']} ({s['interval']})")

    if changed:
        save_db(db)

# ---------- گزارش روزانه ----------
def daily_report():
    db = load_db()
    today = datetime.now().strftime("%Y-%m-%d")
    today_signals = [s for s in db["signals"] if s["time"].startswith(today)]

    wins = [s for s in today_signals if s["status"] == "win"]
    losses = [s for s in today_signals if s["status"] == "loss"]
    active = [s for s in today_signals if s["status"] == "active"]
    expired = [s for s in today_signals if s["status"] == "expired"]

    total_closed = len(wins) + len(losses)
    win_rate = (len(wins) / total_closed * 100) if total_closed > 0 else 0

    total_pip_win = sum(s.get("pip_tp", 0) for s in wins)
    total_pip_loss = sum(s.get("pip_sl", 0) for s in losses)
    net_pip = total_pip_win - total_pip_loss

    forex_count = len([s for s in today_signals if s["market"] == "FOREX"])
    crypto_count = len([s for s in today_signals if s["market"] == "CRYPTO"])

    msg = f"""
📊 گزارش روزانه ({today})
━━━━━━━━━━━━━━
🔔 کل سیگنال‌ها: {len(today_signals)}
   💱 فارکس: {forex_count}
   🪙 کریپتو: {crypto_count}

📈 نتایج:
   ✅ برد: {len(wins)}
   ❌ باخت: {len(losses)}
   ⏳ فعال: {len(active)}
   ⏰ منقضی: {len(expired)}

💰 پیپ‌ها:
   ✅ سود کل: +{total_pip_win:.1f}
   ❌ ضرر کل: -{total_pip_loss:.1f}
   📊 خالص: {net_pip:+.1f} پیپ

🎯 نرخ موفقیت: {win_rate:.1f}%
━━━━━━━━━━━━━━
"""
    bot.send_message(CHAT_ID, msg)

# ---------- اجرای اصلی ----------
if __name__ == "__main__":
    print("🚀 اجرای بات...")
    check_results()

    for symbol in FOREX_SYMBOLS:
        for interval in FOREX_INTERVALS:
            try:
                df = get_forex_candles(symbol, interval)
                check_signal(symbol, df, interval, "FOREX")
            except Exception as e:
                print(f"خطا {symbol}: {e}")

    for symbol in CRYPTO_SYMBOLS:
        for interval in CRYPTO_INTERVALS:
            try:
                df = get_crypto_candles(symbol, interval)
                check_signal(symbol, df, interval, "CRYPTO")
            except Exception as e:
                print(f"خطا {symbol}: {e}")

    now = datetime.now()
    if now.hour == 23 and now.minute < 20:
        daily_report()

    print("✅ پایان اجرا")
