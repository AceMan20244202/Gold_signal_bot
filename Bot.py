import requests
import pandas as pd
import telebot
from telebot import types
import json
import os
from datetime import datetime, timedelta, timezone

# ==================== تنظیمات ====================
TELEGRAM_TOKEN = "8384433271:AAHSZRwKRV3LtSNwErubiN9Id2opTh1UDLc"
ADMIN_ID = "979480591"
CHANNEL_ID = "-1004458845744"
CHANNEL_INVITE_LINK = "https://t.me/+92D1qsrJrzw1OTc8"
TWELVEDATA_API_KEY = "7194fdf6808542bb8bf6bf61d7e7b5da"

FOREX_SYMBOLS = [
    "EUR/USD", "GBP/USD", "USD/JPY", "AUD/USD", "USD/CAD",
    "NZD/USD", "EUR/GBP", "EUR/JPY", "GBP/JPY", "XAU/USD"
]

CRYPTO_SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
    "ADAUSDT", "DOGEUSDT", "DOTUSDT", "MATICUSDT", "LINKUSDT",
    "AVAXUSDT", "TRXUSDT", "LTCUSDT", "BCHUSDT", "XLMUSDT",
    "ATOMUSDT", "ETCUSDT", "FILUSDT", "NEARUSDT", "ALGOUSDT",
    "VETUSDT", "ICPUSDT", "HBARUSDT", "EOSUSDT", "AAVEUSDT"
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
    "XAU/USD": 0.1
}

RR_TP1 = 1.5
RR_TP2 = 2.0
RR_TP3 = 2.5
ENTRY_FILTER_PIPS = 5

# ==================================================

bot = telebot.TeleBot(TELEGRAM_TOKEN)

# ---------- متن‌های آماده ----------
def footer():
    return """
━━━━━━━━━━━━━━━━━━
🌟   برای شما آرزوی 
    ثروت و فراوانی داریم   🌟
━━━━━━━━━━━━━━━━━━
با سپاس فراوان
MiHi Btn"""

WELCOME_MSG = """━━━━━━━━━━━━━━━━━━
   🏆  MiHi  Btn 🏆
━━━━━━━━━━━━━━━━━━

✨  خوش آمدید

🎯  اینجا مکانی است برای 
    معامله‌گرانی که به دنبال 
    رشد حرفه‌ای هستند.

📈  در این کانال:
    ◾️ سیگنال‌های دقیق
    ◾️ تحلیل‌های زنده
    ◾️ مدیریت ریسک
    ◾️ گزارش‌های منظم

🔥  اینجا فقط سیگنال دریافت نمی‌کنید،
    بلکه یاد می‌گیرید چطور 
    مثل یک حرفه‌ای فکر کنید.

💼  با نظم، صبر و استراتژی درست،
    مسیر ثروت هموار می‌شود.

⚠️  یادآوری: بازار همیشه در حرکت است.
    با مدیریت سرمایه عمل کنید.

💎  مسیر ثروت با دانش آغاز می‌شود.

""" + footer()

# ---------- دیتابیس ----------
def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            return json.load(f)
    return {"approved": [ADMIN_ID]}

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

# ---------- ارسال ----------
def send_to_channel(message):
    try:
        bot.send_message(CHANNEL_ID, message)
    except Exception as e:
        print(f"خطا کانال: {e}")

def send_to_admin(message, reply_markup=None):
    try:
        bot.send_message(ADMIN_ID, message, reply_markup=reply_markup)
    except Exception as e:
        print(f"خطا ادمین: {e}")

# ---------- ساعت مجاز ----------
def is_trading_hours(): 
    # تست: موقتاً همیشه True
    return True
    hour = now_iran.hour
    weekday = now_iran.weekday()
    
    if weekday == 4 and hour >= 23: return False
    if weekday == 5: return False
    if weekday == 6 and hour < 3: return False
    if hour >= 22 or hour < 3: return False
    return True

# ---------- محاسبه پیپ/پوینت ----------
def calculate_pip_or_point(symbol, price_diff):
    if symbol.endswith("USDT"):
        return abs(price_diff)
    else:
        pip = PIP_SIZE.get(symbol, 0.0001)
        return abs(price_diff) / pip

