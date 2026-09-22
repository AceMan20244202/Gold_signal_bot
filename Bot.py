import requests
import pandas as pd
import telebot
from telebot import types
import json
import os
from datetime import datetime, timedelta

# ==================== تنظیمات ====================
TELEGRAM_TOKEN = "8384433271:AAHSZRwKRV3LtSNwErubiN9Id2opTh1UDLc"
ADMIN_ID = "979480591"  # آیدی خودت (ادمین)
TWELVEDATA_API_KEY = "7194fdf6808542bb8bf6bf61d7e7b5da"

FOREX_SYMBOLS = [
    "EUR/USD", "GBP/USD", "USD/JPY", "AUD/USD", "USD/CAD",
    "NZD/USD", "EUR/GBP", "EUR/JPY", "GBP/JPY", "XAU/USD"
]

CRYPTO_SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
    "ADAUSDT", "DOGEUSDT", "DOTUSDT", "MATICUSDT", "LINKUSDT"
]

FOREX_INTERVALS = ["15min"]
CRYPTO_INTERVALS = ["15m"]

DB_FILE = "signals_db.json"
USERS_FILE = "users_db.json"
PENDING_FILE = "pending_db.json"

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

# ---------- دیتابیس کاربران ----------
def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            return json.load(f)
    return {"approved": [ADMIN_ID]}  # ادمین پیش‌فرض

def save_users(data):
    with open(USERS_FILE, "w") as f:
        json.dump(data, f, indent=2)

def load_pending():
    if os.path.exists(PENDING_FILE):
        with open(PENDING_FILE, "r") as f:
            return json.load(f)
    return {"pending": []}

def save_pending(data):
    with open(PENDING_FILE, "w") as f:
        json.dump(data, f, indent=2)

def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            return json.load(f)
    return {"signals": []}

def save_db(db):
    with open(DB_FILE, "w") as f:
        json.dump(db, f, indent=2)

# ---------- ارسال به همه کاربران تایید شده ----------
def send_to_all(message):
    users = load_users()
    for cid in users["approved"]:
        try:
            bot.send_message(cid, message)
        except Exception as e:
            print(f"خطا در ارسال به {cid}: {e}")

