import requests
import pandas as pd
import telebot
from telebot import types
import json
import os
import time
from datetime import datetime, timedelta

# ==================== تنظیمات ====================
TELEGRAM_TOKEN = "8384433271:AAHSZRwKRV3LtSNwErubiN9Id2opTh1UDLc"
ADMIN_ID = "979480591"
CHANNEL_ID = "-1004458845744"
TWELVEDATA_API_KEY = "7194fdf6808542bb8bf6bf61d7e7b5da"

# ۱۰ جفت فارکس
FOREX_SYMBOLS = [
    "EUR/USD", "GBP/USD", "USD/JPY", "AUD/USD", "USD/CAD",
    "NZD/USD", "EUR/GBP", "EUR/JPY", "GBP/JPY", "XAU/USD"
]

# ۲۵ ارز کریپتو
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

# پیپ هر نماد فارکس
PIP_SIZE = {
    "EUR/USD": 0.0001, "GBP/USD": 0.0001, "AUD/USD": 0.0001,
    "NZD/USD": 0.0001, "USD/CAD": 0.0001, "EUR/GBP": 0.0001,
    "USD/JPY": 0.01, "EUR/JPY": 0.01, "GBP/JPY": 0.01,
    "XAU/USD": 0.1
}

# نسبت ریسک به ریوارد
RR_TP1 = 1.5
RR_TP2 = 2.0
RR_TP3 = 2.5

# فیلتر Entry (5 پیپ)
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

# ---------- ارسال به کانال ----------
def send_to_channel(message):
    try:
        bot.send_message(CHANNEL_ID, message)
    except Exception as e:
        print(f"خطا در ارسال به کانال: {e}")

# ---------- ارسال به ادمین ----------
def send_to_admin(message, reply_markup=None):
    try:
        bot.send_message(ADMIN_ID, message, reply_markup=reply_markup)
    except Exception as e:
        print(f"خطا در ارسال به ادمین: {e}")

# ---------- بررسی ساعت مجاز ----------
def is_trading_hours():
    now_iran = datetime.utcnow() + timedelta(hours=3, minutes=30)
    hour = now_iran.hour
    weekday = now_iran.weekday()  # 0=دوشنبه ... 4=جمعه، 5=شنبه، 6=یکشنبه
    
    # جمعه شب به بعد (ساعت 23 جمعه)
    if weekday == 4 and hour >= 23:
        return False
    # شنبه کامل
    if weekday == 5:
        return False
    # یکشنبه قبل از 3 بامداد
    if weekday == 6 and hour < 3:
        return False
    
    # هر روز بین 22 شب تا 3 بامداد
    if hour >= 22 or hour < 3:
        return False
    
    return True

# ---------- محاسبه پیپ/پوینت ----------
def calculate_pip_or_point(symbol, price_diff):
    """محاسبه پیپ برای فارکس و پوینت برای کریپتو"""
    if symbol.endswith("USDT"):
        # کریپتو: پوینت (1 واحد = 1 پوینت)
        return abs(price_diff)
    else:
        # فارکس: پیپ
        pip = PIP_SIZE.get(symbol, 0.0001)
        return abs(price_diff) / pip

# ---------- واحد اندازه‌گیری ----------
def get_unit(symbol):
    if symbol.endswith("USDT"):
        return "پوینت"
    return "پیپ"

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