def get_unit(symbol):
    if symbol.endswith("USDT"):
        return "پوینت"
    return "پیپ"

# ---------- دریافت کندل فارکس ----------
def get_forex_candles(symbol, interval):
    url = "https://api.twelvedata.com/time_series"
    params = {"symbol": symbol, "interval": interval, "outputsize": 200, "apikey": TWELVEDATA_API_KEY, "format": "JSON"}
    try:
        r = requests.get(url, params=params, timeout=15)
        data = r.json()
        if "values" not in data: return None
        df = pd.DataFrame(data["values"])
        df["datetime"] = pd.to_datetime(df["datetime"])
        df = df.sort_values("datetime").reset_index(drop=True)
        for col in ["open", "high", "low", "close"]:
            df[col] = df[col].astype(float)
        return df
    except: return None

# ---------- دریافت کندل کریپتو ----------
def get_crypto_candles(symbol, interval):
    url = "https://api.binance.com/api/v3/klines"
    params = {"symbol": symbol, "interval": interval, "limit": 200}
    try:
        r = requests.get(url, params=params, timeout=15)
        data = r.json()
        if not isinstance(data, list) or len(data) == 0: return None
        df = pd.DataFrame(data, columns=["time", "open", "high", "low", "close", "volume", "close_time", "qav", "trades", "tbb", "tbq", "ignore"])
        df["datetime"] = pd.to_datetime(df["time"], unit="ms")
        for col in ["open", "high", "low", "close"]:
            df[col] = df[col].astype(float)
        return df
    except: return None