# ---------- دریافت پیام‌های جدید تلگرام (Polling) ----------
def process_telegram_updates():
    """پیام‌های جدید رو از تلگرام می‌خونه"""
    offset_file = "offset.txt"
    offset = 0
    if os.path.exists(offset_file):
        with open(offset_file, "r") as f:
            offset = int(f.read().strip() or 0)

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    params = {"offset": offset, "timeout": 5}

    try:
        r = requests.get(url, params=params, timeout=15)
        data = r.json()
        if not data.get("ok"):
            return
        updates = data.get("result", [])
        for u in updates:
            update_id = u["update_id"]
            offset = update_id + 1

            # پیام متنی
            if "message" in u:
                msg = u["message"]
                chat_id = str(msg["chat"]["id"])
                text = msg.get("text", "")
                user_name = msg["chat"].get("first_name", "Unknown")

                # بررسی کاربر جدید
                if text == "/start":
                    users = load_users()
                    pending = load_pending()

                    if chat_id == ADMIN_ID:
                        bot.send_message(chat_id, "👑 خوش اومدی ادمین!\nبات آماده است.")
                    elif chat_id in users["approved"]:
                        bot.send_message(chat_id, "✅ شما قبلاً تایید شده‌اید. سیگنال‌ها براتون ارسال می‌شه.")
                    elif any(p["chat_id"] == chat_id for p in pending["pending"]):
                        bot.send_message(chat_id, "⏳ درخواست شما در انتظار تایید ادمین است.")
                    else:
                        # اضافه به لیست انتظار
                        pending["pending"].append({
                            "chat_id": chat_id,
                            "name": user_name,
                            "time": datetime.now().strftime("%Y-%m-%d %H:%M")
                        })
                        save_pending(pending)

                        # پیام به کاربر
                        bot.send_message(chat_id, "✅ درخواست شما ثبت شد.\nلطفاً منتظر تایید ادمین باشید.")

                        # پیام به ادمین
                        keyboard = types.InlineKeyboardMarkup()
                        btn_yes = types.InlineKeyboardButton("✅ تایید", callback_data=f"approve_{chat_id}")
                        btn_no = types.InlineKeyboardButton("❌ رد", callback_data=f"reject_{chat_id}")
                        keyboard.add(btn_yes, btn_no)

                        bot.send_message(ADMIN_ID,
                            f"🔔 درخواست جدید:\n\n"
                            f"👤 نام: {user_name}\n"
                            f"🆔 Chat ID: {chat_id}\n"
                            f"🕐 زمان: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                            reply_markup=keyboard)

            # دکمه‌های تایید/رد
            if "callback_query" in u:
                cb = u["callback_query"]
                cb_id = cb["id"]
                data_cb = cb["data"]
                admin_chat_id = str(cb["from"]["id"])

                if admin_chat_id != ADMIN_ID:
                    continue

                if data_cb.startswith("approve_"):
                    target_id = data_cb.replace("approve_", "")
                    users = load_users()
                    if target_id not in users["approved"]:
                        users["approved"].append(target_id)
                        save_users(users)

                    # حذف از لیست انتظار
                    pending = load_pending()
                    pending["pending"] = [p for p in pending["pending"] if p["chat_id"] != target_id]
                    save_pending(pending)

                    bot.answer_callback_query(cb_id, "✅ تایید شد")
                    bot.edit_message_text(f"✅ کاربر {target_id} تایید شد.",
                        chat_id=ADMIN_ID, message_id=cb["message"]["message_id"])
                    try:
                        bot.send_message(target_id, "🎉 تایید شدید!\nاز این به بعد سیگنال‌ها براتون ارسال می‌شه.")
                    except:
                        pass

                elif data_cb.startswith("reject_"):
                    target_id = data_cb.replace("reject_", "")
                    pending = load_pending()
                    pending["pending"] = [p for p in pending["pending"] if p["chat_id"] != target_id]
                    save_pending(pending)

                    bot.answer_callback_query(cb_id, "❌ رد شد")
                    bot.edit_message_text(f"❌ کاربر {target_id} رد شد.",
                        chat_id=ADMIN_ID, message_id=cb["message"]["message_id"])
                    try:
                        bot.send_message(target_id, "❌ متاسفانه درخواست شما رد شد.")
                    except:
                        pass

        # ذخیره offset
        with open(offset_file, "w") as f:
            f.write(str(offset))

    except Exception as e:
        print(f"خطا در پردازش آپدیت‌ها: {e}")

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
            return None
        df = pd.DataFrame(data["values"])
        df["datetime"] = pd.to_datetime(df["datetime"])
        df = df.sort_values("datetime").reset_index(drop=True)
        for col in ["open", "high", "low", "close"]:
            df[col] = df[col].astype(float)
        return df
    except:
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
    except:
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
            "symbol": symbol, "market": market, "interval": interval,
            "type": signal,
            "entry": round(price, 5), "tp": round(tp, 5), "sl": round(sl, 5),
            "pip_tp": round(pip_tp, 1), "pip_sl": round(pip_sl, 1),
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
        send_to_all(msg)
        print(f"✅ {signal} - {symbol}")

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
                    s["status"] = "expired"; changed = True
                    send_to_all(f"⏰ سیگنال منقضی شد\n📊 {s['symbol']} ({s['interval']})\nنوع: {s['type']}")
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
                send_to_all(f"✅ TP خورد! سود +{s['pip_tp']} پیپ\n📊 {s['symbol']} ({s['interval']})")
            elif current_price <= s["sl"]:
                s["status"] = "loss"; changed = True
                send_to_all(f"❌ SL خورد! ضرر -{s['pip_sl']} پیپ\n📊 {s['symbol']} ({s['interval']})")
        else:
            if current_price <= s["tp"]:
                s["status"] = "win"; changed = True
                send_to_all(f"✅ TP خورد! سود +{s['pip_tp']} پیپ\n📊 {s['symbol']} ({s['interval']})")
            elif current_price >= s["sl"]:
                s["status"] = "loss"; changed = True
                send_to_all(f"❌ SL خورد! ضرر -{s['pip_sl']} پیپ\n📊 {s['symbol']} ({s['interval']})")

    if changed:
        save_db(db)

# ---------- اجرای اصلی ----------
if __name__ == "__main__":
    print("🚀 اجرای بات...")

    # ۱. پردازش پیام‌های جدید تلگرام (تایید/رد)
    process_telegram_updates()

    # ۲. بررسی نتایج سیگنال‌های قبلی
    check_results()

    # ۳. جستجوی سیگنال‌های جدید
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

    print("✅ پایان اجرا")
