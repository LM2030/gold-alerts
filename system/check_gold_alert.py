"""
Gold price alert — запускається GitHub Actions кожні 10 хв (пн-пт).
Надсилає алерти в Telegram при русі XAU/USD від 0.5%.

Стан (які алерти вже надіслані сьогодні) зберігається через GitHub Actions cache.
"""

import urllib.request
import urllib.parse
import json
import os
import sys
from datetime import datetime, date, timezone

# ── Конфіг (з GitHub Secrets / env vars) ─────────────────
TG_TOKEN   = os.environ.get("TG_TOKEN", "")
TG_CHAT_ID = os.environ.get("TG_CHAT_ID", "")
THRESHOLD  = float(os.environ.get("THRESHOLD_1", "0.5"))  # рух (%)
STATE_FILE = "alert_state.json"


# ── Ціна XAU/USD (Yahoo Finance) ─────────────────────────
def get_price():
    url = "https://query1.finance.yahoo.com/v8/finance/chart/GC=F?interval=1m&range=1d"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.loads(r.read())
    meta       = data["chart"]["result"][0]["meta"]
    price      = meta.get("regularMarketPrice") or meta.get("previousClose")
    prev_close = meta.get("previousClose", price)
    change_pct = ((price - prev_close) / prev_close * 100) if prev_close else 0
    return float(price), float(prev_close), float(change_pct)


# ── Telegram ──────────────────────────────────────────────
def send_tg(text):
    url  = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id":    TG_CHAT_ID,
        "text":       text,
        "parse_mode": "HTML"
    }).encode()
    with urllib.request.urlopen(url, data=data, timeout=15) as r:
        return json.loads(r.read())


# ── Стан алертів (скидається щодня) ──────────────────────
def load_state():
    today = str(date.today())
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, encoding="utf-8") as f:
            s = json.load(f)
        if s.get("date") == today:
            return s
    return {
        "date": today,
        "up":   False,   # +0.5%
        "down": False,   # -0.5%
    }


def save_state(s):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(s, f)


# ── Головна логіка ────────────────────────────────────────
def main():
    if not TG_TOKEN or not TG_CHAT_ID:
        print("❌ TG_TOKEN або TG_CHAT_ID не задані")
        sys.exit(1)

    # Отримуємо ціну
    try:
        price, prev, change = get_price()
    except Exception as e:
        print(f"❌ Помилка отримання ціни: {e}")
        sys.exit(0)  # не падаємо — просто пропускаємо цей запуск

    now_utc = datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M UTC")
    sign    = "+" if change >= 0 else ""
    delta   = price - prev
    delta_s = (f"+${delta:,.0f}" if delta >= 0 else f"-${abs(delta):,.0f}")

    print(f"XAU/USD: ${price:,.2f}  {sign}{change:.2f}%  (вчора ${prev:,.2f})")

    state = load_state()

    # ── 📈 Рух вгору ─────────────────────────────────────
    if change >= THRESHOLD and not state["up"]:
        send_tg(
            f"📈 <b>XAU/USD — Рух вгору {sign}{change:.2f}%</b>\n\n"
            f"💰 Ціна: <b>${price:,.2f}</b>\n"
            f"📊 Зміна за день: <b>{sign}{change:.2f}%</b>  ({delta_s})\n"
            f"↕️ Вчора закрив: ${prev:,.2f}\n\n"
            f"⏰ {now_utc}"
        )
        state["up"] = True
        print(f"✅ Надіслано 📈 вгору ({sign}{change:.2f}%)")

    # ── 📉 Рух вниз ──────────────────────────────────────
    elif change <= -THRESHOLD and not state["down"]:
        send_tg(
            f"📉 <b>XAU/USD — Рух вниз {sign}{change:.2f}%</b>\n\n"
            f"💰 Ціна: <b>${price:,.2f}</b>\n"
            f"📊 Зміна за день: <b>{sign}{change:.2f}%</b>  ({delta_s})\n"
            f"↕️ Вчора закрив: ${prev:,.2f}\n\n"
            f"⏰ {now_utc}"
        )
        state["down"] = True
        print(f"✅ Надіслано 📉 вниз ({sign}{change:.2f}%)")

    else:
        print(f"ℹ️  Без алерту — поріг не досягнуто ({THRESHOLD}%)")

    save_state(state)


if __name__ == "__main__":
    main()