# ---------- تحلیل خودکار ----------
def generate_analysis(symbol, signal, price, entry, sl, tp1):
    if signal == "BUY":
        analysis = f"قیمت در ناحیه اشباع فروش قرار دارد.\n"
        analysis += f"احتمال بازگشت صعودی به سمت مقاومت وجود دارد.\n"
        analysis += f"در صورت تثبیت قیمت بالای {entry:.5f}، ورود معتبر است."
    else:
        analysis = f"قیمت در ناحیه اشباع خرید قرار دارد.\n"
        analysis += f"احتمال اصلاح نزولی به سمت حمایت وجود دارد.\n"
        analysis += f"در صورت تثبیت قیمت زیر {entry:.5f}، ورود معتبر است."
    
    return analysis

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
        unit = get_unit(symbol)
        
        # محاسبه Entry با فیلتر
        if symbol.endswith("USDT"):
            # کریپتو: 5 پوینت
            entry_offset = ENTRY_FILTER_PIPS * 1.0
        else:
            # فارکس: 5 پیپ
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
        
        # فیلتر تکرار: 15 دقیقه
        recent = [s for s in db["signals"]
                  if s["symbol"] == symbol
                  and s["type"] == signal
                  and (now - datetime.strptime(s["time"], "%Y-%m-%d %H:%M")).total_seconds() < 900]
        if recent:
            print(f"⏭️ سیگنال تکراری {symbol} رد شد")
            return

        market_name = "فارکس" if market == "FOREX" else "کریپتو"
        analysis = generate_analysis(symbol, signal, price, entry, sl, tp1)

        signal_data = {
            "time": current_time,
            "expire_time": (now + timedelta(hours=2)).strftime("%Y-%m-%d %H:%M"),
            "symbol": symbol,
            "market": market_name,
            "type": signal,
            "price": round(price, 5),
            "entry": round(entry, 5),
            "sl": round(sl, 5),
            "tp1": round(tp1, 5),
            "tp2": round(tp2, 5),
            "tp3": round(tp3, 5),
            "diff_tp1": round(diff_tp1, 1),
            "diff_tp2": round(diff_tp2, 1),
            "diff_tp3": round(diff_tp3, 1),
            "diff_sl": round(diff_sl, 1),
            "unit": unit,
            "tp1_hit": False,
            "tp2_hit": False,
            "tp3_hit": False,
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

🥇  TP1 (محافظه‌کار):
     {tp1:.5f}  |  +{diff_tp1:.1f} {unit}

🥈  TP2 (متعادل):
     {tp2:.5f}  |  +{diff_tp2:.1f} {unit}

🥉  TP3 (تهاجمی):
     {tp3:.5f}  |  +{diff_tp3:.1f} {unit}
━━━━━━━━━━━━━━━━━━
📖  تحلیل:

{analysis}

💡  توصیه معاملاتی:
    ▫️ صبر کنید قیمت به Entry برسد
    ▫️ سپس وارد شوید
    ▫️ محافظه‌کار: TP1
    ▫️ متعادل: TP2
    ▫️ تهاجمی: TP3
    ▫️ پس از TP1، حد ضرر را به 
       نقطه ورود منتقل کنید.

🕐  زمان: {current_time}
""" + footer()

        send_to_channel(msg)
        print(f"✅ {signal} - {symbol}")

# ---------- بررسی نتایج ----------
def check_results():
    db = load_db()
    changed = False
    now = datetime.now()

    for s in db["signals"]:
        if s["status"] != "active":
            continue

        # چک انقضا
        if "expire_time" in s:
            try:
                expire = datetime.strptime(s["expire_time"], "%Y-%m-%d %H:%M")
                if now > expire:
                    s["status"] = "expired"
                    changed = True
                    msg = f"""⏰  سیگنال منقضی شد
━━━━━━━━━━━━━━━━━━
📊  نماد: {s['symbol']}
🔔  نوع سیگنال: {s['type']}

⏳  مدت اعتبار: ۲ ساعت
📊  وضعیت: بدون تغییر قابل توجه

💡  توصیه:
    ▫️ به دنبال فرصت بعدی باشید

🕐  زمان: {now.strftime('%Y-%m-%d %H:%M')}
""" + footer()
                    send_to_channel(msg)
                    continue
            except:
                pass

        # دریافت قیمت جدید
        if s["market"] == "فارکس":
            df = get_forex_candles(s["symbol"], "15min")
        else:
            df = get_crypto_candles(s["symbol"], "15m")

        if df is None or len(df) == 0:
            continue

        current_price = df["close"].iloc[-1]
        unit = s.get("unit", "پیپ")

        if s["type"] == "BUY":
            if not s["tp3_hit"] and current_price >= s["tp3"]:
                s["tp3_hit"] = True
                s["status"] = "win"
                changed = True
                msg = f"""🏆  هدف سوم (TP3) فعال شد
━━━━━━━━━━━━━━━━━━
📊  نماد: {s['symbol']}
🔔  نوع سیگنال: {s['type']}

💰  سود: +{s['diff_tp3']} {unit}
🎯 قیمت: {s['tp3']:.5f}

🎉  تبریک! به هدف نهایی رسیدید.

🕐  زمان: {now.strftime('%Y-%m-%d %H:%M')}
""" + footer()
                send_to_channel(msg)
            elif not s["tp2_hit"] and current_price >= s["tp2"]:
                s["tp2_hit"] = True
                changed = True
                msg = f"""✅  هدف دوم (TP2) فعال شد
━━━━━━━━━━━━━━━━━━
📊  نماد: {s['symbol']}
🔔  نوع سیگنال: {s['type']}

💰  سود: +{s['diff_tp2']} {unit}
🎯 قیمت: {s['tp2']:.5f}

💡  توصیه:
    ▫️ سود خوبی کسب کردید
    ▫️ می‌توانید ادامه دهید 
       یا سیو سود کنید

🕐  زمان: {now.strftime('%Y-%m-%d %H:%M')}
""" + footer()
                send_to_channel(msg)
            elif not s["tp1_hit"] and current_price >= s["tp1"]:
                s["tp1_hit"] = True
                changed = True
                msg = f"""✅  هدف اول (TP1) فعال شد
━━━━━━━━━━━━━━━━━━
📊  نماد: {s['symbol']}
🔔  نوع سیگنال: {s['type']}

💰  سود: +{s['diff_tp1']} {unit}
🎯 قیمت: {s['tp1']:.5f}

💡  توصیه:
    ▫️ می‌توانید سود خود را 
       سیو کنید
    ▫️ یا برای TP2 صبر کنید
    ▫️ حد ضرر را به نقطه ورود 
       منتقل کنید (ریسک فری)

🕐  زمان: {now.strftime('%Y-%m-%d %H:%M')}
""" + footer()
                send_to_channel(msg)
            elif current_price <= s["sl"]:
                s["status"] = "loss"
                changed = True
                msg = f"""❌  حد ضرر فعال شد
━━━━━━━━━━━━━━━━━━
📊  نماد: {s['symbol']}
🔔  نوع سیگنال: {s['type']}

📉  ضرر: -{s['diff_sl']} {unit}
🛑 قیمت: {s['sl']:.5f}

💡  توصیه:
    ▫️ ضرر بخشی از معامله‌گری است
    ▫️ مدیریت سرمایه را رعایت کنید
    ▫️ منتظر سیگنال بعدی باشید

🕐  زمان: {now.strftime('%Y-%m-%d %H:%M')}
""" + footer()
                send_to_channel(msg)
        else:  # SELL
            if not s["tp3_hit"] and current_price <= s["tp3"]:
                s["tp3_hit"] = True
                s["status"] = "win"
                changed = True
                msg = f"""🏆  هدف سوم (TP3) فعال شد
━━━━━━━━━━━━━━━━━━
📊  نماد: {s['symbol']}
🔔  نوع سیگنال: {s['type']}

💰  سود: +{s['diff_tp3']} {unit}
🎯 قیمت: {s['tp3']:.5f}

🎉  تبریک! به هدف نهایی رسیدید.

🕐  زمان: {now.strftime('%Y-%m-%d %H:%M')}
""" + footer()
                send_to_channel(msg)
            elif not s["tp2_hit"] and current_price <= s["tp2"]:
                s["tp2_hit"] = True
                changed = True
                msg = f"""✅  هدف دوم (TP2) فعال شد
━━━━━━━━━━━━━━━━━━
📊  نماد: {s['symbol']}
🔔  نوع سیگنال: {s['type']}

💰  سود: +{s['diff_tp2']} {unit}
🎯 قیمت: {s['tp2']:.5f}

💡  توصیه:
    ▫️ سود خوبی کسب کردید
    ▫️ می‌توانید ادامه دهید 
       یا سیو سود کنید

🕐  زمان: {now.strftime('%Y-%m-%d %H:%M')}
""" + footer()
                send_to_channel(msg)
            elif not s["tp1_hit"] and current_price <= s["tp1"]:
                s["tp1_hit"] = True
                changed = True
                msg = f"""✅  هدف اول (TP1) فعال شد
━━━━━━━━━━━━━━━━━━
📊  نماد: {s['symbol']}
🔔  نوع سیگنال: {s['type']}

💰  سود: +{s['diff_tp1']} {unit}
🎯 قیمت: {s['tp1']:.5f}

💡  توصیه:
    ▫️ می‌توانید سود خود را 
       سیو کنید
    ▫️ یا برای TP2 صبر کنید
    ▫️ حد ضرر را به نقطه ورود 
       منتقل کنید (ریسک فری)

🕐  زمان: {now.strftime('%Y-%m-%d %H:%M')}
""" + footer()
                send_to_channel(msg)
            elif current_price >= s["sl"]:
                s["status"] = "loss"
                changed = True
                msg = f"""❌  حد ضرر فعال شد
━━━━━━━━━━━━━━━━━━
📊  نماد: {s['symbol']}
🔔  نوع سیگنال: {s['type']}

📉  ضرر: -{s['diff_sl']} {unit}
🛑 قیمت: {s['sl']:.5f}

💡  توصیه:
    ▫️ ضرر بخشی از معامله‌گری است
    ▫️ مدیریت سرمایه را رعایت کنید
    ▫️ منتظر سیگنال بعدی باشید

🕐  زمان: {now.strftime('%Y-%m-%d %H:%M')}
""" + footer()
                send_to_channel(msg)

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

    total_pip_win = 0
    for s in wins:
        if s.get("tp3_hit"):
            total_pip_win += s.get("diff_tp3", 0)
        elif s.get("tp2_hit"):
            total_pip_win += s.get("diff_tp2", 0)
        elif s.get("tp1_hit"):
            total_pip_win += s.get("diff_tp1", 0)

    total_pip_loss = sum(s.get("diff_sl", 0) for s in losses)
    net_pip = total_pip_win - total_pip_loss

    forex_count = len([s for s in today_signals if s["market"] == "فارکس"])
    crypto_count = len([s for s in today_signals if s["market"] == "کریپتو"])

    msg = f"""📊  گزارش روزانه 
📅  تاریخ: {today}
━━━━━━━━━━━━━━━━━━
🔔  کل سیگنال‌ها: {len(today_signals)}
    💱 فارکس: {forex_count}
    🪙 کریپتو: {crypto_count}

📈  نتایج:
    ✅ سود : {len(wins)}
    ❌ ضرر : {len(losses)}
    ⏳ فعال: {len(active)}
    ⏰ منقضی: {len(expired)}

💰  سود و ضرر:
    ✅ سود کل: +{total_pip_win:.1f}
    ❌ ضرر کل: -{total_pip_loss:.1f}
    📊 خالص: {net_pip:+.1f}

🎯  نرخ موفقیت: {win_rate:.1f}%
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
            if s_time >= week_ago:
                week_signals.append(s)
        except:
            pass

    wins = [s for s in week_signals if s["status"] == "win"]
    losses = [s for s in week_signals if s["status"] == "loss"]
    active = [s for s in week_signals if s["status"] == "active"]
    expired = [s for s in week_signals if s["status"] == "expired"]

    total_closed = len(wins) + len(losses)
    win_rate = (len(wins) / total_closed * 100) if total_closed > 0 else 0

    total_pip_win = 0
    for s in wins:
        if s.get("tp3_hit"):
            total_pip_win += s.get("diff_tp3", 0)
        elif s.get("tp2_hit"):
            total_pip_win += s.get("diff_tp2", 0)
        elif s.get("tp1_hit"):
            total_pip_win += s.get("diff_tp1", 0)

    total_pip_loss = sum(s.get("diff_sl", 0) for s in losses)
    net_pip = total_pip_win - total_pip_loss

    forex_count = len([s for s in week_signals if s["market"] == "فارکس"])
    crypto_count = len([s for s in week_signals if s["market"] == "کریپتو"])

    start_date = week_ago.strftime("%Y-%m-%d")
    end_date = now.strftime("%Y-%m-%d")

    msg = f"""📊  گزارش هفتگی 
📅  از {start_date} تا {end_date}
━━━━━━━━━━━━━━━━━━
🔔  کل سیگنال‌های هفته: {len(week_signals)}
    💱 فارکس: {forex_count}
    🪙 کریپتو: {crypto_count}

📈  نتایج:
    ✅ سود: {len(wins)}
    ❌ ضرر: {len(losses)}
    ⏳ فعال: {len(active)}
    ⏰ منقضی: {len(expired)}

💰  سود و ضرر:
    ✅ سود کل: +{total_pip_win:.1f}
    ❌ ضرر کل: -{total_pip_loss:.1f}
    📊 خالص: {net_pip:+.1f}

🎯  نرخ موفقیت: {win_rate:.1f}%
""" + footer()
    send_to_channel(msg)

# ---------- پیام آخر هفته ----------
def weekend_message():
    now_iran = datetime.utcnow() + timedelta(hours=3, minutes=30)
    msg = f"""🌙  پایان هفته معاملاتی
━━━━━━━━━━━━━━━━━━
📅  امروز: جمعه
⏰  زمان: {now_iran.strftime('%H:%M')}

🏦  بازارها در حال بسته شدن هستند.

⏳  بازار از الان تا 
    دوشنبه ساعت 03:00 بسته است.

💡  توصیه‌های مهم:
    ▫️ پوزیشن‌های باز را مدیریت کنید
    ▫️ سودها را سیو کنید
    ▫️ ریسک‌های اضافی را ببندید
    ▫️ استراحت کنید و انرژی بگیرید

📊  هفته‌ی پر از سیگنال و تحلیل 
    در انتظار شماست.

🌟  هفته‌ای پر از سود و موفقیت 
    برایتان آرزو می‌کنیم.

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
        if not data.get("ok"):
            return
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
                        send_to_admin("👑 خوش آمدی ادمین!\nبات آماده است.")
                    elif chat_id in users["approved"]:
                        send_to_admin("✅ شما قبلاً تایید شده‌اید.")
                    elif any(p["chat_id"] == chat_id for p in pending["pending"]):
                        send_to_admin("⏳ درخواست شما در انتظار تایید ادمین است.")
                    else:
                        pending["pending"].append({
                            "chat_id": chat_id,
                            "name": user_name,
                            "time": datetime.now().strftime("%Y-%m-%d %H:%M")
                        })
                        save_pending(pending)

                        # پیام خوش‌آمد به کاربر
                        try:
                            bot.send_message(chat_id, WELCOME_MSG)
                        except:
                            pass

                        # پیام تایید به ادمین
                        keyboard = types.InlineKeyboardMarkup()
                        btn_yes = types.InlineKeyboardButton("✅ تایید", callback_data=f"approve_{chat_id}")
                        btn_no = types.InlineKeyboardButton("❌ رد", callback_data=f"reject_{chat_id}")
                        keyboard.add(btn_yes, btn_no)

                        send_to_admin(
                            f"🔔 درخواست جدید:\n\n"
                            f"👤 نام: {user_name}\n"
                            f"🆔 Chat ID: {chat_id}\n"
                            f"🕐 زمان: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                            reply_markup=keyboard)

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

                    pending = load_pending()
                    pending["pending"] = [p for p in pending["pending"] if p["chat_id"] != target_id]
                    save_pending(pending)

                    bot.answer_callback_query(cb_id, "✅ تایید شد")
                    try:
                        bot.edit_message_text(f"✅ کاربر {target_id} تایید شد.",
                            chat_id=ADMIN_ID, message_id=cb["message"]["message_id"])
                    except:
                        pass
                    try:
                        bot.send_message(target_id, "🎉 تایید شدید!\nاز این به بعد سیگنال‌ها در کانال ارسال می‌شود.")
                    except:
                        pass

                elif data_cb.startswith("reject_"):
                    target_id = data_cb.replace("reject_", "")
                    pending = load_pending()
                    pending["pending"] = [p for p in pending["pending"] if p["chat_id"] != target_id]
                    save_pending(pending)

                    bot.answer_callback_query(cb_id, "❌ رد شد")
                    try:
                        bot.edit_message_text(f"❌ کاربر {target_id} رد شد.",
                            chat_id=ADMIN_ID, message_id=cb["message"]["message_id"])
                    except:
                        pass

        with open(offset_file, "w") as f:
            f.write(str(offset))

    except Exception as e:
        print(f"خطا در پردازش آپدیت‌ها: {e}")

# ---------- حلقه بی‌پایان ----------
if __name__ == "__main__":
    print("🚀 بات ۲۴ ساعته MiHi Btn فعال شد...")
    
    try:
        send_to_channel("✅ بات MiHi Btn فعال شد و آماده ارسال سیگنال است.")
    except:
        pass

    last_signal_check = None
    last_daily_report = None
    last_weekly_report = None
    last_weekend_msg = None

    while True:
        try:
            now = datetime.now()
            now_iran = datetime.utcnow() + timedelta(hours=3, minutes=30)
            
            # ۱. پردازش پیام‌های تلگرام
            process_telegram_updates()

            # ۲. بررسی نتایج سیگنال‌ها
            check_results()

            # ۳. بررسی سیگنال‌های جدید (فقط در ساعات مجاز)
            if is_trading_hours():
                current_minute = now_iran.minute
                # هر ۱۵ دقیقه یکبار (دقیقه ۰، ۱۵، ۳۰، ۴۵)
                if current_minute in [0, 15, 30, 45]:
                    time_key = f"{now_iran.hour}_{current_minute}_{now_iran.day}"
                    if last_signal_check != time_key:
                        last_signal_check = time_key
                        print(f"🔍 بررسی سیگنال‌ها در {now_iran.strftime('%H:%M')}...")
                        
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

            # ۴. گزارش روزانه ساعت ۲۲ ایران
            if now_iran.hour == 22 and now_iran.minute < 5:
                day_key = now_iran.strftime("%Y-%m-%d")
                if last_daily_report != day_key:
                    last_daily_report = day_key
                    daily_report()

            # ۵. گزارش هفتگی شنبه‌ها ساعت ۱۰ صبح
            if now_iran.weekday() == 5 and now_iran.hour == 10 and now_iran.minute < 5:
                week_key = now_iran.strftime("%Y-%W")
                if last_weekly_report != week_key:
                    last_weekly_report = week_key
                    weekly_report()

            # ۶. پیام آخر هفته جمعه‌ها ساعت ۲۳
            if now_iran.weekday() == 4 and now_iran.hour == 23 and now_iran.minute < 5:
                weekend_key = now_iran.strftime("%Y-%W")
                if last_weekend_msg != weekend_key:
                    last_weekend_msg = weekend_key
                    weekend_message()

            time.sleep(30)

        except Exception as e:
            print(f"خطا در حلقه اصلی: {e}")
            time.sleep(30)
