import asyncio
import os
import time
from datetime import datetime
from pyrogram import Client
from pyrogram.errors import FloodWait, RPCError

# ===== НАСТРОЙКИ =====
# БЕРЁМ ИЗ ПЕРЕМЕННЫХ ОКРУЖЕНИЯ (их зададим в Railway)
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
PHONE_NUMBER = os.environ.get("PHONE_NUMBER", "")
GROUPS_FILE = "groups.txt"      # Файл со списком ID групп (загрузим отдельно)
MESSAGE_FILE = "message.txt"    # Файл с текстом (тоже загрузим)
POSTS_PER_HOUR = int(os.environ.get("POSTS_PER_HOUR", 5))
SESSION_NAME = "my_account"     # Файл сессии (создастся при первом запуске)
# =====================

INTERVAL_SECONDS = 3600 // POSTS_PER_HOUR

def load_groups():
    if not os.path.exists(GROUPS_FILE):
        print(f"❌ Файл {GROUPS_FILE} не найден!")
        return []
    with open(GROUPS_FILE, 'r', encoding='utf-8') as f:
        groups = [line.strip() for line in f if line.strip()]
    return groups

def load_message():
    if not os.path.exists(MESSAGE_FILE):
        print(f"❌ Файл {MESSAGE_FILE} не найден!")
        return None
    with open(MESSAGE_FILE, 'r', encoding='utf-8') as f:
        message = f.read()
    return message

async def send_to_all_groups(app):
    groups = load_groups()
    message = load_message()
    if not groups or not message:
        return
    print(f"\n🕒 {datetime.now()} - Отправка...")
    for group_id in groups:
        try:
            await app.send_message(int(group_id), message)
            print(f"✅ Отправлено в {group_id}")
            await asyncio.sleep(5)
        except FloodWait as e:
            print(f"⚠️ Флуд: ждём {e.value}с")
            await asyncio.sleep(e.value)
        except Exception as e:
            print(f"❌ Ошибка в {group_id}: {e}")

async def main():
    print("🤖 Юзербот запускается на Railway...")
    if not all([API_ID, API_HASH, PHONE_NUMBER]):
        print("❌ Ошибка: не заданы API_ID, API_HASH или PHONE_NUMBER в переменных окружения")
        return
    
    app = Client(
        name=SESSION_NAME,
        api_id=API_ID,
        api_hash=API_HASH,
        phone_number=PHONE_NUMBER,
        workdir="./"  # чтобы сессия создавалась в текущей папке
    )
    await app.start()
    print("✅ Авторизация успешна")
    
    # Бесконечный цикл рассылки
    while True:
        try:
            await send_to_all_groups(app)
            print(f"⏳ Следующая отправка через {INTERVAL_SECONDS}с")
            await asyncio.sleep(INTERVAL_SECONDS)
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())