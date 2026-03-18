import urllib.request
import urllib.parse
import json
import time
import random
import sqlite3
import re

TOKEN = "YOUR_BOT_TOKEN"
URL = f"https://api.telegram.org/bot{TOKEN}/"

# --- БД ---
conn = sqlite3.connect("db.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    coins INTEGER DEFAULT 0,
    is_admin INTEGER DEFAULT 0,
    messages INTEGER DEFAULT 0
)
""")
conn.commit()

# --- функции БД ---
def get_user(user_id):
    cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    user = cursor.fetchone()
    if not user:
        cursor.execute(
            "INSERT INTO users (user_id, coins, is_admin, messages) VALUES (?, 0, 0, 0)",
            (user_id,)
        )
        conn.commit()

def add_coins(user_id, amount):
    cursor.execute("UPDATE users SET coins = coins + ? WHERE user_id=?", (amount, user_id))
    conn.commit()

def get_balance(user_id):
    cursor.execute("SELECT coins FROM users WHERE user_id=?", (user_id,))
    return cursor.fetchone()[0]

def set_admin(user_id):
    cursor.execute("UPDATE users SET is_admin=1 WHERE user_id=?", (user_id,))
    conn.commit()

def add_message(user_id):
    cursor.execute("UPDATE users SET messages = messages + 1 WHERE user_id=?", (user_id,))
    conn.commit()

def get_messages(user_id):
    cursor.execute("SELECT messages FROM users WHERE user_id=?", (user_id,))
    return cursor.fetchone()[0]

# --- активность ---
def get_activity(msgs):
    if msgs < 50:
        return "🟢 Новичок"
    elif msgs < 200:
        return "🟡 Активный"
    elif msgs < 500:
        return "🟠 Про"
    else:
        return "🔴 Легенда"

# --- Telegram API ---
def send_message(chat_id, text):
    data = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": text
    }).encode()

    urllib.request.urlopen(URL + "sendMessage", data)

def get_updates(offset):
    url = URL + f"getUpdates?offset={offset}&timeout=10"
    response = urllib.request.urlopen(url)
    return json.loads(response.read())

# --- расчёт коинов ---
def calculate_coins(text):
    text = text.strip()

    if len(text) < 3:
        return 0

    clean = re.sub(r'[^a-zA-Zа-яА-Я0-9 ]', '', text)
    words = clean.split()

    if len(words) < 2:
        return 1

    coins = len(text) // 10

    if len(text) > 50:
        coins += 3
    if len(text) > 120:
        coins += 5

    if coins > 20:
        coins = 20

    return coins

# --- кулдаун ---
last_message_time = {}

# --- обработка сообщений ---
def handle_message(message):
    chat_id = message["chat"]["id"]
    user_id = message["from"]["id"]
    text = message.get("text", "")

    get_user(user_id)
    add_message(user_id)

    # --- команды ---
    if text == "/bot":
        send_message(chat_id,
"""🤖 Команды:

/balance - профиль
/shop - магазин
/buy admin - купить админку
/bet 100 - ставка
/duel (ответом) - дуэль
""")
        return

    if text == "/balance":
        coins = get_balance(user_id)
        msgs = get_messages(user_id)
        activity = get_activity(msgs)
        username = message["from"].get("username", "без ника")

        send_message(chat_id,
f"""👤 Ник: @{username}

💰 Баланс: {coins}
📨 Сообщений: {msgs}
🔥 Активность: {activity}
""")
        return

    if text == "/shop":
        send_message(chat_id,
"""🛒 Магазин:
🎁 Подарок - 100
👑 Админка - 10000 (/buy admin)
""")
        return

    if text.startswith("/buy"):
        args = text.split()
        if len(args) < 2:
            return

        if args[1] == "admin":
            coins = get_balance(user_id)
            if coins >= 10000:
                add_coins(user_id, -10000)
                set_admin(user_id)
                send_message(chat_id, "👑 Ты купил админку!")
            else:
                send_message(chat_id, "❌ Недостаточно коинов")
        return

    if text.startswith("/bet"):
        args = text.split()
        if len(args) < 2:
            return

        amount = int(args[1])
        coins = get_balance(user_id)

        if coins < amount:
            send_message(chat_id, "❌ Недостаточно коинов")
            return

        if random.choice([True, False]):
            add_coins(user_id, amount)
            send_message(chat_id, f"🎉 Победа! +{amount}")
        else:
            add_coins(user_id, -amount)
            send_message(chat_id, f"💀 Проигрыш -{amount}")
        return

    if text.startswith("/duel"):
        if "reply_to_message" not in message:
            send_message(chat_id, "Ответь на сообщение игрока")
            return

        opponent = message["reply_to_message"]["from"]["id"]
        winner = random.choice([user_id, opponent])

        add_coins(winner, 50)
        send_message(chat_id, f"⚔ Победил {winner} (+50 коинов)")
        return

    # --- анти-спам ---
    now = time.time()

    if user_id in last_message_time:
        if now - last_message_time[user_id] < 5:
            return

    last_message_time[user_id] = now

    coins = calculate_coins(text)

    if coins > 0:
        add_coins(user_id, coins)

# --- запуск ---
def main():
    offset = 0
    print("Бот запущен...")

    while True:
        updates = get_updates(offset)

        for update in updates["result"]:
            offset = update["update_id"] + 1

            if "message" in update:
                handle_message(update["message"])

        time.sleep(1)

if __name__ == "__main__":
    main()