# ---------- محاسبه OsMA ----------
def calculate_osma(df, fast, slow, signal):
    ema_fast = df["close"].ewm(span=fast, adjust=False).mean()
    ema_slow = df["close"].ewm(span=slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    return macd - signal_line

# ---------- تحلیل خودکار ----------
def generate_analysis(symbol, signal, price, entry, sl, tp1):
    if signal == "BUY":
        return (f"قیمت در ناحیه اشباع فروش قرار دارد.\n"
                f"احتمال بازگشت صعودی به سمت مقاومت وجود دارد.\n"
                f"در صورت تثبیت قیمت بالای {entry:.5f}، ورود معتبر است.")
    else:
        return (f"قیمت در ناحیه اشباع خرید قرار دارد.\n"
                f"احتمال اصلاح نزولی به سمت حمایت وجود دارد.\n"
                f"در صورت تثبیت قیمت زیر {entry:.5f}، ورود معتبر است.")

# ---------- بررسی سیگنال ----------
def check_signal(symbol, df, interval, market):
    if df is None or len(df) < 100: return

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
        unit = get_unit(symbol)
        
        if symbol.endswith("USDT"):
            entry_offset = ENTRY_FILTER_PIPS * 1.0
        else:
            pip = PIP_SIZE.get(symbol, 0.0001)
            entry_offset = ENTRY_FILTER_PIPS * pip

        if signal == "BUY":
            entry = price + entry_offset
            sl = float(df["low"].iloc[-10:].min())
            tp1 = entry + (entry - sl) * RR_TP1
            tp2 = entry + (entry - sl) * RR_TP2
            tp3 = entry + (entry - sl) * RR_TP3
        else:
            entry = price - entry_offset
            sl = float(df["high"].iloc[-10:].max())
            tp1 = entry - (sl - entry) * RR_TP1
            tp2 = entry - (sl - entry) * RR_TP2
            tp3 = entry - (sl - entry) * RR_TP3

        diff_tp1 = calculate_pip_or_point(symbol, entry - tp1)
        diff_tp2 = calculate_pip_or_point(symbol, entry - tp2)
        diff_tp3 = calculate_pip_or_point(symbol, entry - tp3)
        diff_sl = calculate_pip_or_point(symbol, entry - sl)

        db = load_db()
        now = datetime.now()
        current_time = now.strftime("%Y-%m-%d %H:%M")
        
        recent = [s for s in db["signals"]
                  if s["symbol"] == symbol
                  and s["type"] == signal
                  and (now - datetime.strptime(s["time"], "%Y-%m-%d %H:%M")).total_seconds() < 900]
        if recent: return

        market_name = "فارکس" if market == "FOREX" else "کریپتو"
        analysis = generate_analysis(symbol, signal, price, entry, sl, tp1)

        signal_data = {
            "time": current_time,
            "symbol": symbol, "market": market_name, "type": signal,
            "price": round(price, 5), "entry": round(entry, 5), "sl": round(sl, 5),
            "tp1": round(tp1, 5), "tp2": round(tp2, 5), "tp3": round(tp3, 5),
            "diff_tp1": round(diff_tp1, 1), "diff_tp2": round(diff_tp2, 1),
            "diff_tp3": round(diff_tp3, 1), "diff_sl": round(diff_sl, 1),
            "unit": unit, "tp1_hit": False, "tp2_hit": False, "tp3_hit": False,
            "status": "active"
        }
        db["signals"].append(signal_data)
        save_db(db)

        msg = f"""🚨  سیگنال جدید: {signal}  🚨
━━━━━━━━━━━━━━━━━━
💱  نماد: {symbol}
🏦  بازار: {market_name}

🎯  نقطه ورود (Entry): {entry:.5f}
💰  قیمت فعلی: {price:.5f}
🛑  حد ضرر (SL): {sl:.5f}
     اختلاف: {diff_sl:.1f} {unit}
━━━━━━━━━━━━━━━━━━
🎯  اهداف سود:

🥇  TP1: {tp1:.5f}  |  +{diff_tp1:.1f} {unit}
🥈  TP2: {tp2:.5f}  |  +{diff_tp2:.1f} {unit}
🥉  TP3: {tp3:.5f}  |  +{diff_tp3:.1f} {unit}
━━━━━━━━━━━━━━━━━━
📖  تحلیل:
{analysis}

💡  توصیه:
    ▫️ صبر کنید قیمت به Entry برسد
    ▫️ محافظه‌کار: TP1 | متعادل: TP2 | تهاجمی: TP3
    ▫️ پس از TP1، SL را به نقطه ورود منتقل کنید.

🕐  زمان: {current_time}
""" + footer()

        send_to_channel(msg)

# ---------- بررسی نتایج ----------
def check_results():
    db = load_db()
    changed = False
    now = datetime.now()

    for s in db["signals"]:
        if s["status"] != "active": continue

        if s["market"] == "فارکس":
            df = get_forex_candles(s["symbol"], "15min")
        else:
            df = get_crypto_candles(s["symbol"], "15m")

        if df is None or len(df) == 0: continue

        current_price = df["close"].iloc[-1]
        unit = s.get("unit", "پیپ")

        if s["type"] == "BUY":
            if not s["tp3_hit"] and current_price >= s["tp3"]:
                s["tp3_hit"] = True; s["status"] = "win"; changed = True
                send_to_channel(f"🏆 TP3 فعال شد!\n📊 {s['symbol']}\n💰 سود: +{s['diff_tp3']} {unit}\n🎉 تبریک!" + footer())
            elif not s["tp2_hit"] and current_price >= s["tp2"]:
                s["tp2_hit"] = True; changed = True
                send_to_channel(f"✅ TP2 فعال شد!\n📊 {s['symbol']}\n💰 سود: +{s['diff_tp2']} {unit}" + footer())
            elif not s["tp1_hit"] and current_price >= s["tp1"]:
                s["tp1_hit"] = True; changed = True
                send_to_channel(f"✅ TP1 فعال شد!\n📊 {s['symbol']}\n💰 سود: +{s['diff_tp1']} {unit}" + footer())
            elif current_price <= s["sl"]:
                s["status"] = "loss"; changed = True
                send_to_channel(f"❌ SL فعال شد!\n📊 {s['symbol']}\n📉 ضرر: -{s['diff_sl']} {unit}" + footer())
        else:
            if not s["tp3_hit"] and current_price <= s["tp3"]:
                s["tp3_hit"] = True; s["status"] = "win"; changed = True
                send_to_channel(f"🏆 TP3 فعال شد!\n📊 {s['symbol']}\n💰 سود: +{s['diff_tp3']} {unit}" + footer())
            elif not s["tp2_hit"] and current_price <= s["tp2"]:
                s["tp2_hit"] = True; changed = True
                send_to_channel(f"✅ TP2 فعال شد!\n📊 {s['symbol']}\n💰 سود: +{s['diff_tp2']} {unit}" + footer())
            elif not s["tp1_hit"] and current_price <= s["tp1"]:
                s["tp1_hit"] = True; changed = True
                send_to_channel(f"✅ TP1 فعال شد!\n📊 {s['symbol']}\n💰 سود: +{s['diff_tp1']} {unit}" + footer())
            elif current_price >= s["sl"]:
                s["status"] = "loss"; changed = True
                send_to_channel(f"❌ SL فعال شد!\n📊 {s['symbol']}\n📉 ضرر: -{s['diff_sl']} {unit}" + footer())

    if changed:
        save_db(db)

# ---------- اعلام وضعیت پوزیشن‌های باز (هر ۱ ساعت) ----------
def open_positions_report():
    db = load_db()
    active = [s for s in db["signals"] if s["status"] == "active"]
    
    if not active: return
    
    msg = "📋 وضعیت پوزیشن‌های باز:\n━━━━━━━━━━━━━━━━━━\n"
    
    for s in active[-10:]:
        if s["market"] == "فارکس":
            df = get_forex_candles(s["symbol"], "15min")
        else:
            df = get_crypto_candles(s["symbol"], "15m")
        
        if df is None: continue
        
        current = df["close"].iloc[-1]
        unit = s.get("unit", "پیپ")
        entry = s["entry"]
        
        if s["type"] == "BUY":
            pnl = (current - entry) / entry * 100
        else:
            pnl = (entry - current) / entry * 100
        
        status_emoji = "🟢" if pnl > 0 else "🔴"
        
        tp_status = "TP1 ⏳"
        if s.get("tp1_hit"): tp_status = "TP1 ✅"
        if s.get("tp2_hit"): tp_status = "TP2 ✅"
        if s.get("tp3_hit"): tp_status = "TP3 ✅"
        
        msg += f"{status_emoji} {s['symbol']} ({s['type']})\n"
        msg += f"   ورود: {entry:.5f} | فعلی: {current:.5f}\n"
        msg += f"   سود/ضرر: {pnl:+.2f}%\n"
        msg += f"   وضعیت: {tp_status}\n"
        msg += f"   SL: {s['sl']:.5f}\n\n"
    
    msg += "💡 پوزیشن‌های در سود را مدیریت کنید."
    msg += footer()
    
    send_to_channel(msg)

# ---------- گزارش عملکرد هر ۱۰ دقیقه برای اونر ----------
def owner_report():
    db = load_db()
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    
    today_signals = [s for s in db["signals"] if s["time"].startswith(today)]
    wins = [s for s in today_signals if s["status"] == "win"]
    losses = [s for s in today_signals if s["status"] == "loss"]
    active = [s for s in today_signals if s["status"] == "active"]
    
    total_closed = len(wins) + len(losses)
    win_rate = (len(wins) / total_closed * 100) if total_closed > 0 else 0
    
    total_win = sum(s.get("diff_tp3" if s.get("tp3_hit") else "diff_tp2" if s.get("tp2_hit") else "diff_tp1", 0) for s in wins)
    total_loss = sum(s.get("diff_sl", 0) for s in losses)
    
    msg = f"""📊 گزارش عملکرد (هر ۱۰ دقیقه)
🕐 {now.strftime('%H:%M')}
━━━━━━━━━━━━━━━━━━
🔔 امروز: {len(today_signals)} سیگنال
✅ برد: {len(wins)} | ❌ باخت: {len(losses)}
⏳ فعال: {len(active)}
📈 نرخ موفقیت: {win_rate:.1f}%
💰 سود: +{total_win:.1f} | ضرر: -{total_loss:.1f}
📊 خالص: {total_win - total_loss:+.1f}
"""
    send_to_admin(msg)

# ---------- گزارش روزانه ----------
def daily_report():
    db = load_db()
    today = datetime.now().strftime("%Y-%m-%d")
    today_signals = [s for s in db["signals"] if s["time"].startswith(today)]
    wins = [s for s in today_signals if s["status"] == "win"]
    losses = [s for s in today_signals if s["status"] == "loss"]
    active = [s for s in today_signals if s["status"] == "active"]
    total_closed = len(wins) + len(losses)
    win_rate = (len(wins) / total_closed * 100) if total_closed > 0 else 0
    total_win = sum(s.get("diff_tp3" if s.get("tp3_hit") else "diff_tp2" if s.get("tp2_hit") else "diff_tp1", 0) for s in wins)
    total_loss = sum(s.get("diff_sl", 0) for s in losses)
    
    msg = f"""📊 گزارش روزانه 
📅 {today}
━━━━━━━━━━━━━━━━━━
🔔 کل: {len(today_signals)}
✅ سود: {len(wins)} | ❌ ضرر: {len(losses)} | ⏳ فعال: {len(active)}
💰 سود کل: +{total_win:.1f}
❌ ضرر کل: -{total_loss:.1f}
📊 خالص: {total_win - total_loss:+.1f}
🎯 نرخ موفقیت: {win_rate:.1f}%
""" + footer()
    send_to_channel(msg)

# ---------- گزارش هفتگی ----------
def weekly_report():
    db = load_db()
    now = datetime.now()
    week_ago = now - timedelta(days=7)
    week_signals = []
    for s in db["signals"]:
        try:
            s_time = datetime.strptime(s["time"], "%Y-%m-%d %H:%M")
            if s_time >= week_ago: week_signals.append(s)
        except: pass
    wins = [s for s in week_signals if s["status"] == "win"]
    losses = [s for s in week_signals if s["status"] == "loss"]
    total_closed = len(wins) + len(losses)
    win_rate = (len(wins) / total_closed * 100) if total_closed > 0 else 0
    total_win = sum(s.get("diff_tp3" if s.get("tp3_hit") else "diff_tp2" if s.get("tp2_hit") else "diff_tp1", 0) for s in wins)
    total_loss = sum(s.get("diff_sl", 0) for s in losses)
    
    msg = f"""📊 گزارش هفتگی 
📅 {week_ago.strftime('%Y-%m-%d')} تا {now.strftime('%Y-%m-%d')}
━━━━━━━━━━━━━━━━━━
🔔 کل: {len(week_signals)}
✅ سود: {len(wins)} | ❌ ضرر: {len(losses)}
💰 خالص: {total_win - total_loss:+.1f}
🎯 نرخ موفقیت: {win_rate:.1f}%
""" + footer()
    send_to_channel(msg)

# ---------- پیام آخر هفته ----------
def weekend_message():
    msg = f"""🌙 پایان هفته معاملاتی
━━━━━━━━━━━━━━━━━━
⏳ بازار تا دوشنبه 03:00 بسته است.
💡 پوزیشن‌های باز را مدیریت کنید.
🌟 هفته‌ای پر از سود برایتان آرزو می‌کنیم.
""" + footer()
    send_to_channel(msg)

# ---------- پردازش پیام‌های تلگرام ----------
def process_telegram_updates():
    offset_file = "offset.txt"
    offset = 0
    if os.path.exists(offset_file):
        with open(offset_file, "r") as f:
            offset = int(f.read().strip() or 0)

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    params = {"offset": offset, "timeout": 3}

    try:
        r = requests.get(url, params=params, timeout=20)
        data = r.json()
        if not data.get("ok"): return
        updates = data.get("result", [])
        for u in updates:
            update_id = u["update_id"]
            offset = update_id + 1

            if "message" in u:
                msg = u["message"]
                chat_id = str(msg["chat"]["id"])
                text = msg.get("text", "")
                user_name = msg["chat"].get("first_name", "Unknown")

                if text == "/start":
                    users = load_users()
                    pending = load_pending()

                    if chat_id == ADMIN_ID:
                        send_to_admin("👑 خوش آمدی ادمین!")
                    elif chat_id in users["approved"]:
                        try:
                            bot.send_message(chat_id, f"✅ شما قبلاً تایید شده‌اید.\n\n📎 لینک کانال:\n{CHANNEL_INVITE_LINK}")
                        except: pass
                    elif any(p["chat_id"] == chat_id for p in pending["pending"]):
                        try:
                            bot.send_message(chat_id, "⏳ درخواست شما در انتظار تایید ادمین است.")
                        except: pass
                    else:
                        pending["pending"].append({"chat_id": chat_id, "name": user_name, "time": datetime.now().strftime("%Y-%m-%d %H:%M")})
                        save_pending(pending)
                        try: bot.send_message(chat_id, WELCOME_MSG)
                        except: pass

                        keyboard = types.InlineKeyboardMarkup()
                        btn_yes = types.InlineKeyboardButton("✅ تایید", callback_data=f"approve_{chat_id}")
                        btn_no = types.InlineKeyboardButton("❌ رد", callback_data=f"reject_{chat_id}")
                        keyboard.add(btn_yes, btn_no)

                        send_to_admin(f"🔔 درخواست جدید:\n👤 {user_name}\n🆔 {chat_id}\n🕐 {datetime.now().strftime('%H:%M')}", reply_markup=keyboard)

            if "callback_query" in u:
                cb = u["callback_query"]
                cb_id = cb["id"]
                data_cb = cb["data"]
                admin_chat_id = str(cb["from"]["id"])

                if admin_chat_id != ADMIN_ID: continue

                if data_cb.startswith("approve_"):
                    target_id = data_cb.replace("approve_", "")
                    users = load_users()
                    if target_id not in users["approved"]:
                        users["approved"].append(target_id)
                        save_users(users)
                    pending = load_pending()
                    pending["pending"] = [p for p in pending["pending"] if p["chat_id"] != target_id]
                    save_pending(pending)
                    bot.answer_callback_query(cb_id, "✅ تایید شد")
                    try:
                        bot.edit_message_text(f"✅ کاربر {target_id} تایید شد.", chat_id=ADMIN_ID, message_id=cb["message"]["message_id"])
                    except: pass
                    try:
                        bot.send_message(target_id, f"🎉 تایید شدید!\n\n📎 لینک کانال:\n{CHANNEL_INVITE_LINK}")
                    except: pass

                elif data_cb.startswith("reject_"):
                    target_id = data_cb.replace("reject_", "")
                    pending = load_pending()
                    pending["pending"] = [p for p in pending["pending"] if p["chat_id"] != target_id]
                    save_pending(pending)
                    bot.answer_callback_query(cb_id, "❌ رد شد")
                    try:
                        bot.edit_message_text(f"❌ کاربر {target_id} رد شد.", chat_id=ADMIN_ID, message_id=cb["message"]["message_id"])
                    except: pass

        with open(offset_file, "w") as f:
            f.write(str(offset))
    except Exception as e:
        print(f"خطا آپدیت: {e}")

# ---------- بررسی دقیقه ----------
def is_10_min():
    now_iran = datetime.now(timezone.utc) + timedelta(hours=3, minutes=30)
    return now_iran.minute % 10 == 0

def is_1_hour():
    now_iran = datetime.now(timezone.utc) + timedelta(hours=3, minutes=30)
    return now_iran.minute == 0

# ---------- اجرا (GitHub Actions - یک بار اجرا) ----------
if __name__ == "__main__":
    print("🚀 اجرای بات...")
    
    try:
        process_telegram_updates()
    except Exception as e:
        print(f"خطا در process: {e}")
    
    try:
        check_results()
    except Exception as e:
        print(f"خطا در check_results: {e}")
    
    if is_trading_hours():
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

    if is_10_min():
        try: owner_report()
        except: pass
    
    if is_1_hour():
        try: open_positions_report()
        except: pass
    
    now_iran = datetime.now(timezone.utc) + timedelta(hours=3, minutes=30)
    if now_iran.hour == 22 and now_iran.minute < 15:
        try: daily_report()
        except: pass
    
    if now_iran.weekday() == 5 and now_iran.hour == 10 and now_iran.minute < 15:
        try: weekly_report()
        except: pass
    
    if now_iran.weekday() == 4 and now_iran.hour == 23 and now_iran.minute < 15:
        try: weekend_message()
        except: pass
    
    print("✅ پایان اجرا")
